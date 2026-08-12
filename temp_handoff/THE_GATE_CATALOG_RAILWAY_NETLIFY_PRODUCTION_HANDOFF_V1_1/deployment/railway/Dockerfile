FROM python:3.14.5-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY api/requirements.txt /app/requirements.txt
RUN python -m pip install --requirement /app/requirements.txt

COPY api/integrations /app/integrations

CMD ["python", "-m", "integrations.kiot_public_catalog.railway_runtime"]
