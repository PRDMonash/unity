"""
Logging utilities for OT-2 and plate reader control.

Provides timestamped logging and timing decorators.
"""

import time
from functools import wraps
from typing import Callable, Any


def log_msg(message: str) -> None:
    """
    Log a message with a timestamp.
    
    Args:
        message: The message to log.
    """
    current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print(f"[{current_time}] {message}")


def timeit(func: Callable) -> Callable:
    """
    Decorator for measuring a function's running time.
    
    Args:
        func: The function to time.
        
    Returns:
        Wrapped function that logs execution time.
    """
    @wraps(func)
    def measure_time(*args: Any, **kwargs: Any) -> Any:
        start_time = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start_time
        log_msg(f"Processing time of {func.__qualname__}(): {elapsed:.2f} seconds.")
        return result
    
    return measure_time
