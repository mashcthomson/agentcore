# Tutorial 02: Your First Agent

In this tutorial, you'll create and deploy your first AI agent using the AgentCore Starter Toolkit.

## Learning Objectives

By the end of this tutorial, you will:
- Create a simple agent using the Strands framework
- Wrap it with BedrockAgentCoreApp
- Deploy it to AgentCore Runtime
- Test the deployed agent

## What You'll Build

A simple research assistant agent that can answer questions about AI and multi-agent systems.

## Step 1: Create Your First Agent

### 1.1 Create Project Directory

```bash
# Create a directory for your agent
mkdir -p ~/agentcore-workshop/simple_agent
cd ~/agentcore-workshop/simple_agent
```

### 1.2 Write the Agent Code

Now create `simple_agent.py` with the following code:

```python
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent

# Initialize AgentCore app
app = BedrockAgentCoreApp()

@app.entrypoint
def handle_query(payload, context):
    """
    Handle incoming research queries.

    Args:
        payload: Dict with 'query' field containing the user's question
        context: Runtime context from AgentCore

    Returns:
        Dict with 'response' field containing the agent's answer
    """
    query = payload.get("query", "Hello!")

    # Create agent with system prompt
    research_agent = Agent(
        model="anthropic.claude-3-5-sonnet-20241022-v2:0",
        system_prompt="""You are a knowledgeable research assistant specializing in
AI and multi-agent systems. Provide clear, accurate, and helpful responses
to questions about these topics."""
    )

    # Get response from the agent
    response = research_agent(query)

    return {
        "response": str(response.message.get('content', [{}])[0].get('text', str(response)))
    }

if __name__ == "__main__":
    # Run the agent locally for testing
    app.run()
```

### 1.3 Understanding the Code

Let's break down what this code does:

**1. Import Dependencies**
```python
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
```
- `BedrockAgentCoreApp`: Wraps your function as an AgentCore-compatible service
- `Agent`: Strands framework agent (simple and easy to use)

**2. Initialize the App**
```python
app = BedrockAgentCoreApp()
```
Creates an AgentCore application that handles HTTP endpoints, health checks, and AWS integration.

**3. Define the Entrypoint**
```python
@app.entrypoint
def handle_query(payload, context):
    ...
```
The `@app.entrypoint` decorator marks this as the main function. It receives:
- **payload**: Request data containing the query
- **context**: Runtime context from AgentCore

**4. Create the Agent**
```python
research_agent = Agent(
    model="au.anthropic.claude-haiku-4-5-20251001-v1:0 ",
    system_prompt="..."
)
```
Creates an agent with:
- **model**: Bedrock Claude model ID
- **system_prompt**: Instructions that guide the agent's behavior

**5. Process and Return**
```python
response = research_agent(query)
return {"response": str(response.message.get('content', [{}])[0].get('text', str(response)))}
```
Invokes the agent and extracts the text response from the message.

## Step 2: Test Your Agent Locally

Before deploying to AWS, test your agent using the AgentCore local development server:

### 2.1 Configure for Local Development

First, generate the configuration file using AgentCore CLI:

```bash
cd ~/agentcore-workshop
agentcore configure
```

When prompted:
- **Entrypoint**: Enter the absolute path to `simple_agent/simple_agent.py`
- For other questions: Press Enter to accept defaults.
- the last command click "s" to skip memory

**Note**: The configure command uses your AWS login session credentials to validate settings.

### 2.2 Start Local Development Server

Start the agentcore dev server with hot reloading:

```bash
cd ~/agentcore-workshop
agentcore dev --port 8080
```

Expected output:
```
Starting development server with hot reloading
Agent: simple_agent_simple_agent
Module: /home/daghan/agentcore-workshop/simple_agent/simple_agent.py
Server will be available at: http://localhost:8080/invocations
Test your agent with: agentcore invoke --dev "Hello" in a new terminal window

INFO:     Will watch for changes in these directories
INFO:     Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

The server runs in the foreground with **hot reloading** - it automatically detects code changes and restarts. Leave it running and open a new terminal for testing.

**Note**: The dev server loads `.bedrock_agentcore.yaml` and uses the `entrypoint` path to run your agent.

### 2.3 Test the Agent

In a **new terminal**, invoke the local development server:

```bash
# Test with agentcore invoke
agentcore invoke --dev '{"query": "What is artificial intelligence?"}'

# Or test with curl
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"query": "What is artificial intelligence?"}'
```

Expected response:
```json
{
  "response": "Artificial intelligence (AI) is a field of computer science...",
  "model_used": "anthropic.claude-3-5-sonnet-20241022-v2:0"
}
```

Press `Ctrl+C` in the first terminal to stop the development server.

**Benefits of agentcore dev**:
- Hot reloading: Changes to your code are automatically picked up
- Same runtime environment as deployment
- Easy testing with `agentcore invoke --dev`
- Built-in health checks and observability

## Step 3: Deploy to AgentCore Runtime

Now let's deploy the agent to AWS! The `.bedrock_agentcore.yaml` you created for local testing also works for deployment.

### 3.1 Deploy the Agent

```bash
cd ~/agentcore-workshop
agentcore deploy

