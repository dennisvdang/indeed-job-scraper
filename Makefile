.PHONY: setup build run clean jupyter test scrape run-gui scrape-custom

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
	docker run indeed-scraper conda run -n indeed-scraper python indeed_scraper.py --job-title "Data Scientist" --location "Remote" --remote --headless

# Run with GUI (non-headless mode)
run-gui:
	docker run -e DISPLAY=${DISPLAY} \
		-v /tmp/.X11-unix:/tmp/.X11-unix \
		--net=host \
		indeed-scraper conda run -n indeed-scraper python indeed_scraper.py --job-title "Data Scientist" --location "Remote" --remote --no-headless

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
	conda run -n indeed-scraper python indeed_scraper.py --job-title "Data Scientist" --location "Remote" --remote --headless

# Run scraper with specific parameters
scrape-custom:
	conda run -n indeed-scraper python indeed_scraper.py \
		--job-title "$(TITLE)" \
		--location "$(LOCATION)" \
		--search-radius $(RADIUS) \
		--max-pages $(PAGES) \
		--days-ago $(DAYS) \
		$(FLAGS)

# Usage example: make scrape-custom TITLE="Software Engineer" LOCATION="New York" RADIUS=50 PAGES=5 DAYS=14 FLAGS="--no-remote --no-headless"