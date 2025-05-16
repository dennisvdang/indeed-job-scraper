#!/usr/bin/env python3
"""Setup script for the Indeed Job Scraper package."""

import os
from setuptools import setup, find_packages

# Get the absolute path to the directory containing this file
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# Read the README.md file for long description
with open(os.path.join(ROOT_DIR, "README.md"), "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read the requirements.txt file for dependencies
with open(os.path.join(ROOT_DIR, "requirements.txt"), "r", encoding="utf-8") as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="indeed-scraper",
    version="0.2.0",
    author="Dennis",
    description="A tool for scraping, storing, and analyzing job listings from Indeed.com",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/dennisvdang/Indeed-Job-Scraper",
    project_urls={
        "Bug Tracker": "https://github.com/dennisvdang/Indeed-Job-Scraper/issues",
        "Documentation": "https://github.com/dennisvdang/Indeed-Job-Scraper",
        "Source Code": "https://github.com/dennisvdang/Indeed-Job-Scraper",
    },
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    python_requires=">=3.9",
    install_requires=requirements,
    extras_require={
        "dev": [
            "black>=23.12.0",
            "flake8>=6.1.0",
            "isort>=5.13.2",
            "mypy>=1.8.0",
            "pytest>=7.4.3",
            "pytest-cov>=4.1.0",
            "pytest-mock>=3.12.0",
        ],
        "ml": [
            "scikit-learn>=1.3.2",
            "nltk>=3.8.1",
            "spacy>=3.7.2",
            "gensim>=4.3.2",
        ],
        "viz": [
            "matplotlib>=3.7.2",
            "seaborn>=0.13.0",
            "plotly>=5.15.0",
            "wordcloud>=1.9.2",
        ],
    },
    entry_points={
        "console_scripts": [
            "indeed-scraper=indeed_scraper.cli:app",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Internet :: WWW/HTTP :: Browsers",
        "Topic :: Office/Business",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    keywords="web scraping, indeed, job search, data analysis, nlp, selenium",
) 