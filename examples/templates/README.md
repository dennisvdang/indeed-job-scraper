# Job Queue Templates

These template files provide starting points for creating your own job queue configurations.

## Available Templates

- **queue_template.txt**: Template for text-based job queues
- **queue_template.json**: Template for JSON-based job queues

## How to Use

1. Copy the template to your preferred location:
   ```bash
   cp queue_template.txt my_jobs.txt
   ```

2. Edit the file with your job specifications:
   - Replace placeholder values with your actual job titles, locations, etc.
   - Add or remove jobs as needed

3. Run your job queue:
   ```bash
   indeed-scraper --queue my_jobs.txt
   ```

## Tips

- Text files are easier to edit quickly
- JSON files are better for programmatic generation and more complex configurations
- You can mix different job types and parameters within a single queue file
- Comments (lines starting with #) in text files are ignored 