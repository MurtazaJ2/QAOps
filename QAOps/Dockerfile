FROM python:3.10-slim

# Install git since the agent uses it to clone and revert
RUN apt-get update && \
    apt-get install -y git && \
    rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Copy the agent codebase
COPY . .

# Install the agent module
RUN pip install --no-cache-dir -e .

# Create an entrypoint script to parse Docker args properly
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
