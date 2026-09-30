"""
Generate an OpenSearch bulk request for the restaurant index.

Reads restauranter.json and writes a request that can be pasted directly into
OpenSearch Dev Tools:

    POST _bulk
    {"index": {"_index": "restauranter-v1", "_id": "<orgnummer>"}}
    {<document>}
    ...

Usage:
    python3 generate-bulk-request.py            # writes ../index-bulk-request.ndjson
    python3 generate-bulk-request.py --stdout   # prints the request instead
"""

import argparse
import json
import sys
from pathlib import Path

INDEX_NAME = "restauranter-v1"

DATA_FILE = Path(__file__).parent / "restauranter.json"
OUTPUT_FILE = Path(__file__).parent.parent / "index-bulk-request.ndjson"


def transform(doc: dict) -> dict:
    """
    Adjust a document before it is indexed.

    Returned unchanged by default. If your index template uses other field names,
    or you want to add/remove fields, change the document here.
    """
    return doc


def build_bulk_request(docs: list[dict]) -> str:
    """Build a Dev Tools bulk request (NDJSON) with orgnummer as document id."""
    lines = ["POST _bulk"]
    for doc in docs:
        doc = transform(doc)
        action = {"index": {"_index": INDEX_NAME, "_id": doc["orgnummer"]}}
        lines.append(json.dumps(action, ensure_ascii=False))
        lines.append(json.dumps(doc, ensure_ascii=False))
    # The bulk API requires the request to end with a newline
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--stdout",
        action="store_true",
        help=f"print the request instead of writing {OUTPUT_FILE.name}",
    )
    args = parser.parse_args()

    with open(DATA_FILE, encoding="utf-8") as f:
        docs = json.load(f)

    ids = [doc["orgnummer"] for doc in docs]
    if len(ids) != len(set(ids)):
        sys.exit("Duplicate orgnummer found - documents would overwrite each other.")

    request = build_bulk_request(docs)

    if args.stdout:
        sys.stdout.write(request)
    else:
        OUTPUT_FILE.write_text(request, encoding="utf-8")
        print(f"Wrote {len(docs)} documents to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
