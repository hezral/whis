import logging
import functools
import time

# Global flag for verbose logging
_VERBOSE_LOGGING = False

def set_verbose_logging(enabled):
    global _VERBOSE_LOGGING
    _VERBOSE_LOGGING = enabled
    if enabled:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.debug("Verbose logging enabled.")

def get_verbose_logging():
    return _VERBOSE_LOGGING

def log_function_calls(func):
    """Decorator to log function calls with arguments and execution time."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not _VERBOSE_LOGGING:
            return func(*args, **kwargs)
        
        func_name = f"{func.__module__}.{func.__qualname__}"
        # Avoid logging massive data in args
        args_repr = [repr(a)[:100] + "..." if len(repr(a)) > 100 else repr(a) for a in args]
        kwargs_repr = [f"{k}={v!r}"[:100] + "..." if len(f"{k}={v!r}") > 100 else f"{k}={v!r}" for k, v in kwargs.items()]
        signature = ", ".join(args_repr + kwargs_repr)
        
        logging.debug(f"CALL: {func_name}({signature})")
        start_time = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            end_time = time.perf_counter()
            duration = end_time - start_time
            logging.debug(f"RETURN: {func_name} -> {repr(result)[:100]}... (took {duration:.4f}s)")
            return result
        except Exception as e:
            end_time = time.perf_counter()
            duration = end_time - start_time
            logging.error(f"EXCEPTION: {func_name} -> {e} (took {duration:.4f}s)")
            raise e
    return wrapper