# This will:
# 1. Package your code
# 2. Build a container image (via CodeBuild in the cloud)
# 3. Push to Amazon ECR
# 4. Create AgentCore Runtime
# 5. Deploy your agent
```

**Note**: The deploy command uses the default agent from `.bedrock_agentcore.yaml`. To deploy a specific agent, use `agentcore deploy --agent <agent_name>`.


### 3.2 Test the Deployed Agent

```bash
# Invoke the deployed agent (uses default agent from config)
agentcore invoke '{"query": "Explain agent coordination patterns"}'
```

Expected response:
```json
{
  "response": "Agent coordination patterns define how multiple AI agents...",
  "model_used": "anthropic.claude-3-5-sonnet-20241022-v2:0"
}
```

🎉 **Congratulations!** You've deployed your first agent to AgentCore Runtime!


## Step 4: Monitor Your Agent

### 4.1 View in AWS Console

1. Navigate to: https://console.aws.amazon.com/bedrock-agentcore/
2. Click "Runtimes" in the left sidebar
3. Find your runtime: `simple_agent_simple_agent`
4. Click to view details:
   - Invocation count
   - Latency metrics
   - Error rates
   - Recent logs

### 4.2 View CloudWatch Logs

```bash
# Tail the logs
aws logs tail <log group name> --follow 

aws logs tail /aws/bedrock-agentcore/runtimes/simple_agent_simple_agent-qexY4JCOr1-DEFAULT --follow 
```

## Understanding the Deployment

When you run `agentcore deploy`, the AgentCore CLI:

1. **Reads Configuration**
   - Uses `.bedrock_agentcore.yaml` for deployment settings
   - Validates agent configuration and entrypoint

2. **Packages Your Code**
   - Bundles your entrypoint file and dependencies
   - Creates a deployment package with specified source files

3. **Builds Container Image** (via CodeBuild)
   - Creates a Docker container with your code
   - Installs Python dependencies from `pyproject.toml` or `requirements.txt`
   - Configures Python 3.11 runtime
   - Pushes to Amazon ECR

4. **Creates AWS Resources**
   - AgentCore Runtime with specified configuration
   - IAM execution role (auto-created with Bedrock permissions)
   - S3 bucket for deployment artifacts (auto-created)
   - CloudWatch log group for observability

5. **Deploys Agent**
   - Uploads container to AgentCore Runtime
   - Configures health checks and HTTP endpoints
   - Sets up observability and monitoring

## Key Concepts

### BedrockAgentCoreApp

The `BedrockAgentCoreApp` class transforms your Python function into a production service:

```python
app = BedrockAgentCoreApp()

@app.entrypoint
def my_function(payload):
    # Your logic here
    return result

# This becomes:
# - HTTP endpoint: POST /invocations
# - Health check: GET /ping
# - WebSocket: WS /ws
# - Streaming support (for generators)
# - Error handling
# - Logging integration
```

### Strands Framework

Strands is a lightweight agent framework:
- Simple API: `Agent(model, instructions)(query)`
- Built-in tool support
- Streaming responses
- Easy to learn

Alternative frameworks (covered later):
- **LangGraph**: For complex stateful workflows
- **CrewAI**: For multi-agent teams

## Next Steps

You've successfully deployed your first agent! You can see all the artefacts agentcore has created, see S3, ECS, ECR and most importantly agentcore services and inspect what has been created.


But a single agent can only do so much.

In the next tutorial, we'll build a **multi-agent system** where:
- An **Orchestrator** routes queries
- **Specialist agents** handle specific tasks
- Agents communicate with each other

**Continue to**: [Tutorial 03: Multi-Agent Coordination](../03-multi-agent-coordination/)

## Troubleshooting

### Issue: Deployment fails with "Model access denied"

Models are automatically enabled on first use. This error usually means:
- You're in a region where Bedrock isn't available (using ap-southeast-2)
- IAM permissions are insufficient (ensure your AWS user/role has Bedrock permissions)

Verify model availability: `aws bedrock list-foundation-models --region ap-southeast-2`

```bash
# Check model access
aws bedrock list-foundation-models --region ap-southeast-2
```

### Issue: Local testing fails with connection error

Your AWS credentials need Bedrock permissions:
```bash
# Test Bedrock access
aws bedrock invoke-model \
  --model-id anthropic.claude-3-5-sonnet-20241022-v2:0 \
  --body '{"anthropic_version":"bedrock-2023-05-31","messages":[{"role":"user","content":[{"type":"text","text":"Hello"}]}],"max_tokens":100}' \
  --region us-west-2 \
  output.json
```

### Issue: Local dev server won't start

If `agentcore dev` fails to start:
1. Ensure AWS credentials are configured: `aws sts get-caller-identity`
2. Check that `.bedrock_agentcore.yaml` exists in your project directory
3. Verify your entrypoint file exists and has no syntax errors
4. Check the agent name matches in the config file

## Cleanup

To delete the deployed agent and avoid costs:

```bash
# Destroy the AgentCore deployment (uses default agent from config)
cd ~/agentcore-workshop
agentcore destroy
```

## Summary

✅ You created a simple agent using Strands
✅ You wrapped it with BedrockAgentCoreApp
✅ You configured local development with `.bedrock_agentcore.yaml`
✅ You tested locally using `agentcore dev` and `agentcore invoke --dev`
✅ You deployed it to AgentCore Runtime
✅ You tested the deployed agent
✅ You understand the full development and deployment workflow

---

**Next**: [Tutorial 03: Multi-Agent Coordination](../03-multi-agent-coordination/) →
