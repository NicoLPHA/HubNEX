FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY hubnex ./hubnex
COPY web ./web
COPY config ./config
COPY integration ./integration

EXPOSE 8765
VOLUME ["/app/data"]
CMD ["python", "-m", "hubnex.main"]
