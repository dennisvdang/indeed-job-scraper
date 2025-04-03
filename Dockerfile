# Use an official Python runtime as a parent image
FROM continuumio/miniconda3:latest

# Set working directory
WORKDIR /app

# Copy environment file
COPY environment.yml .

# Create conda environment
RUN conda env create -f environment.yml

# Install essential system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    xvfb \
    libxi6 \
    libgconf-2-4 \
    xdg-utils \
    libnss3-dev \
    libgdk-pixbuf2.0-dev \
    libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy the project files
COPY . .

# Create data directories
RUN mkdir -p data/raw data/processed

# Activate conda environment
SHELL ["conda", "run", "-n", "indeed-scraper", "/bin/bash", "-c"]

# Display Chrome version for debugging
RUN google-chrome --version

# Set default command (will be overridden with actual arguments at runtime)
ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "indeed-scraper", "python", "indeed_scraper.py"]

# Default command line parameters (can be overridden when running the container)
CMD ["--job-title", "Software Engineer", "--location", "Remote", "--work-arrangement", "remote", "--max-pages", "3"]

# Example run command:
# docker run -it --rm indeed-scraper --job-title "Data Scientist" --location "New York" --work-arrangement "hybrid" --max-pages 5