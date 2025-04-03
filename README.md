# Indeed Job Scraper & AI Analysis [![Project Status: WIP – Initial development is in progress, but there has not yet been a stable, usable release suitable for the public.](https://www.repostatus.org/badges/latest/wip.svg)](https://www.repostatus.org/#wip)

A Python-based data pipeline that combines web scraping and AI analysis to extract insights from job listings on Indeed.com.

Setup instructions can be found in the [Getting Started](#-getting-started) section below.

## 🚀 Overview

### Indeed Job Scraper

The data scraping pipeline ([indeed_scraper.py](./indeed_scraper.py)) extracts the following information:

- Job title
- Company name
- Location
- Salary information
- Indeed URL link
- Complete job descriptions

### 🔍 Job Description Analysis

This component is currently under development. The goal is to implement an LLM pipeline in Python to extract the following topics from the scraped job descriptions:

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

## 🏁 Getting Started

### Installation Options

#### Using pip and venv (Recommended)

**Prerequisites:** Python 3.11+, pip

```bash
# Clone the repository
git clone https://github.com/dennisvdang/Indeed-Job-Scraper.git
cd Indeed-Job-Scraper

# Create virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\activate  # On Unix/macOS: source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### Using Conda

**Prerequisites:** Python 3.11+, Conda

```bash
# Clone the repository
git clone https://github.com/dennisvdang/Indeed-Job-Scraper.git
cd Indeed-Job-Scraper

# Create and activate the conda environment
conda env create -f environment.yml
conda activate indeed-scraper

# To deactivate the environment when you're done:
conda deactivate
```

#### Using Docker

**Prerequisites:** Docker

```bash
# Clone the repository
git clone https://github.com/dennisvdang/Indeed-Job-Scraper.git
cd Indeed-Job-Scraper

# Build the Docker image
docker build -t indeed-scraper .

# Run the container
docker run indeed-scraper conda run -n indeed-scraper python indeed_scraper.py \
    --job-title "Data Scientist" \
    --location "New York" \
    --search-radius 25 \
    --max-pages 3 \
    --work-arrangement "remote"
```

## 📊 Usage

### Command-Line Arguments

| Parameter | Description | Example | Default |
|-----------|-------------|---------|---------|
| `--job-title` | Job title to search for | "Data Analyst" | None |
| `--location` | Location to search in | "New York City" | None |
| `--search-radius` | Search radius in miles | 25 | 25 (None if no location) |
| `--max-pages` | Maximum number of pages to scrape | 5 | 3 |
| `--days-ago` | Filter for jobs posted within this many days | 14 | 7 |
| `--work-arrangement` | Work arrangement preference | "remote", "hybrid", or "any" | "any" |
| `--dry-run` | Run without saving output file | `--dry-run` | False |

#### CAPTCHA Handling

Due to Indeed's CAPTCHA system, the scraper runs with the Chrome browser visible. When a CAPTCHA appears (usually a simple checkbox on startup):

1. Click the checkbox or solve any additional puzzles that appear
2. Wait for the page to fully load after solving
3. Press Enter in the terminal to continue

The script will only continue the scraping process once you've hit Enter in the command line.

#### Example Usage

Basic example:
```bash
python indeed_scraper.py --job-title "Data Analyst" --location "New York City"
```

Advanced example (all options):
```bash
python indeed_scraper.py \
    --job-title "Software Engineer" \
    --location "San Francisco" \
    --search-radius 50 \
    --max-pages 5 \
    --days-ago 14 \
    --work-arrangement "remote"
```

Testing without saving (shows GUI but doesn't save file):
```bash
python indeed_scraper.py --job-title "Data Analyst" --location "New York City" --max-pages 1 --dry-run
```

### Data Organization

The scraper organizes data in the following structure:
```
data/
├── raw/          # Raw CSV files from Indeed scraping
└── processed/    # For future processed/analyzed data
```

Output files are automatically saved in `data/raw/` with the naming format:
`indeed_[job_title]_[location]_[timestamp].csv`

For example:
`data/raw/indeed_data_analyst_new_york_20240401_153022.csv`

## ⚠️ Disclaimer

This tool is a proof-of-concept intended for research and personal use only. Please respect Indeed.com's terms of service and use responsibly with appropriate delays between requests.