"""
Sets up semantic search over a subset of the Norwegian Wikipedia corpus
following the official OpenSearch semantic search approach:
https://docs.opensearch.org/latest/vector-search/ai-search/semantic-search/

Flow:
  1. Configure ML Commons to allow model inference on data nodes
  2. Register and deploy a sentence-transformer model from the OpenSearch
     model hub — the model runs *inside* OpenSearch, no external service needed
  3. Create a text_embedding ingest pipeline backed by the model
  4. Create a search pipeline with neural_query_enricher so the model_id
     does not need to be specified in every query
  5. Create the norsk-wikipedia index with a knn_vector field and both
     pipelines set as defaults
  6. Download the first MAX_DOCS articles from the 2019 Norwegian Wikipedia
     corpus and bulk-index them — OpenSearch runs each document through the
     ingest pipeline and generates the embedding automatically

Runs once as a one-shot container; exits 0 on success.
"""
import io
import json
import os
import random
import sys
import tarfile
import time
import urllib.request

import requests
from tqdm import tqdm

OPENSEARCH_URL = os.environ.get("OPENSEARCH_URL", "http://localhost:9200")
MAX_DOCS = int(os.environ.get("MAX_DOCS", "1000"))

INDEX_NAME = "norsk-wikipedia"
INGEST_PIPELINE = "wikipedia-embeddings"
SEARCH_PIPELINE = "wikipedia-neural-search"

WIKIPEDIA_URL = "https://www.nb.no/sbfil/tekst/2019_wikipedia.tar.gz"

# paraphrase-multilingual-MiniLM-L12-v2: multilingual (Norwegian + English),
# 384-dimensional, available in the OpenSearch model hub as TORCH_SCRIPT.
MODEL_NAME = "huggingface/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODEL_VERSION = "1.0.1"
VECTOR_DIM = 384

BULK_CHUNK_SIZE = 50

INDEX_MAPPING = {
    "settings": {
        "index.knn": True,
        "default_pipeline": INGEST_PIPELINE,
        "index.search.default_pipeline": SEARCH_PIPELINE,
        "number_of_shards": 1,
        "number_of_replicas": 0,
    },
    "mappings": {
        "properties": {
            "pageid": {"type": "keyword"},
            "title": {
                "type": "text",
                "analyzer": "norwegian",
                "fields": {"raw": {"type": "keyword"}},
            },
            "text": {"type": "text", "analyzer": "norwegian"},
            # The field the ingest pipeline reads to generate the embedding.
            # Populated as "title. first paragraph" by the indexer.
            "embed_text": {"type": "text"},
            "content_vector": {
                "type": "knn_vector",
                "dimension": VECTOR_DIM,
                "method": {
                    "name": "hnsw",
                    "space_type": "cosinesimil",
                    "engine": "lucene",
                },
            },
        }
    },
}


# ---------------------------------------------------------------------------
# Readiness
# ---------------------------------------------------------------------------

def wait_for_opensearch(max_attempts=30, delay_seconds=3):
    for attempt in range(1, max_attempts + 1):
        try:
            r = requests.get(OPENSEARCH_URL, timeout=5)
            if r.status_code == 200:
                print(f"OpenSearch ready (attempt {attempt}).")
                return
        except requests.exceptions.RequestException as exc:
            print(f"Attempt {attempt}/{max_attempts}: not ready ({exc}).")
        time.sleep(delay_seconds)
    print("Gave up waiting for OpenSearch.", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# ML Commons
# ---------------------------------------------------------------------------

def configure_ml_commons():
    settings = {
        "persistent": {
            "plugins.ml_commons.only_run_on_ml_node": False,
            "plugins.ml_commons.model_access_control_enabled": False,
            "plugins.ml_commons.native_memory_threshold": 99,
        }
    }
    r = requests.put(f"{OPENSEARCH_URL}/_cluster/settings", json=settings)
    if r.status_code != 200:
        print(f"Warning: ML Commons settings returned {r.status_code}: {r.text}")
    else:
        print("ML Commons configured.")


def wait_for_task(task_id, max_attempts=240, delay_seconds=5):
    for _ in range(max_attempts):
        r = requests.get(f"{OPENSEARCH_URL}/_plugins/_ml/tasks/{task_id}")
        if r.status_code == 200:
            data = r.json()
            state = data.get("state")
            if state == "COMPLETED":
                return data.get("model_id") or data.get("resource_id")
            if state in ("FAILED", "ERROR"):
                print(f"ML task failed: {data}", file=sys.stderr)
                sys.exit(1)
            print(f"  Task {task_id}: {state}...")
        time.sleep(delay_seconds)
    print(f"Timed out waiting for task {task_id}.", file=sys.stderr)
    sys.exit(1)


def find_deployed_model():
    r = requests.post(
        f"{OPENSEARCH_URL}/_plugins/_ml/models/_search",
        json={
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"name.keyword": MODEL_NAME}},
                        {"term": {"model_state": "DEPLOYED"}},
                    ]
                }
            },
            "size": 1,
        },
        headers={"Content-Type": "application/json"},
    )
    if r.status_code == 200:
        hits = r.json().get("hits", {}).get("hits", [])
        if hits:
            return hits[0]["_id"]
    return None


