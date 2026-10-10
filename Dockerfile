# docker build -t mc .
# docker container run mc
FROM python:3.10.11-alpine3.17
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /bin/

ENV UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy

WORKDIR /multicrypto

# Install dependencies first so this layer is cached between code changes.
COPY pyproject.toml uv.lock ./
RUN ["uv", "sync", "--locked", "--no-install-project"]

COPY . .
RUN ["uv", "sync", "--locked"]
CMD ["uv", "run", "--no-sync", "python", "-m", "pytest", "--cov=./", "--cov-report=html"]
