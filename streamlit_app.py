#!/usr/bin/env python3
"""
Streamlit application entry point for the Indeed Job Scraper.
Ensures proper module import paths in both local and cloud environments.
"""

import os
import sys
from pathlib import Path

# Get the directory containing this file
APP_DIR = Path(__file__).parent.absolute()

# Add the src directory to the Python path if it exists
SRC_DIR = APP_DIR / "src"
if SRC_DIR.exists():
    sys.path.insert(0, str(SRC_DIR))
    print(f"Added {SRC_DIR} to Python path")

# For Streamlit Cloud - check if we're in the /mount/src directory
STREAMLIT_MOUNT = Path("/mount/src")
if STREAMLIT_MOUNT.exists():
    mount_src = STREAMLIT_MOUNT / "indeed-job-scraper" / "src"
    if mount_src.exists() and str(mount_src) not in sys.path:
        sys.path.insert(0, str(mount_src))
        print(f"Added Streamlit Cloud path {mount_src} to Python path")

# Print Python path for debugging
print(f"Python path: {sys.path}")

try:
    from indeed_scraper.streamlit_dashboard import render_dashboard
    
    if __name__ == "__main__":
        render_dashboard()
except ImportError as e:
    import streamlit as st
    st.error(f"Error importing modules: {e}")
    st.write("Python path:", sys.path)
    st.write("Current directory:", os.getcwd())
    st.write("Files in current directory:", os.listdir())
    if SRC_DIR.exists():
        st.write(f"Files in {SRC_DIR}:", os.listdir(SRC_DIR))