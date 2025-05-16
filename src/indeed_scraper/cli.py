#!/usr/bin/env python3
"""Command line interface for Indeed job scraper."""

import logging
import json
import sys
import os
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from . import __version__
from .logger import setup_logging, logger
from .models import ScrapeJob, JobListing
from .scraper import run_scrape_job
from .config import config, WorkSetting, JobType
from .exporter import export_jobs_to_db
from .repository import get_repository
from .browser import setup_browser

app = typer.Typer(
    name="indeed_scraper",
    help="Tool for scraping job listings from Indeed.com",
    add_completion=False
)

console = Console()

def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"Indeed Job Scraper {__version__}")
        raise typer.Exit()

def display_job_summary(jobs: List[JobListing]) -> None:
    """
    Display a summary of the scraped jobs.
    
    Args:
        jobs: List of job listings to summarize
    """
    table = Table(title=f"[bold]Scraped {len(jobs)} Jobs[/bold]")
    
    table.add_column("Job Title", style="green")
    table.add_column("Company", style="blue")
    table.add_column("Location", style="cyan")
    table.add_column("Salary", style="yellow")
    table.add_column("Has Description", style="magenta")
    
    for job in jobs[:10]:
        table.add_row(
            job.title[:30] + "..." if len(job.title) > 30 else job.title,
            job.company[:20] + "..." if len(job.company) > 20 else job.company,
            job.location[:20] + "..." if job.location and len(job.location) > 20 else job.location or "",
            job.salary or "",
            "✓" if job.description else "✗"
        )
    
    if len(jobs) > 10:
        table.add_row("...", "...", "...", "...", "...")
    
    console.print(table)

def is_json_file(value: str) -> bool:
    """Check if the provided query string refers to a JSON file by extension."""
    return value.lower().endswith('.json')

def process_single_job(
    scrape_job: ScrapeJob,
    headless: bool,
    save_to_db: bool,
    repository: Any,
    captcha_already_solved: bool = False,
    driver: Any = None
) -> List[JobListing]:
    """
    Process a single scrape job.
    
    Args:
        scrape_job: Job configuration
        headless: Run in headless mode
        save_to_db: Save results to database
        repository: Database repository
        captcha_already_solved: Whether CAPTCHA is already solved
        driver: WebDriver instance
        
    Returns:
        List of scraped job listings
    """
    jobs = run_scrape_job(
        scrape_job=scrape_job,
        headless=headless,
        repository=repository,
        captcha_already_solved=captcha_already_solved,
        driver=driver
    )
    
    if not jobs:
        console.print("[yellow]No jobs found.[/yellow]")
        return []
    
    display_job_summary(jobs)
    
    # Export results
    if save_to_db and repository:
        saved_count = export_jobs_to_db(jobs, repository)
        console.print(f"[green]Saved {saved_count} jobs to database.[/green]")
    
    return jobs

@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", "-v", help="Show version and exit.", callback=version_callback
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-V", help="Enable verbose logging."
    ),
    json_logs: bool = typer.Option(
        False, "--json-logs", help="Output logs in JSON format (for production)."
    ),
    log_file: Optional[str] = typer.Option(
        None, "--log-file", help="Log file path (default: stdout only)"
    )
) -> None:
    """Indeed Job Scraper - Tool for scraping job listings from Indeed.com."""
    log_level = logging.DEBUG if verbose else logging.INFO
    setup_logging(level=log_level, use_json=json_logs, log_file=log_file)

