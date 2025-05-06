#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from indeed_scraper.streamlit_dashboard import render_dashboard

if __name__ == "__main__":
    render_dashboard()