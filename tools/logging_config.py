#!/usr/bin/env python3
"""
Shared logging configuration for tools modules
Ensures all tools modules log to the same file
"""

import logging
import sys
from pathlib import Path

def setup_tools_logging(name: str):
    """Configure tool module logging, output to file and stderr"""
    # Create log handlers - use file and stderr, avoid stdout conflicts
    log_file_path = Path(__file__).parent.parent / f"mcp_server_{name}.log"
    
    handlers = [
        logging.StreamHandler(sys.stderr),  # Use stderr instead of stdout
        logging.FileHandler(log_file_path, encoding='utf-8')  # File logging
    ]
    
    # Configure root logger
    root_logger = logging.getLogger()
    
    # Avoid duplicate handler addition
    if not any(isinstance(h, logging.FileHandler) and str(h.baseFilename).endswith(f"mcp_server_{name}.log") for h in root_logger.handlers):
        for handler in handlers:
            handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            root_logger.addHandler(handler)
        
        # Set log level
        root_logger.setLevel(logging.INFO)

def get_logger(name: str):
    """Get configured logger"""
    setup_tools_logging(name)
    return logging.getLogger(name)