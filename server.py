#!/usr/bin/env python3
"""
MCP Server - DevOps Workflow Automation
Handles alerts component disable and build workflows
"""

import asyncio
import logging
import os
from typing import List, Dict, Optional, Any
from pathlib import Path
from dataclasses import dataclass
from contextlib import asynccontextmanager

# MCP related imports
from mcp.server.fastmcp import FastMCP, Context
from mcp.server.session import ServerSession
from mcp.types import TextContent

# Local tool imports
from tools.k8s_builder import K8sBuilder

# Import configuration
from config import get_config, ServerConfig

# Get configuration
config = get_config()

# Setup logging - avoid conflicts with MCP stdio communication, only write to local files
def setup_mcp_logging():
    """Configure MCP server logging, output only to files and stderr"""
    import sys
    
    # Create log handlers - only use files and stderr, don't send to MCP client
    handlers = [
        logging.StreamHandler(sys.stderr),  # Use stderr instead of stdout
        logging.FileHandler('mcp_server.log', encoding='utf-8')  # File logging
    ]
    
    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format=config.log_format,
        handlers=handlers,
        force=True  # Force reconfiguration
    )

# Configure logging
setup_mcp_logging()
logger = logging.getLogger(__name__)

# Application context class
@dataclass
class AppContext:
    """Application context containing all necessary dependencies"""
    all_the_things_root: str

# Lifecycle manager
@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AppContext:
    """Manage application lifecycle"""
    try:
        logger.info("Starting MCP server initialization...")
        
        # Validate configuration
        logger.info("Validating configuration...")
        config.validate()
        logger.info(f"Configuration validation passed, using path: {config.all_the_things_root}")
        
        # Initialize components with error handling
        logger.info("Initializing application context...")
        
        context = AppContext(
            all_the_things_root=config.all_the_things_root
        )
        
        logger.info(f"MCP server {config.server_name} v{config.server_version} initialization completed")
        yield context
        
    except Exception as e:
        logger.error(f"Server initialization failed: {e}")
        import traceback
        logger.error(f"Detailed error information: {traceback.format_exc()}")
        raise
    finally:
        logger.info("MCP server shutdown")

# Create FastMCP server instance with lifecycle
server = FastMCP(config.server_name, lifespan=app_lifespan)

# Structured output models

@dataclass
class K8sBuildResult:
    """K8s build result"""
    success: bool
    dt: str
    build_dir: Optional[str] = None
    validation: Optional[bool] = None
    message: Optional[str] = None
    error: Optional[str] = None
    stdout: Optional[str] = None

@dataclass
class HelmBuildResult:
    """Helm build result"""
    success: bool
    dt: str
    region: Optional[str] = None
    env_name: Optional[str] = None
    cluster_name: Optional[str] = None
    build_dir: Optional[str] = None
    schema_files: Optional[List[str]] = None
    validation: Optional[bool] = None
    message: Optional[str] = None
    error: Optional[str] = None
    stdout: Optional[str] = None

@dataclass
class BatchBuildResult:
    """Batch build result"""
    success: bool
    total_dts: int
    successful_dts: List[str]
    failed_dts: List[str]
    success_count: int
    failure_count: int
    build_details: List[K8sBuildResult]
    message: str
    error: Optional[str] = None

@dataclass
class BatchHelmBuildResult:
    """Batch helm build result"""
    success: bool
    total_dts: int
    successful_dts: List[str]
    failed_dts: List[str]
    success_count: int
    failure_count: int
    region: str
    env_name: str
    cluster_name: str
    build_details: List[HelmBuildResult]
    message: str
    error: Optional[str] = None





