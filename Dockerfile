FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy the project files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -e ".[test]"

# Run tests first
RUN pytest tests/

# Create a simple run script that loads environment variables
RUN echo '#!/bin/sh\nset -e\n\nif [ ! -f .env ]; then\n    echo "Error: .env file not found"\n    exit 1\nfi\n\n# Load environment variables\nwhile read line; do\n    case "$line" in\n        "#"*|"") continue ;;\n    esac\n    eval "export $line"\ndone < .env\n\npython examples/real_usage.py' > /app/run.sh && \
    chmod +x /app/run.sh

# Set the entrypoint
ENTRYPOINT ["/app/run.sh"] 