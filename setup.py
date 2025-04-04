#!/usr/bin/env python3
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="indeed-scraper",
    version="0.1.0",
    author="Dennis",
    description="A tool for scraping job listings from Indeed.com",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/indeed-scraper",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    install_requires=[
        "selenium",
        "undetected-chromedriver",
        "pandas",
    ],
    entry_points={
        "console_scripts": [
            "indeed-scraper=src.indeed_scraper:main",
        ],
    },
) 