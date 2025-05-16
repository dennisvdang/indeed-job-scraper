#!/usr/bin/env python3
"""Logging configuration for the Indeed scraper."""

import logging
import sys
import json
import os
import time
import traceback
from contextlib import contextmanager
from datetime import datetime
from functools import wraps
from typing import Dict, Any, Optional, Callable, Generator, TypeVar, cast, List, Union

# Type variables for generics
T = TypeVar('T')
F = TypeVar('F', bound=Callable[..., Any])


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def __init__(self, include_timestamp: bool = True) -> None:
        """
        Initialize JSON formatter.
        
        Args:
            include_timestamp: Whether to include timestamp in logs
        """
        super().__init__()
        self.include_timestamp = include_timestamp
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record as a JSON string.
        
        Args:
            record: Log record to format
            
        Returns:
            JSON string representation of the log record
        """
        log_record: Dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add timestamp if configured
        if self.include_timestamp:
            log_record["timestamp"] = self.formatTime(record, "%Y-%m-%dT%H:%M:%S.%fZ")
        
        # Add thread information for concurrent operations
        log_record["thread"] = {
            "id": record.thread,
            "name": record.threadName
        }
        
        # Add any extra contextual information
        if hasattr(record, "extra") and record.extra:
            log_record.update(record.extra)
        
        # Add exception information if present
        if record.exc_info:
            exception_info = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info)
            }
            log_record["exception"] = exception_info
            
        return json.dumps(log_record, default=str)


class ContextAdapter(logging.LoggerAdapter):
    """Logger adapter that allows adding context to log messages."""
    
    def __init__(self, logger: logging.Logger, extra: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the adapter with a logger and optional extra context.
        
        Args:
            logger: Logger to adapt
            extra: Extra context to add to all log messages
        """
        super().__init__(logger, extra or {})
    
    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """
        Process the log message and kwargs to include context.
        
        Args:
            msg: Log message
            kwargs: Keyword arguments for logging
            
        Returns:
            Tuple of (modified message, modified kwargs)
        """
        # Merge any existing 'extra' in kwargs with our self.extra
        kwargs_extra = kwargs.get('extra', {})
        kwargs_extra.update(self.extra)
        kwargs['extra'] = kwargs_extra
        return msg, kwargs
    
    def with_context(self, **context: Any) -> 'ContextAdapter':
        """
        Create a new adapter with additional context.
        
        Args:
            **context: Additional context to add
            
        Returns:
            New adapter with merged context
        """
        new_extra = self.extra.copy()
        new_extra.update(context)
        return ContextAdapter(self.logger, new_extra)


def setup_logging(
    level: int = logging.INFO,
    use_json: bool = False,
    log_file: Optional[str] = None,
    log_dir: Optional[str] = None,
    app_name: str = "indeed_scraper",
    include_timestamp: bool = True
) -> ContextAdapter:
    """
    Setup application logging with appropriate formatting.
    
    Args:
        level: Logging level
        use_json: Whether to use JSON formatting (for production)
        log_file: Optional path to log file
        log_dir: Optional directory for log files (auto-generates filename)
        app_name: Application name for logger
        include_timestamp: Whether to include timestamp in logs
        
    Returns:
        Logger adapter instance with context support
    """
    # Create logger
    logger = logging.getLogger(app_name)
    logger.setLevel(level)
    
    # Remove any existing handlers
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)
    
    # Create handlers
    handlers: List[logging.Handler] = []
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    handlers.append(console_handler)
    
    # File handler (if requested)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        handlers.append(file_handler)
    elif log_dir:
        # Auto-generate timestamped filename in the specified directory
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = os.path.join(log_dir, f"{app_name}_{timestamp}.log")
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(level)
        handlers.append(file_handler)
    
    # Configure formatter
    if use_json:
        formatter = JsonFormatter(include_timestamp=include_timestamp)
    else:
        formatter = logging.Formatter(
            "[%(levelname)s] %(asctime)s - %(name)s - %(message)s", 
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    
    # Add handlers to logger
    for handler in handlers:
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    # Create and return context adapter
    return ContextAdapter(logger, {"app": app_name})


@contextmanager
def log_duration(logger: ContextAdapter, operation: str) -> Generator[None, None, None]:
    """
    Context manager to log the duration of an operation.
    
    Args:
        logger: Logger to use
        operation: Name of the operation being timed
        
    Usage:
        with log_duration(logger, "database query"):
            results = db.execute_query()
    """
    start_time = time.time()
    logger.info(f"Starting {operation}")
    try:
        yield
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        logger.error(
            f"Error in {operation} after {duration:.2f}s",
            extra={"duration": duration, "error": str(e)}
        )
        raise
    else:
        end_time = time.time()
        duration = end_time - start_time
        logger.info(
            f"Completed {operation} in {duration:.2f}s",
            extra={"duration": duration}
        )


def log_call(logger: Optional[ContextAdapter] = None) -> Callable[[F], F]:
    """
    Decorator to log function calls, arguments, return values and exceptions.
    
    Args:
        logger: Logger to use (uses global logger if None)
        
    Returns:
        Decorated function
        
    Usage:
        @log_call()
        def my_function(arg1, arg2):
            return arg1 + arg2
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Use provided logger or global one
            nonlocal logger
            log = logger or cast(ContextAdapter, globals()['logger'])
            
            # Create context with function info
            func_logger = log.with_context(
                function=func.__name__,
                module=func.__module__
            )
            
            # Log call with arguments (sanitizing sensitive data)
            call_args = ", ".join([
                repr(arg) if not str(arg).lower().startswith(('pass', 'secret', 'token', 'key')) 
                else "***REDACTED***" 
                for arg in args
            ])
            call_kwargs = ", ".join([
                f"{k}={repr(v)}" if not k.lower().startswith(('pass', 'secret', 'token', 'key'))
                else f"{k}=***REDACTED***" 
                for k, v in kwargs.items()
            ])
            call_repr = f"{call_args}{', ' if call_args and call_kwargs else ''}{call_kwargs}"
            
            func_logger.debug(f"Called {func.__name__}({call_repr})")
            
            # Execute function with timing
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Log return value (if not too large)
                result_repr = repr(result)
                if len(result_repr) > 1000:
                    result_repr = f"{result_repr[:1000]}... [truncated]"
                    
                func_logger.debug(
                    f"{func.__name__} returned: {result_repr}",
                    extra={"duration": duration}
                )
                return result
            except Exception as e:
                duration = time.time() - start_time
                func_logger.error(
                    f"{func.__name__} raised {type(e).__name__}: {str(e)}",
                    extra={
                        "duration": duration,
                        "exception_type": type(e).__name__,
                        "exception_message": str(e),
                        "traceback": traceback.format_exc()
                    }
                )
                raise
        return cast(F, wrapper)
    return decorator


# Default logger instance
logger = setup_logging() 