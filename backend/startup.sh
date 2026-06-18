#!/bin/bash
# Azure App Service (Linux, Python) startup command.
# Set this as the "Startup Command" in the App Service configuration,
# or rely on Oryx detecting it. Gunicorn with Uvicorn workers serves the
# FastAPI app (and the bundled React build under app/static if present).
gunicorn app.main:app \
    --workers 2 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:${PORT:-8000} \
    --timeout 120
