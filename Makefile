.PHONY: setup build run clean jupyter test coverage lint scrape-job scrape-custom

# Create and setup conda environment
setup:
	conda env create -f environment.yml
	conda activate indeed-scraper

# Build Docker image
build:
	docker build -t indeed-scraper .

# Run scraper in Docker with default settings
run:
	docker run -it --rm indeed-scraper

# Run with interactive mode (for CAPTCHA solving)
run-interactive:
	docker run -it --rm \
		-e DISPLAY=${DISPLAY} \
		-v /tmp/.X11-unix:/tmp/.X11-unix \
		--net=host \
		indeed-scraper

# Run Jupyter notebook
jupyter:
	conda run -n indeed-scraper jupyter notebook

# Run tests
test:
	conda run -n indeed-scraper pytest

# Run tests with coverage
coverage:
	conda run -n indeed-scraper pytest --cov=indeed_scraper tests/ --cov-report=term-missing

# Run linting and type checking
lint:
	conda run -n indeed-scraper flake8 indeed_scraper.py tests/
	conda run -n indeed-scraper black --check indeed_scraper.py tests/
	conda run -n indeed-scraper isort --check-only indeed_scraper.py tests/
	conda run -n indeed-scraper mypy indeed_scraper.py

# Format code
format:
	conda run -n indeed-scraper black indeed_scraper.py tests/
	conda run -n indeed-scraper isort indeed_scraper.py tests/

# Clean up
clean:
	conda env remove -n indeed-scraper
	docker rmi indeed-scraper || true
	rm -rf __pycache__
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov

# Run scraper locally with preset job
scrape-job:
	conda run -n indeed-scraper python indeed_scraper.py \
		--job-title "Software Engineer" \
		--location "Remote" \
		--work-arrangement remote \
		--max-pages 3 \
		--days-ago 7

# Run scraper with custom parameters (for use with make command)
scrape-custom:
	conda run -n indeed-scraper python indeed_scraper.py \
		--job-title "$(TITLE)" \
		--location "$(LOCATION)" \
		$(if $(RADIUS),--search-radius $(RADIUS),) \
		$(if $(PAGES),--max-pages $(PAGES),) \
		$(if $(DAYS),--days-ago $(DAYS),) \
		$(if $(WORK),--work-arrangement $(WORK),) \
		$(if $(DEBUG),--debug,)

# Usage examples:
# Basic:
#   make scrape-job
# Custom:
#   make scrape-custom TITLE="Data Scientist" LOCATION="San Francisco" PAGES=5 WORK=hybrid DEBUG=1
# Debug mode:
#   make scrape-custom TITLE="Software Engineer" DEBUG=1