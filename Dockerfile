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

# Create a script to run the real example
RUN echo '#!/bin/sh\n\
if [ ! -f .env ]; then\n\
    echo "Error: .env file not found. Please create one based on .env.example"\n\
    exit 1\n\
fi\n\
\n\
# Load environment variables\n\
export $(cat .env | xargs)\n\
\n\
# Run the real usage example\n\
python examples/real_usage.py\n\
' > /app/run.sh

RUN chmod +x /app/run.sh

# Set the entrypoint
ENTRYPOINT ["/app/run.sh"] 