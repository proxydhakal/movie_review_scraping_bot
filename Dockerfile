# Use official Python 3.12 slim image
FROM python:3.12-slim

# Avoid interactive prompts during builds
ENV DEBIAN_FRONTEND=noninteractive

# Set workdir
WORKDIR /app

# Install system dependencies required for Playwright/Chromium
RUN apt-get update && apt-get install -y \
    wget curl gnupg unzip libgbm1 libnss3 libatk-bridge2.0-0 \
    libxss1 libasound2 libgtk-3-0 libxcomposite1 libxrandr2 \
    libxdamage1 libxext6 libxfixes3 libdrm2 libx11-xcb1 \
    libxcb1 libx11-6 libcups2 fonts-liberation && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Download browsers (including Chromium) for Playwright
RUN python -m playwright install --with-deps

# Default command to run the bot
CMD ["python", "-m", "robocorp.tasks", "run", "tasks.py"]
