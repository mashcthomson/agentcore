# Tutorial 01: Getting Started with AgentCore

Welcome to the Multi-Agent Research Workshop! In this tutorial, you'll set up your development environment and learn about Amazon Bedrock AgentCore.

## Learning Objectives

By the end of this tutorial, you will:
- Understand what Amazon Bedrock AgentCore is
- Set up your AWS account and credentials
- Install the AgentCore Starter Toolkit
- Verify your setup is working

## What is Amazon Bedrock AgentCore?

Amazon Bedrock AgentCore is a comprehensive platform for deploying and operating AI agents securely at scale. It provides:

- **🚀 AgentCore Runtime**: Serverless deployment and scaling for agents
- **🧠 AgentCore Memory**: Persistent storage with semantic and event memory
- **💻 AgentCore Code Interpreter**: Secure code execution in isolated sandboxes
- **🌐 AgentCore Browser**: Cloud-based browser for web interaction
- **🔗 AgentCore Gateway**: Transform APIs into agent tools
- **📊 AgentCore Observability**: Real-time monitoring and tracing
- **🔐 AgentCore Identity**: Secure authentication and access management

## Why Use AgentCore?

Traditional agent development requires managing:
- Infrastructure (servers, containers, scaling)
- Security (authentication, authorization, isolation)
- Observability (logging, monitoring, tracing)
- Integration (APIs, tools, data sources)

AgentCore handles all of this for you, letting you focus on agent logic.

## Prerequisites Checklist

Before starting, ensure you have:

- [ ] **Python 3.11+** installed (`python --version`)
- [ ] **AWS Account** with admin access
- [ ] **AWS CLI** installed and configured
- [ ] **Basic Python knowledge** (functions, async/await)
- [ ] **Basic AI/LLM concepts** (prompts, models, tools)

## Step 1: Set Up AWS Account

### 1.1 Create AWS Account (if needed)

If you don't have an AWS account:
1. Visit https://aws.amazon.com/account/
2. Click "Create an AWS Account"
3. Follow the registration process

### 1.2 Install AWS CLI

**macOS/Linux:**
```bash
# Download and install
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Verify installation
aws --version
```

**Windows:**
Download and run the installer from: https://aws.amazon.com/cli/

### 1.3 Configure AWS Credentials

```bash
# Configure AWS CLI with your credentials
aws login

# You'll be prompted for:
# - login to your AWS account via browser
# - provide you a temporary permission to continue your workshop
# - you might need to call this again if your permission is time out
```

### 1.4 Enable Bedrock Model Access

In this tutorial, we will use Amazon Bedrock Claude models. Before using Claude models, you need to complete a one-time use case details form.

#### Step 1: Navigate to Model Access

1. Open the AWS Console and go to Amazon Bedrock
2. In the left sidebar, click **Model catalog**

#### Step 2: Request Anthropic Claude Access

1. Click **Submit Use Case details** button
3. You'll see Anthropic Claude models that require use case details

#### Step 3: Fill Out Use Case Details Form

When prompted, provide the following information:

**Company Information:**
- Company name (or "Personal/Learning" if individual)
- Industry/sector
- Country

**Use Case Details:**
- **Use case description**: Describe what you're building
  - Example: "Building AI agents for research and multi-agent coordination workshops"
  - Example: "Learning AgentCore and developing agent-based applications"
  - Example: "Prototyping intelligent automation workflows"

- **Responsible AI practices**: How you'll ensure responsible use
  - Example: "Following AWS responsible AI guidelines, implementing content filtering, monitoring for misuse"
  - Example: "Educational use with supervision, adhering to Anthropic's usage policies"

**Tips:**
- Be honest and specific about your use case
- Educational/learning purposes are perfectly valid
- Emphasize responsible AI practices and monitoring
- Approval is typically granted within minutes for legitimate use cases

#### Step 4: Submit and Wait for Approval

1. Review your information
2. Click **Submit** or **Request access**
3. Wait for approval (usually takes a few minutes)
4. You'll receive a notification when approved

#### Step 5: Verify Model Access

After approval, verify models are available:

```bash
# List available Claude models
aws bedrock list-foundation-models \
  --region ap-southeast-2 \
  --query 'modelSummaries[?contains(modelId, `claude`)].modelId' \
  --output table

# Expected output should show Claude models like:
# - anthropic.claude-3-5-sonnet-20241022-v2:0
# - anthropic.claude-3-haiku-20240307-v1:0
```

**Note**: This is a one-time setup per AWS account. Once approved, you can use Claude models across all your projects in that account and region.

## Step 2: Install AgentCore Starter Toolkit

