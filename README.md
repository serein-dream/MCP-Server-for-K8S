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

**Mustache Build Example:**
```
Batch build mustache deployable for the following configuration:
- dt_list: ["agent-portal-api", "agent_two"]
```

**Helm Build Example:**
```
Batch build helm deployable for the following configuration:
- dt_list: ["agent-portal-api", "agent_two"]
- region: "us-east-1" 
- env_name: "stage-live"
- cluster_name: "main"
```

## What Makes a Good Prompt?

To ensure reliable and predictable builds, follow these best practices when crafting your prompts:

### 1. Specify Build Type

Always explicitly specify whether you want to build **mustache** or **helm** deployables in your prompt. This ensures the correct tool is called.

- ✅ **Recommended**: "Build **mustache** deployables for..."
- ✅ **Recommended**: "Build **helm** deployables for..."
- ❌ **Not recommended**: Relying on Cursor's automatic detection, as this may lead to unpredictable tool selection

> **Note**: We are considering adding automatic build type detection in future versions.

### 2. Provide Clear Parameter Information

#### 2.1 DT_list Parameter

Specify which deployables (DTs) to build using a list format:
```
dt_list: ["deployable-name-1", "deployable-name-2"]
```

#### 2.2 Cluster Specification

Each DT contains multiple clusters named in the format: `region-env-cluster`

**For Mustache Builds:**
- No need to specify region, env, or cluster parameters
- Will build ALL region-env-cluster combinations under the specified DT

**For Helm Builds:**
- MUST specify region, env, and cluster parameters
- Will only build the specified region-env-cluster combination

**Helm Parameter Format:**

For a cluster like `"eu-north-1-prod-sandbox"`, we recommend:

✅ **Recommended approach:**
```
region: "eu-north-1"
env_name: "prod" 
cluster_name: "sandbox"
```

⚠️ **Alternative (but not recommended):**
```
env: "eu-north-1-prod-sandbox"
```
*This Parameter relies on cursor understanding and splitting, which may lead to incorrect partitioning. It is still recommended to specify in the form of three parameters.*


