ARG PYTHON_IMAGE=python:3.11-slim-bookworm
ARG JAVA_IMAGE=eclipse-temurin:11-jdk-jammy
ARG GO_IMAGE=golang:1.19.13-bullseye
FROM ${JAVA_IMAGE} AS java
FROM ${GO_IMAGE} AS go
FROM ${PYTHON_IMAGE}
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ libc6-dev \
    && rm -rf /var/lib/apt/lists/*
COPY --from=java /opt/java/openjdk /opt/java/openjdk
COPY --from=go /usr/local/go /usr/local/go
ENV PATH="/opt/java/openjdk/bin:/usr/local/go/bin:${PATH}" \
    GOCACHE=/tmp/gocache GOPATH=/tmp/gopath GOPROXY=off GOTOOLCHAIN=local \
    PYTHONDONTWRITEBYTECODE=1
COPY exec.py /opt/prismqa/exec.py
USER 1000:1000
WORKDIR /work
