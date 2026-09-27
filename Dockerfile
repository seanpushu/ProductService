FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Non-sensitive build identifiers, exposed by GET /version.
ARG GIT_SHA=local
ARG APP_VERSION=0.2.1
ENV GIT_SHA=${GIT_SHA} \
    APP_VERSION=${APP_VERSION} \
    PYTHONUNBUFFERED=1

# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
