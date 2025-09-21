#!/usr/bin/env python3
"""
MCP server configuration file
"""

import os
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

# Setup logging
logger = logging.getLogger(__name__)

@dataclass
class ServerConfig:
    """Server configuration class"""
    server_name: str = "devops-build-server"
    server_version: str = "1.0.0"
    all_the_things_root: str = "C:/Users/l/Desktop/Proj_3"
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Build configuration
    build_config_path: str = "config/workflows.yaml"
    
    # Timeout configuration
    build_timeout: int = 1800  # seconds
    
    @classmethod
    def from_env(cls) -> "ServerConfig":
        """Create configuration from environment variables"""
        return cls(
            server_name=os.getenv("MCP_SERVER_NAME", "devops-build-server"),
            server_version=os.getenv("MCP_SERVER_VERSION", "1.0.0"),
            all_the_things_root=os.getenv("ALL_THE_THINGS_ROOT", "C:/Users/l/Desktop/Proj_3"),
            log_level=os.getenv("MCP_LOG_LEVEL", "INFO"),
            log_format=os.getenv("MCP_LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
            build_config_path=os.getenv("BUILD_CONFIG_PATH", "config/workflows.yaml"),
            build_timeout=int(os.getenv("BUILD_TIMEOUT", "1800"))
        )
    
    def validate(self) -> None:
        """Validate configuration validity"""
        # Check necessary paths (may not exist in dev environment, only log warnings)
        if not Path(self.all_the_things_root).exists():
            logger.warning(f"ALL_THE_THINGS_ROOT path does not exist: {self.all_the_things_root}")
            logger.warning("This might be a development environment, some features may not be available")
        
        # Check build config file (may not exist in dev environment, only log warnings)
        if not Path(self.build_config_path).exists():
            logger.warning(f"Build config file does not exist: {self.build_config_path}")
            logger.warning("This might be a development environment, some features may not be available")
        
        # Validate log level
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level not in valid_log_levels:
            raise ValueError(f"Invalid log level: {self.log_level}, valid values: {valid_log_levels}")
        
        # Validate timeout value
        if self.build_timeout <= 0:
            raise ValueError("Build timeout must be greater than 0")

# Default configuration instance
config = ServerConfig.from_env()

def get_config() -> ServerConfig:
    """Get current configuration"""
    return config

def reload_config() -> ServerConfig:
    """Reload configuration"""
    global config
    config = ServerConfig.from_env()
    config.validate()
    return config