@app.command("scrape")
def scrape_command(
    query: str = typer.Argument(..., help="Job title to search for or path to a JSON file with job configs"),
    location: str = typer.Option("", "--location", "-l", help="Location to search in"),
    search_radius: int = typer.Option(
        config.default_search_radius, "--radius", "-r", 
        help="Search radius in miles"
    ),
    max_pages: int = typer.Option(
        config.default_max_pages, "--pages", "-p", 
        help="Maximum number of pages to scrape"
    ),
    days_ago: int = typer.Option(
        config.default_days_ago, "--days-ago", "-d", 
        help=f"Jobs posted within days (valid options: {', '.join(map(str, config.valid_days_ago))})"
    ),
    work_setting: Optional[str] = typer.Option(
        None, "--work-setting", "-w", 
        help="Work setting (remote, hybrid, onsite)"
    ),
    job_type: Optional[str] = typer.Option(
        None, "--job-type", "-j", 
        help="Job type (full-time, part-time, contract, etc.)"
    ),
    headless: bool = typer.Option(
        False, "--headless", help="Run browser in headless mode (not recommended due to CAPTCHA issues)"
    ),
    save_to_db: bool = typer.Option(
        True, "--save/--no-save",
        help="Save results to database"
    )
) -> None:
    """
    Scrape job listings from Indeed.com. Can take either a job title or a path to a JSON file with multiple job configs.
    
    Examples:
        indeed_scraper scrape "python developer" --location "New York, NY" --pages 5
        indeed_scraper scrape jobs.json --output ./data/exports
    """
    # Validate work_setting if provided
    if work_setting and not any(ws.value == work_setting.lower() for ws in WorkSetting):
        valid_options = ", ".join(ws.value for ws in WorkSetting)
        console.print(f"[red]Invalid work setting: {work_setting}[/red]")
        console.print(f"Valid options are: {valid_options}")
        raise typer.Exit(1)
    
    # Validate job_type if provided
    if job_type and not any(jt.value == job_type.lower() for jt in JobType):
        valid_options = ", ".join(jt.value for jt in JobType)
        console.print(f"[red]Invalid job type: {job_type}[/red]")
        console.print(f"Valid options are: {valid_options}")
        raise typer.Exit(1)
    
    # Get repository
    repository = get_repository() if save_to_db else None
    
    # Check if the query is a JSON file or a job title
    if is_json_file(query):
        # Process as batch job
        try:
            with open(query, 'r') as f:
                job_configs = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            console.print(f"[red]Error loading job file: {e}[/red]")
            raise typer.Exit(1)
        
        if not isinstance(job_configs, list):
            console.print("[red]Job file must contain a list of job configurations.[/red]")
            raise typer.Exit(1)
        
        total_jobs = len(job_configs)
        console.print(f"[bold]Running {total_jobs} scrape jobs from {query}[/bold]")
        
        all_jobs = []
        
        # Flag to skip CAPTCHA check after first job
        captcha_already_solved = False
        
        # reuse one browser session for entire batch
        with setup_browser(headless=headless) as driver:
            for i, job_config in enumerate(job_configs):
                try:
                    scrape_job = ScrapeJob.from_dict(job_config)
                    console.print(f"\n[bold][{i+1}/{total_jobs}] Scraping: {scrape_job.job_title}[/bold]")
                    
                    jobs = process_single_job(
                        scrape_job=scrape_job,
                        headless=headless,
                        save_to_db=save_to_db,
                        repository=repository,
                        captcha_already_solved=captcha_already_solved,
                        driver=driver
                    )
                    
                    # Set flag after first successful job
                    if jobs and not captcha_already_solved:
                        captcha_already_solved = True
                    
                    all_jobs.extend(jobs)
                    
                except Exception as e:
                    logger.error(f"Error processing job {job_config.get('job_title', f'#{i+1}')}: {e}")
                    console.print(f"[red]Error processing job: {e}[/red]")
        
        # Final summary
        console.print(f"\n[bold green]Completed {total_jobs} scrape jobs with {len(all_jobs)} total listings.[/bold green]")
        
    else:
        # Process as single job search
        # Create ScrapeJob
        scrape_job = ScrapeJob(
            job_title=query,
            location=location,
            search_radius=search_radius,
            max_pages=max_pages,
            days_ago=days_ago,
            work_setting=work_setting.lower() if work_setting else None,
            job_type=job_type.lower() if job_type else None
        )
        
        # Display job config
        console.print(Panel.fit(
            f"[bold]Scraping jobs:[/bold]\n"
            f"Job Title: [green]{query}[/green]\n"
            f"Location: [blue]{location or 'Any'}[/blue]\n"
            f"Pages: [yellow]{max_pages}[/yellow]",
            title="Indeed Job Scraper",
            border_style="green"
        ))
        
        process_single_job(
            scrape_job=scrape_job,
            headless=headless,
            save_to_db=save_to_db,
            repository=repository
        )

# Keep the run-jobs command for backward compatibility but mark it as deprecated
@app.command("run-jobs", deprecated=True)
def run_jobs_command(
    job_file: str = typer.Argument(..., help="Path to JSON file with job configs"),
    headless: bool = typer.Option(
        False, "--headless", help="Run browser in headless mode"
    ),
    save_to_db: bool = typer.Option(
        True, "--save/--no-save",
        help="Save results to database"
    )
) -> None:
    """
    [Deprecated] Run multiple scrape jobs from a JSON configuration file.
    Use 'scrape' command with a JSON file instead.
    
    Example:
        indeed_scraper scrape jobs.json --output ./data/exports
    """
    console.print("[yellow]Warning: 'run-jobs' command is deprecated. Use 'scrape' with a JSON file instead.[/yellow]")
    
    # Forward to the scrape command
    scrape_command(
        query=job_file, 
        headless=headless, 
        save_to_db=save_to_db
    )
    
if __name__ == "__main__":
    app() 