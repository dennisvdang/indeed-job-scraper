# Indeed Job Scraper [![Project Status: WIP – Initial development is in progress, but there has not yet been a stable, usable release suitable for the public.](https://www.repostatus.org/badges/latest/wip.svg)](https://www.repostatus.org/#wip)

![Indeed Job Scraper Dashboard](images/dashboard-cover.jpg)

A Python CLI tool for scraping job listings from Indeed.com with an interactive Streamlit dashboard for data visualization.

## 🚀 Overview

This repo contains python tools that do the following:
- Scrape job listings from Indeed.com with customizable filters
- Extract job details including salaries and job descriptions
- Analyze the job market with an interactive dashboard
- Export structured data for further analysis

<details>
<summary>📋 Data extracted includes...</summary>

- Job titles, companies, locations, and contact information
- Detailed salary data (normalized to yearly equivalents)
- Work settings (remote, hybrid, in-person) and job types
- Full job descriptions and posting dates
- Direct links to job listings

</details>

## 🏁 Quick Start

### Installation

```bash
# Clone and setup
git clone https://github.com/dennisvdang/Indeed-Job-Scraper.git
cd Indeed-Job-Scraper

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate  # On Windows
source venv/bin/activate  # On macOS/Linux

# Install
pip install -r requirements.txt

```

### Basic Usage

```bash
# Run a basic job search
indeed-scraper --job-title "Software Engineer" --location "San Francisco"

# View your results in the dashboard
streamlit run src/streamlit_dashboard.py
```

## 🔍 Key Features

### 1. Flexible Job Filtering

```bash
indeed-scraper \
    --job-title "Data Scientist" \
    --location "New York" \
    --work-setting remote \
    --job-type "full-time" \
    --days-ago 7
```

### 2. Multiple Job Queues

Run multiple job searches sequentially:

```bash
indeed-scraper --queue examples/job_queues/software_and_data_jobs.txt
```

<details>
<summary>Learn more about job queues...</summary>

Create text or JSON configuration files with multiple search parameters. See the [`examples/job_queues/`](examples/job_queues/) directory for sample files and [`examples/templates/`](examples/templates/) for templates.

</details>

### 3. Interactive Dashboard

Visualize and analyze your job data:

```bash
streamlit run src/streamlit_dashboard.py
```

The dashboard automatically loads all scraped job data from the `data/raw/` directory and provides:
- Salary distribution analysis
- Geographic job distribution
- Company and role breakdowns
- Detailed job descriptions

## 📚 Documentation

- **[Examples Directory](examples/)**: Sample files and usage patterns
- **[Command Line Reference](#command-line-reference)**: All available CLI options
- **[Troubleshooting](#troubleshooting)**: Common issues and solutions

## 📊 Command Line Reference

| Parameter | Description | Example |
|-----------|-------------|---------|
| `--job-title` | Job title to search for (**required**) | `"Data Analyst"` |
| `--location` | Location to search in | `"New York, NY"` |
| `--work-setting` | Work arrangement | `remote`, `hybrid`, `onsite` |
| `--job-type` | Employment type | `"full-time"`, `"contract"` |
| `--days-ago` | Filter by posting date | `1`, `3`, `7`, `14` |
| `--queue` | Run multiple job searches | `examples/job_queues/remote_jobs.txt` |

<details>
<summary>Show all options...</summary>

| Parameter | Description | Possible Values | Default |
|-----------|-------------|-----------------|---------|
| `--search-radius` | Search radius in miles | Any positive integer | 25 |
| `--num-pages` | Maximum pages to scrape | Any positive integer | 3 |
| `--exclude-descriptions` | Skip job descriptions | Flag | False |
| `--verbose` | Detailed logging | Flag | False |
| `--output` | Custom output file path | Valid file path | Auto-generated |
| `--keep-browser` | Keep browser open | Flag | False |

</details>

## 🔧 Troubleshooting

### CAPTCHA Handling

When prompted, solve the CAPTCHA in the browser window and press Enter to continue.

### Chrome Issues

The tool uses undetected-chromedriver with Chrome version 134 (or compatible). Ensure you have Chrome installed and updated.

## ⚠️ Disclaimer

This tool is for educational and personal use only. Use responsibly and respect Indeed.com's terms of service by limiting requests and using for personal research purposes only.

## 🔮 Future Development

- Job description analysis using LLM pipeline
- Dashboard improvements

---