### 2.1 Install uv (Fast Python Package Manager)

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Verify installation
uv --version
```

Expected output:
```
uv 0.x.x
```

**Why uv?**
- **10-100x faster** than pip
- Built-in virtual environment management
- Resolves dependencies more reliably
- Industry-standard Python package manager

### 2.2 Set Up Workshop Project

```bash
# Create and navigate to workshop directory
mkdir -p ~/agentcore-workshop
cd ~/agentcore-workshop

# Initialize a uv project — this creates pyproject.toml and a .venv
uv init --python 3.11

# Confirm pyproject.toml was created (required before `uv add` works)
ls pyproject.toml
```

> **Important**: `uv add` needs a `pyproject.toml` in the current directory. If you
> see `error: No pyproject.toml found`, you skipped `uv init` above or you're in the
> wrong directory — run `uv init --python 3.11` here first, then continue.

### 2.3 Install the AgentCore Starter Toolkit

The starter toolkit provides the `agentcore` CLI plus the runtime SDK used to
build and deploy agents. Run these from inside `~/agentcore-workshop` (where the
`pyproject.toml` lives):

```bash
# Install the starter toolkit (provides the `agentcore` CLI)
uv add bedrock-agentcore-starter-toolkit

# Install the runtime SDK (BedrockAgentCoreApp, Memory, Browser, etc.)
uv add bedrock-agentcore

# Install the Strands framework we'll use for the agents
uv add strands-agents
```

`uv add` automatically creates and uses the project's `.venv`, so there's no
separate `uv venv` / activate step needed before installing.

Verify the CLI installed correctly:

```bash
# Confirm the agentcore CLI is available
uv run agentcore --help
```

Expected output:
```
Usage: agentcore [OPTIONS] COMMAND [ARGS]...

Commands:
  configure  Configure AgentCore project
  deploy     Deploy agent to AgentCore Runtime
  invoke     Invoke deployed agent
  ...
```

> **Tip**: Prefix commands with `uv run` (e.g. `uv run agentcore ...`) to use the
> project's virtual environment, or activate it once with `source .venv/bin/activate`
> and call `agentcore` directly.

## Step 3: Verify Your Setup

### 3.1 Test AWS Access

```bash
# Test AWS credentials
aws sts get-caller-identity
```

Expected output (with your account details):
```json
{
    "UserId": "AIDACKCEVSQ6C2EXAMPLE",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/YourName"
}
```

### 3.2 Test AgentCore CLI

```bash
# Show AgentCore CLI help
agentcore --help
```

Expected output:
```
Usage: agentcore [OPTIONS] COMMAND [ARGS]...

Commands:
  configure  Configure AgentCore project
  deploy     Deploy agent to AgentCore Runtime
  invoke     Invoke deployed agent
  ...
```

## Understanding the AgentCore Starter Toolkit

The AgentCore Starter Toolkit provides:

### 1. **CLI Tools**
- `agentcore configure`: Set up project configuration
- `agentcore deploy`: Deploy agents to Runtime
- `agentcore invoke`: Test deployed agents

### 2. **CloudFormation Templates**
Production-ready infrastructure templates for:
- Single agent deployments
- Multi-agent orchestrator/specialist patterns
- Memory integration
- Gateway integration

### 3. **Framework Examples**
Code examples for popular frameworks:
- **Strands**: Simple, minimal setup (we'll use this)
- **LangGraph**: Stateful workflows with graphs
- **CrewAI**: Multi-agent teams with roles

### 4. **SDK Components**
Python SDK for:
- `BedrockAgentCoreApp`: Wrap functions as agents
- `Memory`: Semantic and event memory
- `Browser`: Web interaction tool
- `CodeInterpreter`: Secure code execution

## Next Steps

Now that your environment is set up, you're ready to build your first agent!

**Continue to**: [Tutorial 02: Your First Agent](../02-first-agent/)

## Troubleshooting

### Issue: AWS CLI not found

```bash
# Verify PATH
echo $PATH

# On macOS/Linux, add to ~/.bashrc or ~/.zshrc:
export PATH="/usr/local/bin:$PATH"

# Reload shell
source ~/.bashrc
```

### Issue: uv command not found

```bash
# Re-run the installation
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add to PATH (if needed)
echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Issue: Virtual environment activation fails

```bash
# uv sync automatically creates .venv
# Just activate it:
source .venv/bin/activate

# If still issues, try:
uv venv
source .venv/bin/activate
```

## Summary

✅ You've set up your AWS account and credentials
✅ You've installed the AgentCore Starter Toolkit
✅ You've verified your setup is working
✅ You understand AgentCore's platform services

You're now ready to build your first agent!

---

**Next**: [Tutorial 02: Your First Agent](../02-first-agent/) →
