# --- Stage 1: Build Frontend ---
FROM node:18-slim AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Final Image ---
FROM python:3.9-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN if [ -f /etc/apt/sources.list ]; then \
        sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list && \
        sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list; \
    elif [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
        sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources; \
    fi && \
    apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# Copy project files (respects .dockerignore)
COPY . .

# Copy built frontend assets to Django
# 1. Copy all assets to static directory
COPY --from=frontend-builder /frontend/dist/assets ./static/assets
# 2. Copy index.html to templates so Django can render it
COPY --from=frontend-builder /frontend/dist/index.html ./templates/index.html
# 3. Copy other root files (like vite.svg, favicon.ico) to static
COPY --from=frontend-builder /frontend/dist/vite.svg ./static/

# Create necessary directories
RUN mkdir -p state logs

# Set environment variable for collectstatic
ENV WHITENOISE_MANIFEST_STRICT=False

# Collect static files
RUN python manage.py collectstatic --noinput --clear

# Setup entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
