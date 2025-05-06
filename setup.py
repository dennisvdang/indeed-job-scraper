#!/usr/bin/env python3
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="indeed-scraper",
    version="0.2.0",
    author="Dennis",
    description="A tool for scraping job listings from Indeed.com",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/indeed-scraper",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",
    install_requires=[
        "selenium>=4.16.0",
        "undetected-chromedriver>=3.5.4",
        "pandas>=2.1.0",
        "typer>=0.9.0",
        "rich>=13.9.0",
        "pydantic>=2.6.0",
        "pydantic-settings>=2.2.0",
        "html2text>=2024.2.26",
    ],
    entry_points={
        "console_scripts": [
            "indeed-scraper=indeed_scraper.cli:app",
        ],
    },
) 