FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY index_data.py .
COPY data/bekk-opensearch.ndjson ./data/bekk-opensearch.ndjson

CMD ["python", "index_data.py"]
