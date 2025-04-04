# Indeed Job Scraper [![Project Status: WIP – Initial development is in progress, but there has not yet been a stable, usable release suitable for the public.](https://www.repostatus.org/badges/latest/wip.svg)](https://www.repostatus.org/#wip)

A Python CLI tool for scraping job listings from Indeed.com with filtering and export options.

## 🚀 Overview

This tool scrapes job listings from Indeed.com and exports the data to CSV format. It extracts the following information:

- Job title and company name
- Location and salary (when available)
- Job type (full-time, part-time, contract, etc.)
- Full job descriptions and posting dates (when using `--include-descriptions`)
- Source URLs for reference

The scraper supports filtering by job title, location, posting date, work arrangement, and job type through command-line arguments.

## 🏁 Getting Started

### Installation

**Prerequisites:** Python 3.7+, pip

```bash
# Clone the repository
git clone https://github.com/dennisvdang/Indeed-Job-Scraper.git
cd Indeed-Job-Scraper

# Create virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\activate  # On Windows
source venv/bin/activate  # On macOS/Linux

# Install the package in development mode
pip install -e .
```

This installs the `indeed-scraper` command globally in your virtual environment, allowing you to run it from anywhere.

### Alternative Installation Methods

#### Using Conda

```bash
# Clone the repository
git clone https://github.com/dennisvdang/Indeed-Job-Scraper.git
cd Indeed-Job-Scraper

# Create and activate the conda environment
conda env create -f environment.yml
conda activate indeed-scraper

# Install the package in development mode
pip install -e .
```

#### Using Docker

```bash
# Clone the repository
git clone https://github.com/dennisvdang/Indeed-Job-Scraper.git
cd Indeed-Job-Scraper

# Build the Docker image
docker build -t indeed-scraper .

# Run the container
docker run indeed-scraper conda run -n indeed-scraper indeed-scraper \
    --job-title "Data Scientist" \
    --location "New York" \
    --search-radius 25 \
    --num-pages 3 \
    --remote remote
```

## 📊 Usage

### Basic Command

```bash
indeed-scraper --job-title "Software Engineer" --location "San Francisco"
```

### All Available Options

| Parameter | Description | Example | Default |
|-----------|-------------|---------|---------|
| `--job-title` | Job title to search for (required) | "Data Analyst" | None |
| `--location` | Location to search in | "New York City" | None |
| `--search-radius` | Search radius in miles | 25 | 25 |
| `--num-pages` | Maximum number of pages to scrape | 5 | 3 |
| `--days-ago` | Filter for jobs posted in the last X days | 14 | 7 |
| `--remote` | Remote work filter | "remote", "hybrid", or "onsite" | None |
| `--job-type` | Type of job | "full-time", "part-time", "contract" | None |
| `--include-descriptions` | Include full job descriptions | | False |
| `--verbose` | Enable detailed logging | | False |
| `--output` | Custom output file path | "my_jobs.csv" | Auto-generated |

### Example Commands

Basic search:
```bash
indeed-scraper --job-title "Data Analyst" --location "New York City"
```

Advanced search:
```bash
indeed-scraper \
    --job-title "Software Engineer" \
    --location "San Francisco" \
    --search-radius 50 \
    --num-pages 5 \
    --days-ago 14 \
    --remote remote \
    --job-type "full-time" \
    --include-descriptions
```

The `--verbose` flag can be used to get detailed logging during execution:
```bash
indeed-scraper --job-title "Data Analyst" --location "Irvine, CA" --num-pages 2 --include-descriptions --verbose
```

### CAPTCHA Handling

Indeed employs CAPTCHA protection that requires human interaction. The tool opens a visible Chrome browser window and pauses when a CAPTCHA is detected:

1. When prompted, solve the CAPTCHA in the browser window
2. Ensure the page loads completely after solving the CAPTCHA
3. Return to your terminal and press Enter to continue scraping

### Output Files

Results are saved in `data/raw/` with an auto-generated filename:
```
data/raw/indeed_[job_title]_[location]_[timestamp].csv
```

Example: `data/raw/indeed_software_engineer_san_francisco_20240404_103022.csv`

## 🔧 Troubleshooting

### Common Issues

**ChromeDriver installation errors:**

- The tool currently requires Chrome version 134 (or compatible)
- Ensure you have Chrome installed and updated to a recent version
- If you encounter driver-related errors, try updating your Chrome browser
- The tool uses undetected-chromedriver which automatically handles most driver compatibility

**"No such element" errors:**

- Indeed occasionally changes their website structure, try updating to the latest version

**Scraping interruptions:**

- Indeed may rate-limit or block excessive requests; use reasonable values for `--num-pages`
- Try adding delays between runs if you perform multiple searches

## 🔮 Future Development

### Job Description Analysis

A planned enhancement is to implement an LLM pipeline in Python to extract the following topics from the scraped job descriptions:

| Topic | Examples |
|----------|----------|
| Domain/Industry | Finance, Healthcare, Ecommerce |
| Compensation | Base salary, 401K, bonuses, equity |
| Benefits | PTO, healthcare, remote work options |
| Requirements | Education level, years of experience |
| Work Arrangement | Remote, hybrid, on-site |
| Role responsibilities* | Project management, client relations, data analysis |
| Technical requirements* | Programming languages, certifications, tools |
| Technologies mentioned* | Salesforce, Python, AWS, WorkDay |

*\* These topics might be included as they are interesting from a job seeker's perspective, but are lower priority.*

## ⚠️ Disclaimer

This tool is a proof-of-concept for educational and personal use only. Use responsibly and respect Indeed.com's terms of service by:

- Adding reasonable delays between requests
- Not performing excessive scraping
- Using for personal research purposes only