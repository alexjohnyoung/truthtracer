"""
Centralized logging utility for the application.

This module provides a consistent way to configure loggers across the application.
"""

import logging


def get_logger(name: str, level: str = 'INFO') -> logging.Logger:
    """
    Create and configure a logger with consistent settings.
    
    Args:
        name: The name of the logger (typically the module name)
        level: The logging level ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
        
    Returns:
        A configured logger instance
    """
    level_map = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    log_level = level_map.get(level.upper(), logging.INFO)
    
    logger = logging.getLogger(name)
    logger.propagate = False 
    logger.setLevel(log_level)
    
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    
    return logger 