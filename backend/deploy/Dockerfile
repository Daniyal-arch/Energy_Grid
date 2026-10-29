# The backend's Lambda image: FastAPI behind the AWS Lambda Web Adapter (response streaming).
# Build from the repository root (it needs agent/ and a few of the app's map files):
#   docker build -f backend/deploy/Dockerfile -t infraatlas-backend .
# The adapter runs the web app as is: locally the same image is a plain uvicorn server on 8080.
# Multi-arch base images: built for arm64 in CI (backend.yml), amd64 works for local runs.

ARG PYTHON_IMAGE=public.ecr.aws/docker/library/python:3.12-slim
FROM public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 AS lwa
FROM ghcr.io/astral-sh/uv:0.9.5 AS uv

FROM ${PYTHON_IMAGE} AS build
COPY --from=uv /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /var/task/backend
COPY backend/pyproject.toml backend/uv.lock ./
# optional providers: --build-arg EXTRAS="--extra openai --extra aws"
ARG EXTRAS=""
# An optional CA bundle (build secret "ca") for builds behind a TLS-inspecting proxy.
RUN --mount=type=secret,id=ca,required=false \
    if [ -f /run/secrets/ca ]; then export SSL_CERT_FILE=/run/secrets/ca; fi; \
    uv sync --frozen --no-dev --no-install-project ${EXTRAS}
# DuckDB extensions installed at build: nothing is downloaded at start.
RUN --mount=type=secret,id=ca,required=false \
    if [ -f /run/secrets/ca ]; then export SSL_CERT_FILE=/run/secrets/ca; fi; \
    .venv/bin/python -c "import duckdb; c = duckdb.connect(config={'extension_directory': '/opt/duckdb_ext'}); [c.install_extension(e) for e in ('httpfs', 'spatial')]; c.install_extension('h3', repository='community')"

FROM ${PYTHON_IMAGE}
COPY --from=lwa /lambda-adapter /opt/extensions/lambda-adapter
COPY --from=build /var/task/backend/.venv /var/task/backend/.venv
COPY --from=build /opt/duckdb_ext /opt/duckdb_ext
COPY backend/app /var/task/backend/app
COPY backend/agent /var/task/backend/agent
COPY backend/tools /var/task/backend/tools
COPY backend/data /var/task/backend/data
COPY backend/mcp_server /var/task/backend/mcp_server
COPY backend/obs /var/task/backend/obs
COPY backend/evals /var/task/backend/evals
COPY agent /var/task/agent
COPY frontend/src/app/datasets.json frontend/src/app/store.ts /var/task/frontend/src/app/
COPY frontend/public/data/eu/countries.json frontend/public/data/eu/world.json \
     frontend/public/data/eu/grid.json frontend/public/data/eu/plants.json \
     frontend/public/data/eu/world_plants.json frontend/public/data/eu/prices.json \
     frontend/public/data/eu/water.json frontend/public/data/eu/cities.json \
     /var/task/frontend/public/data/eu/
COPY frontend/public/data/us/states.json frontend/public/data/us/plants.json /var/task/frontend/public/data/us/
ARG GIT_SHA=dev
ENV PATH=/var/task/backend/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    ATLAS_ROOT=/var/task \
    DUCKDB_EXTENSION_DIR=/opt/duckdb_ext \
    GIT_SHA=${GIT_SHA} \
    AWS_LWA_INVOKE_MODE=response_stream \
    AWS_LWA_PORT=8080 \
    AWS_LWA_READINESS_CHECK_PATH=/api/health
WORKDIR /var/task/backend
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
