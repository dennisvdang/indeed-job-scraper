# Indeed Job Scraper [![Project Status: WIP – Initial development is in progress, but there has not yet been a stable, usable release suitable for the public.](https://www.repostatus.org/badges/latest/wip.svg)](https://www.repostatus.org/#wip)

![Indeed Job Scraper Dashboard](images/dashboard-cover.jpg)

This repository contains a Python command-line tool to help you scrape job listings from Indeed.com, along with an interactive Streamlit dashboard for visualizing and exploring job data. It's meant as a helpful resource for research, analysis, or personal exploration of the job market.

## 📖 Overview

With this tool, you can:

- Scrape job listings from Indeed.com using simple and clear filtering options.
- Extract detailed job information, including salaries and descriptions.
- Explore and analyze the collected data using an interactive dashboard.
- Export structured data for further personal research or analysis.

<details>
<summary>📋 Extracted job data includes...</summary>

- Job titles, companies, locations, and contact information (when available).
- Salary information (normalized to annual equivalents for easier comparison).
- Work settings, such as remote, hybrid, or onsite.
- Job types such as full-time, part-time, or contract.
- Full job descriptions and posting dates.
- Direct links to original job postings.

</details>

## 🛠️ Getting Started

### Installation

To use the tool, follow these steps:

```bash
# Clone this repository
git clone https://github.com/dennisvdang/Indeed-Job-Scraper.git
cd Indeed-Job-Scraper

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

# Install required packages
pip install -r requirements.txt
```

### Basic Usage

Here's how you can perform a simple job search:

```bash
# Run a basic job search
indeed-scraper --job-title "Software Engineer" --location "San Francisco, CA"
```

## 🔍 Key Features

### 1. Search Filters

```bash
indeed-scraper \
    --job-title "Data Scientist" \
    --location "New York" \
    --work-setting remote \
    --job-type "full-time" \
    --days-ago 7
```

<summary>Filter commands</summary>

| Parameter | Description | Example |
|-----------|-------------|---------|
| `--job-title` | Job title to search for (**required**) | `"Data Analyst"` |
| `--location` | Location to search in | `"New York, NY"` |
| `--work-setting` | Work arrangement | `remote`, `hybrid`, `onsite` |
| `--job-type` | Employment type | `"full-time"`, `"contract"` |
| `--days-ago` | Filter by posting date | `1`, `3`, `7`, `14` |
| `--search-radius` | Search radius in miles | `25`, `50`, `100` |

### 2. Multiple Job Searches/Queues

You can run several job searches at once using a queue file:

```bash
indeed-scraper --queue examples/job_queues/top_cities_major_jobs.json
```

<details>

<summary>More about job queues...</summary>

You can create your own text or JSON queue files to automate multiple searches. Check the [`examples/job_queues/`](examples/job_queues/) directory for examples and [`examples/templates/`](examples/templates/) for templates you can customize.

</details>

### 3. Interactive Dashboard

To explore the scraped data interactively:

```bash
streamlit run src/streamlit_dashboard.py
```
The dashboard automatically loads your collected data from the `data/raw/` directory and helps you explore:
- Salary distributions
- Geographic locations of jobs
- Companies and job roles
- Detailed job descriptions

## 📚 Helpful Resources

- **[Examples Directory](examples/)**: Sample files and usage patterns
- **[Command Line Reference](#command-line-reference)**: All available command-line options explained.
- **[Troubleshooting](#troubleshooting)**: Solutions for common issues.

## 📊 Command Line Reference

| Parameter | Description | Example |
|-----------|-------------|---------|
| `--job-title` | Job title to search for (**required**) | `"Data Analyst"` |
| `--location` | Location to search in | `"New York, NY"` |
| `--work-setting` | Work arrangement | `remote`, `hybrid`, `onsite` |
| `--job-type` | Employment type | `"full-time"`, `"contract"` |
| `--days-ago` | Filter by posting date | `1`, `3`, `7`, `14` |
| `--search-radius` | Search radius in miles | `25`, `50`, `100` |
| `--queue` | Run multiple job searches | `examples/job_queues/remote_jobs.txt` |

<summary>Additional options...</summary>

| Parameter | Description | Possible Values | Default |
|-----------|-------------|-----------------|---------|
| `--max-pages` | Maximum pages to scrape | Any positive integer | 3 |
| `--exclude-descriptions` | Skip job descriptions | Flag | False |
| `--verbose` | Detailed logging | Flag | False |
| `--output` | Custom output file path | Valid file path | Auto-generated |
| `--keep-browser` | Keep browser open | Flag | False |

## 🔧 Troubleshooting

### CAPTCHA Handling

When prompted, solve the CAPTCHA in the browser window and press Enter to continue.

### Chrome Issues

The tool uses undetected-chromedriver with Chrome version 134 (or compatible). Ensure you have Chrome installed and updated.

## ⚠️ Disclaimer

Please use this tool responsibly. It is intended strictly for educational and personal research purposes. Always respect Indeed.com's terms of service.

## 🌱 Planned Improvements

Some areas for future improvement include:

- Adding job description analysis using language models.
- Further enhancements to the dashboard experience.

Contributions, suggestions, and feedback from everyone are warmly welcomed. Feel free to open an issue or submit a pull request if you'd like to help make the project better.

---