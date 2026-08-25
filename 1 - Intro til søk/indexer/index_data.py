"""
Creates the `bekk-articles` index in OpenSearch (dropping it first if it
already exists) and bulk-loads bekk-opensearch.ndjson into it.

Runs once as a one-shot container in docker-compose; exits 0 on success,
non-zero on failure (so `docker compose up` surfaces indexing problems).
"""
import json
import os
import sys
import time

import requests

OPENSEARCH_URL = os.environ.get("OPENSEARCH_URL", "http://localhost:9200")
INDEX_NAME = "bekk-articles"
DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "bekk-opensearch.ndjson")
BULK_CHUNK_SIZE = 500

INDEX_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
    },
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "sourceDataset": {"type": "keyword"},
            "contentType": {"type": "keyword"},
            "title": {
                "type": "text",
                "analyzer": "norwegian",
                "fields": {"raw": {"type": "keyword"}},
            },
            "authors": {"type": "keyword"},
            "tags": {"type": "keyword"},
            "series": {"type": "keyword"},
            "publishedAt": {
                "type": "date",
                "format": "strict_date_optional_time||yyyy-MM-dd",
                "ignore_malformed": True,
            },
            "createdAt": {"type": "date", "ignore_malformed": True},
            "updatedAt": {"type": "date", "ignore_malformed": True},
            "url": {"type": "keyword"},
            "language": {"type": "keyword"},
            "keywords": {"type": "keyword"},
            "previewText": {"type": "text", "analyzer": "norwegian"},
            "summary": {"type": "text", "analyzer": "norwegian"},
            "content": {"type": "text", "analyzer": "norwegian"},
            "stringDescription": {"type": "text", "analyzer": "norwegian"},
        }
    },
}


def wait_for_opensearch(max_attempts=30, delay_seconds=3):
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.get(OPENSEARCH_URL, timeout=5)
            if resp.status_code == 200:
                print(f"OpenSearch is up (attempt {attempt}).")
                return
        except requests.exceptions.RequestException as exc:
            print(f"Attempt {attempt}/{max_attempts}: OpenSearch not ready yet ({exc}).")
        time.sleep(delay_seconds)
    print("Gave up waiting for OpenSearch.", file=sys.stderr)
    sys.exit(1)


def create_index():
    # Drop the index first so re-running the indexer (e.g. `docker compose up`
    # again after updating the data file) always produces a clean, consistent index.
    del_resp = requests.delete(f"{OPENSEARCH_URL}/{INDEX_NAME}")
    if del_resp.status_code not in (200, 404):
        print(f"Warning: unexpected response deleting index: {del_resp.status_code} {del_resp.text}")

    create_resp = requests.put(
        f"{OPENSEARCH_URL}/{INDEX_NAME}",
        json=INDEX_MAPPING,
        headers={"Content-Type": "application/json"},
    )
    if create_resp.status_code not in (200, 201):
        print(f"Failed to create index: {create_resp.status_code} {create_resp.text}", file=sys.stderr)
        sys.exit(1)
    print(f"Created index '{INDEX_NAME}'.")


def transform_document(doc):
    """
    Transform document to handle nested tag objects.
    Extracts the 'current' value from tag objects like {current: "Ledelse", _type: "slug"}.
    """
    if "tags" in doc and doc["tags"] is not None:
        tags = doc["tags"]

        # Handle list of tags
        if isinstance(tags, list):
            transformed_tags = []
            for tag in tags:
                if isinstance(tag, dict) and "current" in tag:
                    transformed_tags.append(tag["current"])
                elif isinstance(tag, str):
                    transformed_tags.append(tag)
            doc["tags"] = transformed_tags

        # Handle single tag object
        elif isinstance(tags, dict) and "current" in tags:
            doc["tags"] = tags["current"]

    return doc


def load_docs():
    docs = []
    with open(DATA_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                docs.append(json.loads(line))
    return docs


def bulk_index(docs):
    total_errors = 0
    for start in range(0, len(docs), BULK_CHUNK_SIZE):
        chunk = docs[start:start + BULK_CHUNK_SIZE]
        lines = []
        for doc in chunk:
            # Transform document to handle nested tag objects
            transformed_doc = transform_document(doc.copy())
            action = {"index": {"_index": INDEX_NAME, "_id": transformed_doc["id"]}}
            lines.append(json.dumps(action))
            lines.append(json.dumps(transformed_doc, ensure_ascii=False))
        bulk_body = "\n".join(lines) + "\n"

        resp = requests.post(
            f"{OPENSEARCH_URL}/_bulk",
            data=bulk_body.encode("utf-8"),
            headers={"Content-Type": "application/x-ndjson"},
        )
        if resp.status_code != 200:
            print(f"Bulk request failed: {resp.status_code} {resp.text}", file=sys.stderr)
            sys.exit(1)

        result = resp.json()
        if result.get("errors"):
            for item in result["items"]:
                op = item.get("index", {})
                if op.get("status", 200) >= 300:
                    total_errors += 1
                    print(f"  Failed to index doc {op.get('_id')}: {op.get('error')}", file=sys.stderr)

        print(f"Indexed {min(start + BULK_CHUNK_SIZE, len(docs))}/{len(docs)} docs...")

    if total_errors:
        print(f"Finished with {total_errors} document errors.", file=sys.stderr)
        sys.exit(1)


def refresh_and_count():
    requests.post(f"{OPENSEARCH_URL}/{INDEX_NAME}/_refresh")
    count_resp = requests.get(f"{OPENSEARCH_URL}/{INDEX_NAME}/_count")
    print(f"Index count: {count_resp.json()}")


def main():
    wait_for_opensearch()
    create_index()
    docs = load_docs()
    print(f"Loaded {len(docs)} docs from {DATA_PATH}")
    bulk_index(docs)
    refresh_and_count()
    print("Indexing complete.")


if __name__ == "__main__":
    main()
