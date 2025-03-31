.PHONY: setup build run clean jupyter test

# Create and setup conda environment
setup:
	conda env create -f environment.yml
	conda activate indeed-scraper
	python -m spacy download en_core_web_sm

# Build Docker image
build:
	docker build -t indeed-scraper .

# Run scraper in Docker
run:
	docker run indeed-scraper

# Run Jupyter notebook
jupyter:
	conda run -n indeed-scraper jupyter notebook

# Run tests
test:
	conda run -n indeed-scraper pytest

# Clean up
clean:
	conda env remove -n indeed-scraper
	docker rmi indeed-scraper

# Run scraper locally (without Docker)
scrape:
	conda run -n indeed-scraper python indeed_scraper.py 