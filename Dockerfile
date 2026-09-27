FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Commit SHA exposed by GET /version. The version number itself lives only in app/config.py.
ARG GIT_SHA=local
ENV GIT_SHA=${GIT_SHA} \
    PYTHONUNBUFFERED=1

# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
