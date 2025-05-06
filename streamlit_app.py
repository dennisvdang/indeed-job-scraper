import sys
from pathlib import Path

# Import dashboard code from the new package structure
from src.indeed_scraper.streamlit_dashboard import render_dashboard

# Call the main function
render_dashboard()