def register_and_deploy_model():
    existing = find_deployed_model()
    if existing:
        print(f"Model already deployed (id: {existing}). Reusing.")
        return existing

    print(f"Registering '{MODEL_NAME}' from OpenSearch model hub...")
    r = requests.post(
        f"{OPENSEARCH_URL}/_plugins/_ml/models/_register",
        json={
            "name": MODEL_NAME,
            "version": MODEL_VERSION,
            "model_format": "TORCH_SCRIPT",
        },
        headers={"Content-Type": "application/json"},
    )
    if r.status_code not in (200, 201):
        print(f"Failed to register model: {r.status_code} {r.text}", file=sys.stderr)
        sys.exit(1)

    task_id = r.json().get("task_id")
    print(f"Downloading model (task {task_id}) — this may take a few minutes...")
    model_id = wait_for_task(task_id)
    print(f"Model registered (id: {model_id}).")

    print("Deploying model...")
    r = requests.post(f"{OPENSEARCH_URL}/_plugins/_ml/models/{model_id}/_deploy")
    if r.status_code not in (200, 201, 202):
        print(f"Failed to deploy model: {r.status_code} {r.text}", file=sys.stderr)
        sys.exit(1)
    wait_for_task(r.json().get("task_id"))
    print("Model deployed.")
    return model_id


# ---------------------------------------------------------------------------
# Pipelines
# ---------------------------------------------------------------------------

def create_ingest_pipeline(model_id):
    pipeline = {
        "description": "Generate embeddings for Norwegian Wikipedia articles",
        "processors": [
            {
                "text_embedding": {
                    "model_id": model_id,
                    "field_map": {"embed_text": "content_vector"},
                }
            }
        ],
    }
    r = requests.put(
        f"{OPENSEARCH_URL}/_ingest/pipeline/{INGEST_PIPELINE}",
        json=pipeline,
        headers={"Content-Type": "application/json"},
    )
    if r.status_code not in (200, 201):
        print(f"Failed to create ingest pipeline: {r.status_code} {r.text}", file=sys.stderr)
        sys.exit(1)
    print(f"Ingest pipeline '{INGEST_PIPELINE}' created.")


def create_search_pipeline(model_id):
    pipeline = {
        "request_processors": [
            {
                "neural_query_enricher": {
                    "default_model_id": model_id,
                    "neural_field_default_id": {
                        "content_vector": model_id,
                    },
                }
            }
        ]
    }
    r = requests.put(
        f"{OPENSEARCH_URL}/_search/pipeline/{SEARCH_PIPELINE}",
        json=pipeline,
        headers={"Content-Type": "application/json"},
    )
    if r.status_code not in (200, 201):
        print(f"Failed to create search pipeline: {r.status_code} {r.text}", file=sys.stderr)
        sys.exit(1)
    print(f"Search pipeline '{SEARCH_PIPELINE}' created.")


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------

def create_index():
    r = requests.delete(f"{OPENSEARCH_URL}/{INDEX_NAME}")
    if r.status_code not in (200, 404):
        print(f"Warning: delete index returned {r.status_code}: {r.text}")

    r = requests.put(
        f"{OPENSEARCH_URL}/{INDEX_NAME}",
        json=INDEX_MAPPING,
        headers={"Content-Type": "application/json"},
    )
    if r.status_code not in (200, 201):
        print(f"Failed to create index: {r.status_code} {r.text}", file=sys.stderr)
        sys.exit(1)
    print(f"Created index '{INDEX_NAME}'.")