@server.tool()
async def build_deployables(
    dt_list: List[str],
    att_root: Optional[str] = None,
    max_concurrent: int = 3,
    ctx: Context[ServerSession, AppContext] = None
) -> BatchBuildResult:
    """
    Concurrent batch build of multiple mustache deployables
    
    Parameters:
    - dt_list: List of DT names to build
    - att_root: all-the-things root path, optional
    - max_concurrent: Maximum concurrent number, default is 3
    """
    try:
        if ctx is None:
            return BatchBuildResult(
                success=False,
                total_dts=len(dt_list) if dt_list else 0,
                successful_dts=[],
                failed_dts=dt_list if dt_list else [],
                success_count=0,
                failure_count=len(dt_list) if dt_list else 0,
                build_details=[],
                message="Invalid context",
                error="Invalid context"
            )
        
        if not dt_list:
            return BatchBuildResult(
                success=True,
                total_dts=0,
                successful_dts=[],
                failed_dts=[],
                success_count=0,
                failure_count=0,
                build_details=[],
                message="No DT list provided for building"
            )
        
        logger.info(f"Starting batch build of {len(dt_list)} DTs: {dt_list}")
        
        # Get application context
        app_ctx = ctx.request_context.lifespan_context
        
        # Use configured path or provided path
        build_root = att_root or app_ctx.all_the_things_root
        
        # Create K8s builder
        k8s_builder = K8sBuilder(build_root)
        
        await ctx.info(f"Running concurrent batch build of {len(dt_list)} DTs (max concurrent: {max_concurrent})...")
        
        # Execute concurrent batch build
        build_result = await k8s_builder.build_multiple_deployables(dt_list, max_concurrent)
        
        # Convert result format
        batch_result = BatchBuildResult(
            success=build_result["success"],
            total_dts=build_result["total_dts"],
            successful_dts=build_result["successful_dts"],
            failed_dts=build_result["failed_dts"],
            success_count=build_result["success_count"],
            failure_count=build_result["failure_count"],
            build_details=[
                K8sBuildResult(
                    success=detail["success"],
                    dt=detail["dt"],
                    build_dir=detail.get("build_dir"),
                    validation=detail.get("validation"),
                    message=detail.get("message"),
                    error=detail.get("error"),
                    stdout=detail.get("stdout")
                ) for detail in build_result["build_details"]
            ],
            message=build_result["message"]
        )
        
        # Report progress and results
        if batch_result.success:
            await ctx.info(f"Batch build completed successfully! All {batch_result.success_count} DTs built successfully")
        elif batch_result.success_count == 0:
            await ctx.error(f"Batch build failed! All {batch_result.failure_count} DTs failed to build")
        else:
            await ctx.info(f"Batch build partially successful! {batch_result.success_count} successful, {batch_result.failure_count} failed")
        
        # Detailed report of failed DTs
        if batch_result.failed_dts:
            failed_details = []
            for detail in batch_result.build_details:
                if not detail.success:
                    failed_details.append(f"  - {detail.dt}: {detail.error}")
            
            if failed_details:
                await ctx.error("Failed DT details:\n" + "\n".join(failed_details))
        
        return batch_result
        
    except Exception as e:
        error_msg = f"Batch build DT failed: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        
        return BatchBuildResult(
            success=False,
            total_dts=len(dt_list) if dt_list else 0,
            successful_dts=[],
            failed_dts=dt_list if dt_list else [],
            success_count=0,
            failure_count=len(dt_list) if dt_list else 0,
            build_details=[],
            message=error_msg,
            error=error_msg
        )


