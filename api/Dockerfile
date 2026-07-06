FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (for pandas & optional cudf) – keep minimal
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libffi-dev \
        python3-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the FastAPI application code
COPY . .

# Expose the FastAPI port (default 8080)
EXPOSE 8080

# Command to run the server
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
