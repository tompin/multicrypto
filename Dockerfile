# docker build -t mc .
# docker container run mc
FROM python:3.10.11-alpine3.17

WORKDIR /multicrypto

# Install dependencies first so this layer is cached between code changes.
COPY requirements.txt requirements_dev.txt ./
RUN ["python", "-m", "venv", "/venv"]
RUN ["/venv/bin/pip", "install", "--no-cache-dir", "-r", "requirements.txt", "-r", "requirements_dev.txt"]

COPY . .
CMD ["/venv/bin/python", "-m", "pytest", "--cov=./", "--cov-report=html"]
