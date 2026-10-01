FROM node:22-bookworm-slim AS console
WORKDIR /build
COPY console/package*.json ./
RUN npm ci --no-audit --no-fund
COPY console/ ./
RUN npm run check && npm run build

FROM python:3.12-slim-bookworm AS app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
RUN pip install '.[console]' && useradd --uid 10001 --create-home trapdefense \
    && mkdir /state /generated /control-keys /policy-trust \
    && chown 10001:10001 /state /generated /control-keys /policy-trust
COPY --from=console /build/dist ./console/dist/
USER 10001:10001
ENTRYPOINT ["python", "-m", "asr_proxy.selfhost.main"]
CMD ["serve"]
