# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .

RUN pip install --no-cache-dir .
RUN playwright install --with-deps chromium

# Copy the rest of the application code
COPY . .

# Set PYTHONPATH
ENV PYTHONPATH=/app
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Run the API server
CMD ["python", "src/api/run_api.py"]