# ---------------------------------------------------------------------------
# Wikipedia data
# ---------------------------------------------------------------------------

def reservoir_sample_bokmal(k: int) -> list[dict]:
    """
    Stream nob.wikipedia.json from the tar.gz and return a uniformly random
    sample of k articles using reservoir sampling (Algorithm R).
    Requires only O(k) memory regardless of corpus size.
    """
    reservoir: list[dict] = []
    seen = 0

    print(f"Downloading {WIKIPEDIA_URL} and reservoir-sampling {k} bokmål articles...")
    with urllib.request.urlopen(WIKIPEDIA_URL) as response:
        with tarfile.open(fileobj=io.BufferedReader(response), mode="r|gz") as tar:
            for member in tar:
                if not member.isfile() or "nob.wikipedia" not in member.name:
                    continue
                f = tar.extractfile(member)
                if f is None:
                    continue
                data = json.loads(f.read().decode("utf-8"))
                for article in (data if isinstance(data, list) else [data]):
                    if not article.get("title") or not article.get("text"):
                        continue
                    if seen < k:
                        reservoir.append(article)
                    else:
                        j = random.randint(0, seen)
                        if j < k:
                            reservoir[j] = article
                    seen += 1
                    if seen % 50_000 == 0:
                        print(f"  Scanned {seen:,} articles, reservoir size: {len(reservoir)}")
                break  # only one bokmål file

    print(f"Scanned {seen:,} bokmål articles total. Sampled {len(reservoir)}.")
    return reservoir


def make_embed_text(article: dict) -> str:
    title = article.get("title", "")
    first_para = article.get("text", "").split("\n")[0][:500]
    return ". ".join(p for p in [title, first_para] if p)


# ---------------------------------------------------------------------------
# Bulk indexing
# ---------------------------------------------------------------------------

def bulk_index(articles: list[dict]):
    total_errors = 0
    for start in tqdm(range(0, len(articles), BULK_CHUNK_SIZE), unit="chunk"):
        chunk = articles[start : start + BULK_CHUNK_SIZE]
        lines = []
        for article in chunk:
            doc_id = str(article.get("pageid", start))
            record = {
                "pageid": str(article.get("pageid", "")),
                "title": article.get("title", ""),
                "text": article.get("text", "")[:10_000],
                "embed_text": make_embed_text(article),
            }
            lines.append(json.dumps({"index": {"_index": INDEX_NAME, "_id": doc_id}}))
            lines.append(json.dumps(record, ensure_ascii=False))

        r = requests.post(
            f"{OPENSEARCH_URL}/_bulk",
            data=("\n".join(lines) + "\n").encode("utf-8"),
            headers={"Content-Type": "application/x-ndjson"},
            timeout=300,
        )
        if r.status_code != 200:
            print(f"Bulk request failed: {r.status_code} {r.text}", file=sys.stderr)
            sys.exit(1)

        if r.json().get("errors"):
            for item in r.json()["items"]:
                op = item.get("index", {})
                if op.get("status", 200) >= 300:
                    total_errors += 1
                    print(f"  Doc error {op.get('_id')}: {op.get('error')}", file=sys.stderr)

    if total_errors:
        print(f"Finished with {total_errors} document errors.", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    wait_for_opensearch()
    configure_ml_commons()
    model_id = register_and_deploy_model()
    create_ingest_pipeline(model_id)
    create_search_pipeline(model_id)
    create_index()

    articles = reservoir_sample_bokmal(MAX_DOCS)

    print("Bulk indexing (OpenSearch generates embeddings via ingest pipeline)...")
    bulk_index(articles)

    requests.post(f"{OPENSEARCH_URL}/{INDEX_NAME}/_refresh")
    count = requests.get(f"{OPENSEARCH_URL}/{INDEX_NAME}/_count").json()
    print(f"Index count: {count}")

    print("\nIndexing complete!")
    print(f"\nSemantic search from Dev Tools:\n")
    print(f"""\
GET norsk-wikipedia/_search
{{
  "size": 5,
  "_source": ["title", "text"],
  "query": {{
    "neural": {{
      "content_vector": {{
        "query_text": "din søkestreng her",
        "k": 5
      }}
    }}
  }}
}}""")


if __name__ == "__main__":
    main()
