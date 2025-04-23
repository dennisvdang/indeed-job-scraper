import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.append(str(src_path))

# Import dashboard code
from streamlit_dashboard import render_dashboard

# Call the main function
render_dashboard()