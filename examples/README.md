# Indeed Job Scraper Examples

This directory contains example files and configurations for the Indeed Job Scraper.

## Directory Structure

- **job_queues/**: Ready-to-use example job queue files
- **templates/**: Template files you can copy and customize

## Example Use Cases

1. **Searching for the same job in multiple locations**:
   ```bash
   indeed-scraper --queue examples/job_queues/software_and_data_jobs.txt
   ```

2. **Searching for remote-only jobs across different roles**:
   ```bash
   indeed-scraper --queue examples/job_queues/remote_jobs.txt
   ```

3. **Using the JSON format for more complex configurations**:
   ```bash
   indeed-scraper --queue examples/job_queues/multi_location_search.json
   ```

## Creating Your Own Job Queues

See the `templates/` directory for starting points to create your own job queues:

1. Copy a template
2. Edit with your search parameters
3. Run with `--queue`

For more details on job queue options, see the main README.md. 