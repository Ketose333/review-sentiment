# syntax=docker/dockerfile:1

FROM python:3.11-slim-bookworm AS artifacts
WORKDIR /build
COPY backend/app/artifacts.py backend/app/artifacts.py
COPY models/lstm/tokenizer.json models/lstm/tokenizer.json
COPY models/klue_bert/config.json models/klue_bert/config.json
COPY models/klue_bert/tokenizer.json models/klue_bert/tokenizer.json
COPY models/klue_bert/tokenizer_config.json models/klue_bert/tokenizer_config.json
COPY scripts/install_model_artifacts.py scripts/install_model_artifacts.py
RUN python scripts/install_model_artifacts.py /build /opt/model-artifacts

FROM python:3.11-slim-bookworm AS runtime-deps
ARG TARGETARCH
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    JAVA_HOME=/opt/java \
    TFIDF_ARTIFACT_DIR=/opt/model-artifacts/models/tfidf_lr \
    LSTM_ARTIFACT_DIR=/opt/model-artifacts/models/lstm \
    KLUE_BERT_ARTIFACT_DIR=/opt/model-artifacts/models/klue_bert

RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jdk-headless libgomp1 \
    && ln -s "$(dirname "$(dirname "$(readlink -f "$(command -v java)")")")" "$JAVA_HOME" \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
# The CPU wheel index avoids CUDA packages. tensorflow-cpu has no ARM64 wheel;
# the regular tensorflow package has a Linux ARM64 wheel and provides the same import.
RUN sed '/^tensorflow[<=>]/d' backend/requirements.txt > /tmp/api-requirements.txt \
    && case "$TARGETARCH" in amd64) tensorflow_package='tensorflow-cpu==2.21.0' ;; arm64) tensorflow_package='tensorflow==2.21.0' ;; *) exit 1 ;; esac \
    && python -m pip install --no-cache-dir 'torch==2.12.1+cpu' --index-url https://download.pytorch.org/whl/cpu \
    && python -m pip install --no-cache-dir -r /tmp/api-requirements.txt "$tensorflow_package" 'transformers==5.12.1' \
    && rm /tmp/api-requirements.txt

FROM runtime-deps
COPY backend /app/backend
COPY src /app/src
COPY --from=artifacts /opt/model-artifacts /opt/model-artifacts

RUN useradd --create-home --uid 10001 appuser \
    && chmod -R a+rX /opt/model-artifacts
USER appuser
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
