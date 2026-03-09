FROM python:3.12-slim

# Metadata
LABEL description="Robbi Application Container"
LABEL version="1.0"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Clone the git repository and checkout the main branch
RUN git clone https://github.com/lipnelz/robbi.git . && \
    git checkout main

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir docker==7.1.0

# Create config directory
RUN mkdir -p /app/config

# Copy the configuration file to the root
# Note: The topology.json file must be present in the build context
COPY topology.json /app/

# Copy the startup script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Default command to start the application
ENTRYPOINT ["/app/entrypoint.sh"]