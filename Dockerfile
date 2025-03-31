# Use an official Python runtime as a parent image
FROM continuumio/miniconda3

# Set working directory
WORKDIR /app

# Copy environment file
COPY environment.yml .

# Create conda environment
RUN conda env create -f environment.yml

# Install Chrome and ChromeDriver
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy the project files
COPY . .

# Activate conda environment
SHELL ["conda", "run", "-n", "indeed-scraper", "/bin/bash", "-c"]

# Set default command
CMD ["conda", "run", "-n", "indeed-scraper", "python", "indeed_scraper.py", "--args-will-be-overridden"]

# Example run command: `docker run indeed-scraper conda run -n indeed-scraper python indeed_scraper.py --job-title "Data Analyst" --location "New York" --max-pages 5`