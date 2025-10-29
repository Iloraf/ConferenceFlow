FROM python:3.13-slim

# you might want to install some required dependencies by your app here
# here is an example:
# RUN apt-get update && apt-get install -y \
#     gcc \
#     libpq-dev \
#     && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y \
    libglib2.0-0 libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 libjpeg-dev libopenjp2-7-dev libffi-dev \
    python3-psycopg2 libpq-dev \
    && rm -rf /var/lib/apt/lists/*


ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100

WORKDIR /app

# create and use a non root user
RUN groupadd --system appuser && \
    useradd --system --create-home --gid appuser --shell /sbin/nologin appuser
USER appuser
ENV PATH="/home/appuser/.local/bin:${PATH}"
WORKDIR /home/appuser/
COPY requirements.txt .
RUN pip install --user -r requirements.txt
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-latex-base texlive-latex-recommended lmodern \
    ghostscript \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*
USER appuser    
COPY --chown=appuser:appuser app ./app

COPY --chown=appuser:appuser init_app.py ./init_app.py
COPY --chown=appuser:appuser run.py ./run.py


COPY --chown=appuser:appuser deployment/cflow/gunicorn.conf.py .
COPY --chown=appuser:appuser deployment/cflow/wsgi.py .
