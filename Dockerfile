FROM mcr.microsoft.com/dotnet/sdk:8.0-alpine AS builder

RUN apk add --no-cache python3 py3-pip

COPY src ./src
COPY restler ./restler
COPY build-restler.py .

RUN python3 build-restler.py --dest_dir /build

RUN python3 -m compileall -b /build/engine

FROM mcr.microsoft.com/dotnet/aspnet:8.0-alpine AS target

RUN apk add --no-cache python3 py3-pip

# Create a virtual environment
RUN python3 -m venv /venv

# Activate the virtual environment and install packages
RUN /venv/bin/pip install applicationinsights requests

# Ensure the virtual environment is activated by default
ENV PATH="/venv/bin:$PATH"

COPY --from=builder /build /RESTler
