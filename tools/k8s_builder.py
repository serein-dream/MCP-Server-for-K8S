#!/usr/bin/env python3
"""
File: mcp-devops-server/tools/k8s_builder.py
Kubernetes build tool for handling deployables build and validation
"""

import asyncio
import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Set
import os
import glob

# Use shared logging configuration
from .logging_config import get_logger

logger = get_logger(__name__)

class K8sBuilder:
    """Kubernetes build tool class"""
    
    def __init__(self, att_root: str):
        self.att_root = Path(att_root)
        self.deployable_dir = self.att_root / "deployable"
        self.build_results = {}
        
    async def _run_make_command(self, args: List[str], cwd: Path) -> Dict:
        """Execute make command"""
        try:
            process = await asyncio.create_subprocess_exec(
                "make", *args,
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, "ATT_ROOT": str(self.att_root)}
            )
            stdout, stderr = await process.communicate()
            
            return {
                "success": process.returncode == 0,
                "stdout": stdout.decode().strip(),
                "stderr": stderr.decode().strip(),
                "returncode": process.returncode
            }
        except Exception as e:
            logger.error(f"Make command failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_all_deployables(self) -> List[str]:
        """Get all deployable directories"""
        deployables = []
        for dt_path in self.deployable_dir.iterdir():
            if dt_path.is_dir():
                k8s_resources = dt_path / "kubernetes" / "resources" / "envs"
                if k8s_resources.exists():
                    deployables.append(dt_path.name)
        return sorted(deployables)
    
    
    async def build_single_deployable(self, dt_name: str) -> Dict:
        """Build single deployable"""
        dt_path = self.deployable_dir / dt_name
        
        if not dt_path.exists():
            return {
                "success": False,
                "error": f"Deployable {dt_name} does not exist"
            }
        
        logger.info(f"Building {dt_name}")
        
        # Execute make k8s_build_all_no_git
        result = await self._run_make_command(
            ["k8s_build_all_no_git"],
            cwd=dt_path
        )
        

        if result["success"]:
            # Validate build output
            build_dir = dt_path / "kubernetes" / "build"
            
            return {
                "success": True,
                "dt": dt_name,
                "build_dir": str(build_dir),
                "validation": True,
                "message": f"Successfully built {dt_name}"
            }
        
        return {
            "success": False,
            "dt": dt_name,
            "error": result.get("stderr", "Build failed"),
            "stdout": result.get("stdout", "")
        }
    
    async def build_single_helm_deployable(self, dt_name: str, region: str, env_name: str, cluster_name: str) -> Dict:
        """Build single helm deployable"""
        dt_path = self.deployable_dir / dt_name
        
        if not dt_path.exists():
            return {
                "success": False,
                "error": f"Deployable {dt_name} does not exist"
            }
        
        helm_path = dt_path / "kubernetes" / "helm"
        if not helm_path.exists():
            return {
                "success": False,
                "error": f"Helm directory not found for {dt_name}"
            }
        
        logger.info(f"Building helm deployable {dt_name} for {region}-{env_name}-{cluster_name}")
        
        try:
            # Step 1: Enter helm directory and update dependencies
            logger.info(f"Updating helm dependencies for {dt_name}")
            # If make dependency update fails, try using helm command directly
            process = await asyncio.create_subprocess_exec(
                "helm", "dependency", "update",
                cwd=str(helm_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, "ATT_ROOT": str(self.att_root)}
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                return {
                    "success": False,
                    "dt": dt_name,
                    "error": f"Helm dependency update failed: {stderr.decode().strip()}",
                    "stdout": stdout.decode().strip()
                }
        
            # Step 2: Execute helm build
            logger.info(f"Running helm build for {dt_name}")
            build_result = await self._run_make_command(
                ["k8s_helm_build", f"REGION={region}", f"ENV_NAME={env_name}", f"CLUSTER_NAME={cluster_name}", f"DT={dt_name}"],
                cwd=helm_path
            )
            
            if build_result["success"]:
                # Step 3: Validate build output
                build_dir = dt_path / "kubernetes" / "build" / f"{region}-{env_name}-{cluster_name}"
                schema_files = list(build_dir.glob("*schema*")) if build_dir.exists() else []
                
                return {
                    "success": True,
                    "dt": dt_name,
                    "build_dir": str(build_dir),
                    "region": region,
                    "env_name": env_name,
                    "cluster_name": cluster_name,
                    "schema_files": [str(f) for f in schema_files],
                    "validation": len(schema_files) > 0,
                    "message": f"Successfully built helm deployable {dt_name} for {region}-{env_name}-{cluster_name}",
                    "stdout": build_result.get("stdout", "")
                }
            
            return {
                "success": False,
                "dt": dt_name,
                "error": build_result.get("stderr", "Helm build failed"),
                "stdout": build_result.get("stdout", "")
            }
            
        except Exception as e:
            logger.error(f"Exception during helm build for {dt_name}: {e}")
            return {
                "success": False,
                "dt": dt_name,
                "error": f"Helm build exception: {str(e)}"
            }

    async def build_multiple_helm_deployables(self, dt_list: List[str], region: str, env_name: str, cluster_name: str, max_concurrent: int = 3) -> Dict:
        """Concurrent batch build of multiple helm deployables
        
        Parameters:
        - dt_list: List of DT names to build
        - region: Region, e.g. us-east-1
        - env_name: Environment name, e.g. stage-live
        - cluster_name: Cluster name, e.g. main
        - max_concurrent: Maximum concurrent number, default 3
        """
        if not dt_list:
            return {
                "success": True,
                "total_dts": 0,
                "successful_dts": [],
                "failed_dts": [],
                "success_count": 0,
                "failure_count": 0,
                "build_details": [],
                "message": "No DT list provided for building"
            }
        
        logger.info(f"Starting concurrent batch helm build of {len(dt_list)} DTs: {dt_list}, target: {region}-{env_name}-{cluster_name}, max concurrent: {max_concurrent}")
        
        # Create semaphore to control concurrency
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def build_single_helm_with_semaphore(dt_name: str, index: int) -> Dict:
            """Single helm DT build with semaphore control"""
            async with semaphore:
                logger.info(f"Building Helm DT {index + 1}/{len(dt_list)}: {dt_name}")
                
                try:
                    # Call single helm DT build method
                    build_result = await self.build_single_helm_deployable(dt_name, region, env_name, cluster_name)
                    
                    # Create build detail object
                    detail = {
                        "success": build_result["success"],
                        "dt": dt_name,
                        "build_dir": build_result.get("build_dir"),
                        "region": build_result.get("region"),
                        "env_name": build_result.get("env_name"),
                        "cluster_name": build_result.get("cluster_name"),
                        "schema_files": build_result.get("schema_files", []),
                        "validation": build_result.get("validation"),
                        "message": build_result.get("message"),
                        "error": build_result.get("error"),
                        "stdout": build_result.get("stdout")
                    }
                    
                    if build_result["success"]:
                        logger.info(f"Helm DT {dt_name} build successful")
                    else:
                        logger.error(f"Helm DT {dt_name} build failed: {build_result.get('error', 'Unknown error')}")
                    
                    return detail
                    
                except Exception as e:
                    logger.error(f"Exception occurred during Helm DT {dt_name} build: {str(e)}")
                    return {
                        "success": False,
                        "dt": dt_name,
                        "error": f"Helm build exception: {str(e)}"
                    }
        
        # Create all build tasks
        tasks = [
            build_single_helm_with_semaphore(dt_name, i) 
            for i, dt_name in enumerate(dt_list)
        ]
        
        # Execute all build tasks concurrently
        logger.info(f"Starting {len(tasks)} concurrent Helm build tasks...")
        build_details = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and exceptions
        successful_dts = []
        failed_dts = []
        processed_details = []
        
        for i, detail in enumerate(build_details):
            dt_name = dt_list[i]
            
            # Handle exception cases
            if isinstance(detail, Exception):
                logger.error(f"Helm DT {dt_name} build task exception: {str(detail)}")
                failed_dts.append(dt_name)
                processed_details.append({
                    "success": False,
                    "dt": dt_name,
                    "error": f"Helm task exception: {str(detail)}"
                })
            else:
                processed_details.append(detail)
                if detail["success"]:
                    successful_dts.append(dt_name)
                else:
                    failed_dts.append(dt_name)
        
        success_count = len(successful_dts)
        failure_count = len(failed_dts)
        total_success = failure_count == 0
        
        # Generate summary message
        if total_success:
            message = f"Concurrent batch Helm build completed! All {success_count} DTs built successfully"
        elif success_count == 0:
            message = f"Concurrent batch Helm build failed! All {failure_count} DTs failed to build"
        else:
            message = f"Concurrent batch Helm build partially successful! {success_count} successful, {failure_count} failed"
        
        logger.info(message)
        
        return {
            "success": total_success,
            "total_dts": len(dt_list),
            "successful_dts": successful_dts,
            "failed_dts": failed_dts,
            "success_count": success_count,
            "failure_count": failure_count,
            "build_details": processed_details,
            "message": message
        }

    async def build_multiple_deployables(self, dt_list: List[str], max_concurrent: int = 3) -> Dict:
        """Concurrent batch build of multiple deployables
        
        Parameters:
        - dt_list: List of DT names to build
        - max_concurrent: Maximum concurrent number, default 3 (to avoid system resource overload)
        """
        if not dt_list:
            return {
                "success": True,
                "total_dts": 0,
                "successful_dts": [],
                "failed_dts": [],
                "success_count": 0,
                "failure_count": 0,
                "build_details": [],
                "message": "No DT list provided for building"
            }
        
        logger.info(f"Starting concurrent batch build of {len(dt_list)} DTs: {dt_list}, max concurrent: {max_concurrent}")
        
        # Create semaphore to control concurrency
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def build_single_with_semaphore(dt_name: str, index: int) -> Dict:
            """Single DT build with semaphore control"""
            async with semaphore:
                logger.info(f"Building DT {index + 1}/{len(dt_list)}: {dt_name}")
                
                try:
                    # Call single DT build method
                    build_result = await self.build_single_deployable(dt_name)
                    
                    # Create build detail object
                    detail = {
                        "success": build_result["success"],
                        "dt": dt_name,
                        "build_dir": build_result.get("build_dir"),
                        "validation": build_result.get("validation"),
                        "message": build_result.get("message"),
                        "error": build_result.get("error"),
                        "stdout": build_result.get("stdout")
                    }
                    
                    if build_result["success"]:
                        logger.info(f"DT {dt_name} build successful")
                    else:
                        logger.error(f"DT {dt_name} build failed: {build_result.get('error', 'Unknown error')}")
                    
                    return detail
                    
                except Exception as e:
                    logger.error(f"Exception occurred during DT {dt_name} build: {str(e)}")
                    return {
                        "success": False,
                        "dt": dt_name,
                        "error": f"Build exception: {str(e)}"
                    }
        
        # Create all build tasks
        tasks = [
            build_single_with_semaphore(dt_name, i) 
            for i, dt_name in enumerate(dt_list)
        ]
        
        # Execute all build tasks concurrently
        logger.info(f"Starting {len(tasks)} concurrent build tasks...")
        build_details = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and exceptions
        successful_dts = []
        failed_dts = []
        processed_details = []
        
        for i, detail in enumerate(build_details):
            dt_name = dt_list[i]
            
            # Handle exception cases
            if isinstance(detail, Exception):
                logger.error(f"DT {dt_name} build task exception: {str(detail)}")
                failed_dts.append(dt_name)
                processed_details.append({
                    "success": False,
                    "dt": dt_name,
                    "error": f"Task exception: {str(detail)}"
                })
            else:
                processed_details.append(detail)
                if detail["success"]:
                    successful_dts.append(dt_name)
                else:
                    failed_dts.append(dt_name)
        
        success_count = len(successful_dts)
        failure_count = len(failed_dts)
        total_success = failure_count == 0
        
        # Generate summary message
        if total_success:
            message = f"Concurrent batch build completed! All {success_count} DTs built successfully"
        elif success_count == 0:
            message = f"Concurrent batch build failed! All {failure_count} DTs failed to build"
        else:
            message = f"Concurrent batch build partially successful! {success_count} successful, {failure_count} failed"
        
        logger.info(message)
        
        return {
            "success": total_success,
            "total_dts": len(dt_list),
            "successful_dts": successful_dts,
            "failed_dts": failed_dts,
            "success_count": success_count,
            "failure_count": failure_count,
            "build_details": processed_details,
            "message": message
        }
    