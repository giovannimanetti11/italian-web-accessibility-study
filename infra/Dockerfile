FROM mcr.microsoft.com/playwright/python:v1.63.0-noble@sha256:72bd171a9ffc2b4b59532aaa6210e21014d07093120dc25528870c0b840da1f0

# Chromium runs in a limited Docker container, not directly on HomeServer.
RUN apt-get update \
    && apt-get install -y --no-install-recommends iptables \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install --no-cache-dir uv==0.11.28
ENV UV_PYTHON_INSTALL_DIR=/opt/uv-python
WORKDIR /opt/iwass
COPY pyproject.toml uv.lock ./
RUN uv python install 3.13.14 \
    && uv sync --frozen --no-dev --python 3.13.14

COPY infra/container-entrypoint.sh /usr/local/bin/iwass-entrypoint
COPY iwass /work/iwass
COPY scripts /work/scripts
COPY node_modules/axe-core/axe.min.js /work/node_modules/axe-core/axe.min.js
COPY node_modules/axe-core/package.json /work/node_modules/axe-core/package.json
RUN chmod 755 /usr/local/bin/iwass-entrypoint \
    && chmod -R a+rX /work/iwass /work/scripts /work/node_modules \
    && mkdir -p /work
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp
WORKDIR /work
ENTRYPOINT ["/usr/local/bin/iwass-entrypoint"]
