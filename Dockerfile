# Ground Pass API container.
#
#   docker build -t ground-pass-api .
#   docker run --rm -p 8000:8000 ground-pass-api
#
# then open http://127.0.0.1:8000/docs

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    GROUNDPASS_CACHE_DIR=/home/app/.cache/groundpass

WORKDIR /app

# Core install only (no plotting, no dev tools) to keep the image small.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install .

# Do not run as root.
RUN useradd --create-home app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1

CMD ["uvicorn", "groundpass.api:app", "--host", "0.0.0.0", "--port", "8000"]
