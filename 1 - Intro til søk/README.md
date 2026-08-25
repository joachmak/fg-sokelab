# Bekk Search

A small full-text search app over the combined Bekk christmas + fag article dataset,
built on OpenSearch. Everything runs via Docker Compose:

- **opensearch** — official `opensearchproject/opensearch:latest` image, single node,
  security plugin disabled and CORS enabled so the browser can query it directly.
- **indexer** — a one-shot Python container that creates the `bekk-articles` index
  (with a Norwegian-language text analyzer) and bulk-loads
  `indexer/data/bekk-opensearch.ndjson` into it. Runs once per `docker compose up`
  and then exits.

## Run it

```bash
docker compose up --build
```

First run pulls the OpenSearch image and builds the two custom images, so it can
take a few minutes. Wait for the `bekk-indexer` container to log "Indexing complete."
Then open:

- **OpenSearch API:** http://localhost:9200 (e.g. `curl http://localhost:9200/bekk-articles/_count`)
- **OpenSearch Dashboards:** http://localhost:5601

To stop everything:

```bash
docker compose down
```

To wipe the indexed data too (OpenSearch data is stored in a named volume):

```bash
docker compose down -v
```

## Re-indexing after changing the data

The indexer drops and recreates the `bekk-articles` index every time it runs, so
if you update `indexer/data/bekk-opensearch.ndjson` you can just re-run the indexer
alone:

```bash
docker compose up --build indexer
```

## Notes / things you might want to change

- **Security is disabled** (`DISABLE_SECURITY_PLUGIN=true`) and CORS is wide open
  (`http.cors.allow-origin=*`) so the React app can call OpenSearch directly from
  the browser without a backend. This is fine for local/dev use, but if you ever
  expose this beyond your own machine, put OpenSearch behind a proper API/auth layer
  instead.
- **`authors`** are stored as raw Sanity reference IDs, not names (see the data
  pipeline conversation) — the search UI doesn't currently show author names.
- The search query boosts `title`, then `tags`/`keywords`, then `summary`, then
  falls back to `previewText`/`content`/`stringDescription`, with `fuzziness: AUTO`
  for typo tolerance. Tune the field list/boosts in `frontend/src/api/opensearch.js`.
- Ports: OpenSearch on `9200`, the app on `8080`. Change the `ports:` mappings in
  `docker-compose.yml` if either is already taken on your machine — if you change
  the OpenSearch port, also update `VITE_OPENSEARCH_URL` in the `frontend` build args.
