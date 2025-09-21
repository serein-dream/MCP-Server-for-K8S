# MCP DevOps Build Server

A Model Context Protocol (MCP) server for automated DevOps builds supporting Mustache and Helm deployables.

## Quick Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Cursor IDE**:
   Add to your Cursor settings JSON (replace {your_path} with your actual project directory):
   ```json
   {
     "mcp": {
       "servers": {
         "devops-build-server": {
           "command": "python",
           "args": ["{this_file_path}/MCP_build_version_1/server.py"],
           "env": {
             "ALL_THE_THINGS_ROOT": "{K8S_all_things_root}"
           }
         }
       }
     }
   }
   ```

3. **Restart Cursor IDE**

## Available Tools

- **build_deployables**: Build mustache templates concurrently
- **build_helm_deployables**: Build Helm charts for specific environments

## Usage Examples

**Mustache Build**:
Batch build mustache deployable for the following configuration:
- dt_list: ["agent-portal-api", "agent_two"]

**Helm Build**:
Batch build helm deployable for the following configuration:
- dt_list: ["agent-portal-api", "agent_two"]
- region: "us-east-1" 
- env_name: "stage-live"
- cluster_name: "main"