@server.tool()
async def build_helm_deployables(
    dt_list: List[str],
    region: str,
    env_name: str,
    cluster_name: str,
    att_root: Optional[str] = None,
    max_concurrent: int = 3,
    ctx: Context[ServerSession, AppContext] = None
) -> BatchHelmBuildResult:
    """
    Concurrent batch build of multiple helm deployables
    
    Parameters:
    - dt_list: List of DT names to build
    - region: Target region (e.g., us-east-1)
    - env_name: Environment name (e.g., stage-live)
    - cluster_name: Cluster name (e.g., main)
    - att_root: all-the-things root path, optional
    - max_concurrent: Maximum concurrent number, default is 3
    """
    try:
        # Get ATT_ROOT path
        if att_root is None:
            att_root = os.environ.get('ALL_THE_THINGS_ROOT')
            if att_root is None:
                raise ValueError("ATT_ROOT environment variable is not set and att_root parameter is not provided")
        
        # Validate path
        build_root = Path(att_root)
        if not build_root.exists():
            raise FileNotFoundError(f"ATT_ROOT directory does not exist: {att_root}")
        
        await ctx.info(f"Starting helm build for {len(dt_list)} DTs: {dt_list}")
        await ctx.info(f"Target: {region}-{env_name}-{cluster_name}")
        await ctx.info(f"Using ATT_ROOT: {att_root}")
        await ctx.info(f"Max concurrent builds: {max_concurrent}")
        
        # Create K8sBuilder instance
        k8s_builder = K8sBuilder(build_root)
        
        await ctx.info(f"Running concurrent batch helm build of {len(dt_list)} DTs (max concurrent: {max_concurrent})...")
        
        # Execute concurrent batch helm build
        build_result = await k8s_builder.build_multiple_helm_deployables(dt_list, region, env_name, cluster_name, max_concurrent)
        
        # Convert result format
        batch_result = BatchHelmBuildResult(
            success=build_result["success"],
            total_dts=build_result["total_dts"],
            successful_dts=build_result["successful_dts"],
            failed_dts=build_result["failed_dts"],
            success_count=build_result["success_count"],
            failure_count=build_result["failure_count"],
            region=region,
            env_name=env_name,
            cluster_name=cluster_name,
            build_details=[
                HelmBuildResult(
                    success=detail["success"],
                    dt=detail["dt"],
                    region=detail.get("region"),
                    env_name=detail.get("env_name"),
                    cluster_name=detail.get("cluster_name"),
                    build_dir=detail.get("build_dir"),
                    schema_files=detail.get("schema_files"),
                    validation=detail.get("validation"),
                    message=detail.get("message"),
                    error=detail.get("error"),
                    stdout=detail.get("stdout")
                ) for detail in build_result["build_details"]
            ],
            message=build_result["message"]
        )
        
        # Report progress and results
        if batch_result.success:
            await ctx.info(f"Batch helm build completed successfully! All {batch_result.success_count} DTs built successfully")
            await ctx.info(f"Target: {region}-{env_name}-{cluster_name}")
        elif batch_result.success_count == 0:
            await ctx.error(f"Batch helm build failed! All {batch_result.failure_count} DTs failed to build")
        else:
            await ctx.info(f"Batch helm build partially successful! {batch_result.success_count} successful, {batch_result.failure_count} failed")
        
        # Detailed report of failed DTs
        if batch_result.failed_dts:
            failed_details = []
            for detail in batch_result.build_details:
                if not detail.success:
                    failed_details.append(f"  - {detail.dt}: {detail.error}")
            
            if failed_details:
                await ctx.error("Failed helm DT details:\n" + "\n".join(failed_details))
        
        # Report schema files
        if batch_result.success and batch_result.build_details:
            schema_summary = []
            for detail in batch_result.build_details:
                if detail.success and detail.schema_files:
                    schema_summary.append(f"  - {detail.dt}: {len(detail.schema_files)} schema files")
            
            if schema_summary:
                await ctx.info("Schema files generated:\n" + "\n".join(schema_summary))
        
        return batch_result
        
    except Exception as e:
        error_msg = f"Batch helm build DT failed: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        
        return BatchHelmBuildResult(
            success=False,
            total_dts=len(dt_list) if dt_list else 0,
            successful_dts=[],
            failed_dts=dt_list if dt_list else [],
            success_count=0,
            failure_count=len(dt_list) if dt_list else 0,
            region=region,
            env_name=env_name,
            cluster_name=cluster_name,
            build_details=[],
            message=error_msg,
            error=error_msg
        )






# Resource functions
@server.resource("status://server")
async def get_server_status() -> str:
    """Get server status information"""
    return f"""MCP DevOps Build Server Status:
- Server Name: {config.server_name}
- Version: {config.server_version}
- Status: Running
- Config Path: {config.all_the_things_root}
- Available Tools: 2
- Available Resources: 1
- Supported Features: Mustache build, Helm build"""

# Prompt functions
@server.prompt(title="Build Assistant")
async def build_assistant() -> str:
    """Provide build assistance information"""
    return """I am a DevOps build assistant that can help you with:

1. Build mustache deployables (k8s_build_all_no_git)
2. Build helm deployables for specific regions/environments
3. Concurrent batch builds for multiple DTs

Please tell me what build operation you need to perform, and I will provide corresponding assistance."""


if __name__ == "__main__":
    try:
        logger.info("Starting MCP server...")
        # Use FastMCP's built-in run method
        server.run()
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.error(f"Server run failed: {e}")
        exit(1)
