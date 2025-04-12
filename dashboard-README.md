# Indeed Job Dashboard

An interactive dashboard for visualizing data from the Indeed Job Scraper.

## Features

- Interactive visualizations of job data including:
  - Salary distributions
  - Job counts by company
  - Geographic distribution with US map
  - Work setting breakdown (remote, hybrid, in-person)
  - Job type analysis
  - Word cloud of popular job titles
  - Posting date trends
- Filters for date range, work setting, job type, and location
- Data table with raw job listings
- Export capabilities

## Setup

### Prerequisites

- Python 3.8+
- Data from running the Indeed Job Scraper

### Installation

1. Install the required packages:

```bash
pip install -r requirements-dashboard.txt
```

2. Ensure you have scraped job data available in the `data/raw/` directory (CSV files).

### Running the Dashboard

Launch the dashboard with:

```bash
streamlit run src/streamlit_dashboard.py
```

This will start a local web server and automatically open the dashboard in your browser.

## Usage Tips

- **Filtering Data**: Use the sidebar filters to narrow down the job listings by date, work setting, job type, or location.
- **Comparing Salaries**: The salary analysis tab shows distribution and statistics for better comparison.
- **Exporting Data**: You can download the filtered dataset as a CSV using the button at the bottom of the Job Details tab.
- **Multiple Data Sets**: The dashboard automatically combines all CSV files in the data/raw directory, so you can view data from multiple job searches.

## Troubleshooting

- **No Data Available**: Make sure you've run the scraper and have CSV files in the `data/raw/` directory.
- **ZIP Code Display**: If ZIP codes show with apostrophes, they're still correctly stored as strings (the apostrophe is Excel's way of preserving leading zeros).
- **Map Not Showing**: Ensure the state abbreviations are standard US two-letter codes.

## Customization

To customize the dashboard:

- Edit color schemes in `src/streamlit_dashboard.py` (look for `color_continuous_scale` parameters)
- Add new visualizations by creating additional functions and adding them to the appropriate tab
- Change data loading logic in `load_multiple_datasets()` if you store your data differently 