#!/usr/bin/env python3
"""Logging configuration for the Indeed scraper."""

import logging
import sys
import json
from typing import Dict, Any, Optional

class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as a JSON string."""
        log_record: Dict[str, Any] = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        
        if hasattr(record, "extra"):
            log_record.update(record.extra)
        
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_record)

def setup_logging(
    level: int = logging.INFO,
    use_json: bool = False,
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    Setup application logging with appropriate formatting.
    
    Args:
        level: Logging level
        use_json: Whether to use JSON formatting (for production)
        log_file: Optional path to log file
        
    Returns:
        Logger instance
    """
    logger = logging.getLogger("indeed_scraper")
    logger.setLevel(level)
    logger.handlers = []  # Remove any existing handlers
    
    # Create handlers
    handlers = []
    console_handler = logging.StreamHandler(sys.stdout)
    handlers.append(console_handler)
    
    if log_file:
        file_handler = logging.FileHandler(log_file)
        handlers.append(file_handler)
    
    # Configure formatter
    if use_json:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            "[%(levelname)s] %(asctime)s - %(name)s - %(message)s", 
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    
    # Add handlers to logger
    for handler in handlers:
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger

# Default logger instance
logger = setup_logging() 