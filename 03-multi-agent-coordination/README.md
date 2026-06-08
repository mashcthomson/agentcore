# Tutorial 03: Multi-Agent Coordination

In this tutorial, you'll build a multi-agent research system using the orchestrator/specialist pattern from the AgentCore Starter Toolkit.

## Learning Objectives

By the end of this tutorial, you will:
- Understand the orchestrator/specialist pattern
- Create an orchestrator agent that routes queries
- Create a specialist agent for web search
- Enable agent-to-agent communication via a2a protocol
- Deploy and test the multi-agent system

## What You'll Build

A research system with two agents:

```
User Query
    ↓
┌─────────────────────────────────┐
│   Orchestrator Agent            │
│   - Routes simple queries       │
│   - Delegates research tasks    │
└───────────┬─────────────────────┘
            │
            │ a2a protocol
            ↓
┌─────────────────────────────────┐
│   Search Specialist Agent       │
│   - Performs web searches       │
│   - Returns formatted results   │
└─────────────────────────────────┘
```

## Why Multi-Agent Systems?

**Single Agent Limitations:**
- One agent tries to do everything
- Generic, not specialized
- Hard to maintain and extend

**Multi-Agent Benefits:**
- **Specialization**: Each agent excels at one thing
- **Modularity**: Easy to add/remove/replace agents
- **Scalability**: Agents can run in parallel
- **Maintainability**: Clear separation of concerns
- **Secure Communication**: A2A protocol enables IAM-controlled agent interactions

## Architecture Decisions

### Decision 1: Separate Configuration Files

We use **two separate `.bedrock_agentcore.yml` files** (one per agent) instead of a single file. While the AgentCore toolkit supports multiple agent definitions in one file, this approach has limitations:

- **Permission Management**: The toolkit doesn't handle cross-agent IAM permissions automatically
- **Local Testing**: Running multiple agents from a single config file creates port conflicts and makes local development difficult
- **Deployment Independence**: Each agent can be deployed, updated, and scaled independently

### Decision 2: A2A Protocol for Agent Communication

We use the **Agent-to-Agent (A2A) protocol** for inter-agent communication instead of the AgentCore `invoke_agent` API:

**Benefits of A2A:**
- **Cloud-Agnostic**: Agents can run on any platform (AWS, GCP, Azure, on-premises)
- **Dynamic Discovery**: Agents discover each other via Agent Cards, no hardcoded URLs
- **Standardized Protocol**: Uses JSON-RPC 2.0 over HTTP with IAM authentication
- **Flexibility**: Agents can be relocated or replicated without code changes

**Trade-offs:**
- Requires additional A2A client/server code
- Not directly supported by AgentCore toolkit (manual implementation needed)

**Alternative (Not Chosen):** Using `invoke_agent` API would tightly couple agents to AWS AgentCore infrastructure and require hardcoded agent ARNs in code. 


## Prerequisites

Before starting, install the required dependencies:

```bash
# using uv (recommended)
uv add 'strands-agents[a2a]'
```

The `[a2a]` extra installs:
- `a2a-python`: A2A protocol client and server components
- `httpx`: Async HTTP client for A2A communication
- All other A2A protocol dependencies

## Step 1: Create the Search Specialist Agent

The specialist handles web search tasks using AgentCore Browser.

### 1.1 Create Directory Structure

```bash
#First, create the directory structure for both agents:

cd ~/agentcore-workshop
mkdir -p multi-agent-research/agents/{search_specialist,orchestrator}

# Copy requirements files
cp pyproject.toml multi-agent-research/agents/search_specialist/
cp pyproject.toml multi-agent-research/agents/orchestrator/
```

### 1.2 Create Search Specialist

Create copy `03-multi-agent-coordination/agents/search_specialist.py` to `~/agentcore-workshop/multi-agent-research/agents/search_specialist`


### 1.3 Configure and Test Search Specialist Locally

**Step 1: Configure the Search Specialist**

Before deploying, create the configuration for local testing:

```bash
cd ~/agentcore-workshop/multi-agent-research/agents/search_specialist

# Configure the Search Specialist with A2A protocol using agentcore CLI
agentcore configure --entrypoint search_specialist.py --protocol A2A

# The CLI will prompt you interactively:
#
# Agent name (default: search_specialist): # <press Enter> until 
#
# Memory Configuration: s
#                       ↑ Type 's' to skip
#
# This creates .bedrock_agentcore.yaml with:
# - protocol: A2A (port 9000, JSON-RPC 2.0, Agent Card enabled)
# - deployment_type: direct_code_deploy

# Verify the configuration
cat .bedrock_agentcore.yaml
```

**Step 2: Start the local development server with A2A Protocol**


```bash
# Start the Search Specialist on port 9000 (A2A protocol)
agentcore dev --port 9000

# Expected output:
# 🚀 Starting development server with hot reloading
# Agent: agent_search_specialist
# Module: multi-agent-research.agents.search_specialist:app
# 💡 Test your agent with: agentcore invoke --dev "Hello" in a new terminal window
# ℹ️  This terminal window will be used to run the dev server
# Press Ctrl+C to stop the server
#
# Server will be available at:
#   • Localhost: http://localhost:9000/invocations
#   • 127.0.0.1: http://127.0.0.1:9000/invocations
#   • Local network: http://192.168.1.67:9000/invocations
#
# INFO:     Uvicorn running on http://0.0.0.0:9000 (Press CTRL+C to quit)
# INFO:     Application startup complete.
```

**Step 3: Test the Search Specialist**

In a **new terminal**, test the agent:

```bash
cd ~/agentcore-workshop
# Check if the server is running
curl http://localhost:9000/ping
# Expected: {"status": "healthy"} or similar health check response

# check agent card
curl http://localhost:9000/.well-known/agent-card.json

# Use agentcore invoke for testing (simplest method), NOTE we can run this because we put a redirect in the code. see @app.post("/invocations")
agentcore invoke --dev --port 9000 '{
           "jsonrpc": "2.0",
           "method": "message/send",
           "id": 1,
           "params": {
             "message": {
               "messageId": "msg-001",
               "role": "user",
               "parts": [
                 {
                   "kind": "text",
                   "text": "Hello, who are you?"
                 }
               ]
             }
           }
         }'

# Expected: Search results with agent response
# {
#    'response': 
# '{"id":1,"jsonrpc":"2.0","result":{"artifacts":[{"artifactId":"1c106d67-b944-478a-9797-c15683d72b1c","name
# ":"agent_response","parts":[{"kind":"text","text":"I am a search specialist agent designed to help you 
# find and summarize information from the web. I can:\\n\\n1. Execute web searches based on your 
# queries\\n2. Analyze the search results\\n3. Provide organized summaries of the findings\\n4. Include 
# source URLs for reference and fact-checking\\n\\nTo get started, just ask me any question or provide a 
# topic you\'d like to learn more about. I\'ll use my web search capabilities to find relevant inf
# }

# or you can use
curl -X POST http://127.0.0.1:9000/ \
     -H "Content-Type: application/json" \
     -d '{
           "jsonrpc": "2.0",
           "method": "message/send",
           "id": 1,
           "params": {
             "message": {
               "messageId": "msg-001",
               "role": "user",
               "parts": [
                 {
                   "kind": "text",
                   "text": "Hello, who are you?"
                 }
               ]
             }
           }
         }' | jq .

# Expected output 
{
  "id": 1,
  "jsonrpc": "2.0",
  "result": {
    "artifacts": [
      {
        "artifactId": "a273cc2b-59f6-4075-b09b-4aece1b26b3d",
        "name": "agent_response",
        "parts": [
          {
            "kind": "text",
            "text": "I am a search specialist assistant designed to:\n- Perform focused web searches\n- Provide brief 2-3 bullet summaries \n- Include source URLs\n\nI aim to be extremely concise. How can I help you search for information today?\n"

# Finally check the agent card
curl http://localhost:9000/.well-known/agent-card.json | jq .

# Expected: json generated automatically from the agent comment in the code


```
Go back to the first terminal and **Stop the dev server** (Ctrl+C) when testing is complete.

### 1.4 Configure and test remotely

First deploy your specialist agent to cloud:

```bash
agentcore deploy
```
Interact with the agent with agentcore toolkit

```bash
cd ~/agentcore-workshop/multi-agent-research/agents/search_specialist
agentcore invoke --port 9000 '{
           "jsonrpc": "2.0",
           "method": "message/send",
           "id": 1,
           "params": {
             "message": {
               "messageId": "msg-001",
               "role": "user",
               "parts": [
                 {
                   "kind": "text",
                   "text": "Tell me how important multi agent systems are?"
                 }
               ]
             }
           }
         }'

# Expected output 
Response:
{"id":1,"jsonrpc":"2.0","result":{"artifacts":[{"artifactId":"2d920591-3486-42ec-95f5-de1417812054","name":"agent_response","parts":[{"kind"
:"text","text":"Found 2 key points about multi-agent systems:\n- Enable complex problem solving through distributed intelligence and 
collaboration between autonomous agents\n- Critical for real-world applications like smart cities, robotics, and AI coordination\n\nSources:
https://example.com/1, 
```
Getting the URL of your agent in the cloud is little complicated. For that I have created a script for you the you need to move to your project folder and run. 

```bash
cd ~/agentcore-workshop
# Run the following to invoke your agent through http call
# Copy 03-multi-agent-coordination/infrastructure/invoke_agent.sh under ~/agentcore-workshop/multi-agent-research/infrastructure and run
uv add awscurl
chmod +x ./multi-agent-research/infrastructure/invoke_agent.sh
./multi-agent-research/infrastructure/invoke_agent.sh

# Expected output 
--- Retrieving Agent Metadata ---
Found Agent ARN: arn:aws:bedrock-agentcore:ap-southeast-2:872970450826:runtime/search_specialist-tEVNSFF5p2
Region: ap-southeast-2
--- Invoking Agent ---
URL: https://bedrock-agentcore.ap-southeast-2.amazonaws.com/runtimes/arn%3Aaws%3Abedrock-agentcore%3Aap-southeast-2%3A872970450826%3Aruntime%2Fsearch_specialist-tEVNSFF5p2/invocations
{
  "id": 1,
  "jsonrpc": "2.0",
  "result": {
    "artifacts": [
```
URL in the output is important and we will use it later. that is the URL of your deployed agent. if you inspect the script, you will see we have used awscurl, that is a special curl library that adds IAM permission to your call. Normally your invocation endpoints are not exposed to public. More on this later. 

## Step 2: Create the Orchestrator Agent

The orchestrator routes queries and delegates to specialists.

### 2.1 Create Orchestrator Code

Copy  `agent-experiments/multi-agent-research-workshop/tutorials/03-multi-agent-coordination/agents/orchestrator/orchestrator.py` to `multi-agent-research/agents/orchestrator/orchestrator.py`:

Take a look at the code. Observe that we use "agent as a tool" pattern here. You can use other patters as described here https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/agents-as-tools/

### 2.2 Configure and Test Orchestrator Locally

**Step 1: Configure the Orchestrator**

```bash
cd ~/agentcore-workshop/multi-agent-research/agents/orchestrator

# Configure the orchestrator using agentcore CLI with A2A protocol
agentcore configure --entrypoint orchestrator.py --protocol A2A

# The CLI will prompt you interactively:
#
# Agent name (default: orchestrator): <press Enter> until
#
# Configure memory? (yes/no) [no]: s
#                                 ↑ Type 's' to skip

# This adds the orchestrator to .bedrock_agentcore.yaml
# The orchestrator uses A2A protocol on port 9000 (same as search specialist)

# Verify the configuration
cat .bedrock_agentcore.yaml
```

**Step 2: Run Locally with A2A Communication**

For local multi-agent testing:

Lets restart the search agent

```bash
# Terminal 1: Start the Search Specialist on port 9000
# we need to run agentcore dev in corresponding folder
cd ~/agentcore-workshop/multi-agent-research/agents/search_specialist
agentcore dev --port 9000
# Expected output:
# 🚀 Starting development server with hot reloading
# Agent: search_specialist
# Module: search_specialist:app
```
PS: alternatively you can use python search_specialist.py if you wish but using agentcore cli makes it easier to control the port at runtime

```bash
# Terminal 2: Start the Orchestrator on port 9001 with SEARCH_SPECIALIST_URL set
cd ~/agentcore-workshop/multi-agent-research/agents/orchestrator
uv add aws_requests_auth
agentcore dev --port 9001 --env SEARCH_SPECIALIST_URL=http://localhost:9000

# Expected output:
# 🚀 Starting development server with hot reloading
# Agent: orchestrator
# Module: orchestrator:app
```

**Local Development Ports**:
- Search Specialist: `http://localhost:9000` (search_specialist.py line 96)
- Orchestrator: `http://localhost:9001` (orchestrator.py line 125)
- Both use port 9000 in production when deployed independently to AgentCore


**Step 3: Test each agents locally**

In a **third terminal**, test the orchestrator:

```bash
# Test if search agent is running aaain
curl http://localhost:9000/ping

# check agent card
curl http://localhost:9000/.well-known/agent-card.json

# now lets check orchesrator agent
curl http://localhost:9001/ping

# check agent card
curl http://localhost:9001/.well-known/agent-card.json

# Simple query (handled by orchestrator directly)
agentcore invoke --dev --port 9001 '{
           "jsonrpc": "2.0",
           "method": "message/send",
           "id": 1,
           "params": {
             "message": {
               "messageId": "msg-001",
               "role": "user",
               "parts": [
                 {
                   "kind": "text",
                   "text": "Hello, who are you?"
                 }
               ]
             }
           }
         }'

# alternatively with culr
curl -X POST http://localhost:9001/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "id": 1,
    "params": {
      "message": {
        "messageId": "msg-001",
        "role": "user",
        "parts": [
          {
            "kind": "text",
            "text": "Hello, who are you?"
          }
        ]
      }
    }
  }' | jq .

# Expected: Orchestrator answers directly without calling specialist
# Expected response:
# "Hi there! I hope you're having a good day. Since this is a simple greeting,
#  I can respond directly without needing to use any research tools.
#  How can I help you today? I'm ready to assist with any questions or research topics you'd like to explore"


**Step 3: Test the Multi-Agent System Locally**


# On the third terminal, we will ask a question to Orchestrator agent and expect the orchestrator agent talk to search agent before answering back
agentcore invoke --dev --port 9001 '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "id": 2,
    "params": {
      "message": {
        "messageId": "msg-002",
        "role": "user",
        "parts": [
          {
            "kind": "text",
            "text": "Search for multi-agent systems"
          }
        ]
      }
    }
  }' 

# Expected flow:
# 1. Orchestrator (port 9001) receives query
# 2. Orchestrator calls Search Specialist via A2A protocol at http://localhost:9000/
# 3. Search Specialist (port 9000) processes search and returns results via JSON-RPC 2.0
# 4. Orchestrator formats and returns final response

# Expected response 
{"id":2,"jsonrpc":"2.0","result":{"artifacts":[{"artifactId":"019c793a-8c20-488a-8775-1374de0b182a","name":"agent_response","parts":[{"kind
":"text","text":"Based on the search results, here are the key findings about multi-agent systems:\\n\\n1. Definition: Multi-agent systems 
are networks of AI agents that interact with each other to solve complex tasks.\\n\\n2. Applications:\\n

```

**Stop both dev servers** (Ctrl+C in each terminal) when testing is complete.

## Step 3: Deploy the Multi-Agent System

### 3.1 Deploy the Search Agent

We have already deployed Search Specialist, here is how to do it again if you have made any changes:

```bash
cd ~/agentcore-workshop/multi-agent-research/search_specialist
agentcore deploy

# Get the a2a endpoint URL from the deployment and make sure the specialist agent deployment is responding 
cd ~/agentcore-workshop
./multi-agent-research/infrastructure/invoke_agent.sh
# Copy the URL value given as output. This URL can be used by any a2a-compliant client on any cloud, given that they have AIM permissins to access this endpoint. Remeber this is not a public URL and protected by AIM permissions, more on this later. We will use it for Orchestrator agent to talk to the search agent.

# URL should look similar to https://bedrock-agentcore.ap-southeast-2.amazonaws.com/runtimes/arn%3Aaws%3Abedrock-agentcore%3Aap-southeast-2%3A872970450826%3Aruntime%2Fsearch_specialist-LWtoPKC0Hg/invocations
```

### 3.2 Deploy the Orchestrator Agent

Now deploy the Orchestrator with the Search Specialist's a2a URL:

```bash
# Lets start deploying locally and talk to search agent in the cloud. this si useful when you are debuging and building your agents. replace the URL with the URL you have received from the previous step
#
# IMPORTANT: the URL must end in /invocations — AgentCore serves the A2A agent
# card at /runtimes/{arn}/invocations/.well-known/agent-card.json. Without the
# /invocations segment the orchestrator's A2ACardResolver gets a 404.

agentcore dev --port 9000 --env SEARCH_SPECIALIST_URL=https://bedrock-agentcore.ap-southeast-2.amazonaws.com/runtimes/arn%3Aaws%3Abedrock-agentcore%3Aap-southeast-2%3A786020471868%3Aruntime%2Fsearch_specialist-Z9dJXj7jJ3/invocations

# and invoke on local
agentcore invoke --dev --port 9000 '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "id": 2,
    "params": {
      "message": {
        "messageId": "msg-002",
        "role": "user",
        "parts": [
          {
            "kind": "text",
            "text": "can you tell me what is multi agent system and what is its importance?"
          }
        ]
      }
    }
  }' 
```
You can see most of the code is about authentication and client and server initialisation. Once you are happy that the agent is working then lets deploy it and test it again in the agentcore. NOTE: if it does not work, find the permissions of your login credentials that you have used during "aws login".

```bash
# Deploy the Orchestrator with the Search Specialist URL
# Environment variables must be passed via --env flag (not in YAML file)
cd ~/agentcore-workshop/multi-agent-research/agents/orchestrator

# WARNING: env vars are NOT persisted in .bedrock_agentcore.yaml. Every
# `agentcore deploy` must re-pass --env SEARCH_SPECIALIST_URL=... or the
# deployed runtime loses the variable and the orchestrator logs
# "SEARCH_SPECIALIST_URL not set - search specialist unavailable".

# Deploy with --env flag
agentcore deploy --env SEARCH_SPECIALIST_URL=https://bedrock-agentcore.ap-southeast-2.amazonaws.com/runtimes/arn%3Aaws%3Abedrock-agentcore%3Aap-southeast-2%3A786020471868%3Aruntime%2Fsearch_specialist-Z9dJXj7jJ3/invocations
```
Once deployemnt is complete go to your AWS account and see taht you have both agetns deployed https://ap-southeast-2.console.aws.amazon.com/bedrock-agentcore/agents?region=ap-southeast-2 make sure they are both active before you run the next command.


```bash
# lets see if it can answer a simple question without talking to the search agent
cd ~/agentcore-workshop/multi-agent-research/agents/orchestrator
agentcore invoke --port 9000 '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "id": 2,
    "params": {
      "message": {
        "messageId": "msg-002",
        "role": "user",
        "parts": [
          {
            "kind": "text",
            "text": "Hello, who are you?"
          }
        ]
      }
    }
  }' 

# You should receive something like the following
Response:
{"id":2,"jsonrpc":"2.0","result":{"artifacts":[{"artifactId":"63c86d87-4d7c-4346-a6b1-ab86ea630888","name":"agent_response","parts":[{"kind"
:"text","text":"Hello! I'm a research orchestrator assistant. I can help you by:\n\n1. Answering simple questions directly\n2. Delegating 
research queries and web searches to a specialized search agent\n3. Providing clear and organized responses\n\nI aim to make information 
access efficient and helpful. Is there any specific topic you'd like to learn more 

# how about a question the the orchestraot agent need to talk to a search agent
agentcore invoke --port 9000 '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "id": 2,
    "params": {
      "message": {
        "messageId": "msg-002",
        "role": "user",
        "parts": [
          {
            "kind": "text",
            "text": "Search for multi-agent systems."
          }
        ]
      }
    }
  }' 

# You are expected to get the following message with a technical issue 

Response:
{"id":2,"jsonrpc":"2.0","result":{"artifacts":[{"artifactId":"9abf4213-a943-46c7-8bd2-1dc2e1a5296b","name":"agent_response","parts":[{"kind"
:"text","text":"I apologize, but it seems there is a technical issue with accessing the search specialist at the moment. However, I can tell
you that multi-agent systems (MAS) are:\n\n1. 
```

We did not give permission for orchestrator agent to talk to search agent. To be clear, when we were running on our local machine we were using our root or AIM account which has admin permissions. Once we deploy to agentcore you need your agent role has permissions has access to agentcore runtime. Lets do that next.

### 3.4 Grant A2A Communication Permissions

The Orchestrator needs permission to invoke the Search Specialist via a2a protocol:

```bash
cd ~/agentcore-workshop/multi-agent-research/agents/orchestrator
# Get the Orchestrator's execution role ARN from its config.
# (macOS/BSD grep has no -P/\K; read it from the yaml with portable sed instead.)
ORCHESTRATOR_ROLE=$(grep -E '^[[:space:]]*execution_role:' .bedrock_agentcore.yaml | grep -v 'null' | head -1 | sed -E 's/.*execution_role:[[:space:]]*//')
echo "$ORCHESTRATOR_ROLE"

# Grant InvokeAgentRuntime permission
aws iam put-role-policy \
  --role-name $(basename $ORCHESTRATOR_ROLE) \
  --policy-name A2AInvokeSpecialist \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": ["bedrock-agentcore:GetAgentCard","bedrock-agentcore:InvokeAgentRuntime"],
      "Resource": "arn:aws:bedrock-agentcore:ap-southeast-2:*:runtime/*"
    }]
  }'

```
If you wish, you can check the values added in the AWS AIM console

This is a very generic permission for orchestator agent to run any bedrock agent. you can limit it by the search agent ARN but this is good for now. Make sure you pay attention that we have given permission to "GetAgentCard" and "InvokeAgentRuntime" to enable agent discovery and invocation; both are needed for A2A protocol to work.

PS: instead of updating orchestrator agent role you can also define resource-based policy for the search_specialist from the AWS console to grant permission to orchestrator agent. your security governance define the way you want to proceed.

### 3.5 Retry the A2A communication 

Lets try the last question to Organiser agent now that we have given permission. 

WARNING: you might need to redeploy your orchestrator agent if you still see the error.

```bash
cd ~/agentcore-workshop/multi-agent-research/agents/orchestrator
agentcore invoke --port 9000 '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "id": 2,
    "params": {
      "message": {
        "messageId": "msg-002",
        "role": "user",
        "parts": [
          {
            "kind": "text",
            "text": "Search for multi-agent systems."
          }
        ]
      }
    }
  }' 
```


## Understanding A2A Protocol Communication

### What is A2A Protocol?

Agent-to-Agent (A2A) protocol is a **cloud-agnostic, standardized protocol** for AI agent communication. It enables agents to communicate across different cloud platforms (AWS, GCP, Azure, on-prem) using HTTP endpoints and JSON-RPC 2.0. Instead of cloud-specific API calls, a2a-compliant URL.

### Authentication

A2A protocol supports multiple authentication methods:

- **OAuth 2.0**: Cloud-agnostic token-based auth
- **SigV4**: AWS-specific request signing
- **Bearer tokens**: Standard HTTP authorization

In this workshop, we use IAM for AWS-hosted agents (Step 3.4).

### A2A Request/Response Flow

1. **User** → Orchestrator: `{"query": "Find research on X"}`
2. **Orchestrator** analyzes query, decides to delegate
3. **Strands framework** → `SEARCH_SPECIALIST_URL` via a2a protocol (JSON-RPC)
4. **Search Specialist** (on any cloud) processes and returns results
5. **Orchestrator** → User: `{"response": "Based on my search specialist findings..."}`

All communication uses the a2a protocol specification from [https://a2a-protocol.org/](https://a2a-protocol.org/)

### Benefits of A2A Protocol

- **Cloud-Agnostic**: Works across AWS, GCP, Azure, on-prem
- **Simple**: No manual API calls, boto3, or base64 encoding needed
- **Standardized**: Uses JSON-RPC 2.0 protocol specification
- **Secure**: Multiple auth options (OAuth, SigV4, Bearer tokens)
- **Scalable**: Each agent runs independently
- **Decoupled**: Agents can be on different clouds/platforms
- **Observable**: Standard HTTP logging and tracing
- **Discoverable**: Agent Cards at `/.well-known/agent-card.json`
- **Interoperable**: Any a2a-compliant agent can talk to any other


### Additional Resources

- **AgentCore Documentation**: https://aws.github.io/bedrock-agentcore-starter-toolkit/
- **Multi-Agent Examples**: https://github.com/aws/bedrock-agentcore-starter-toolkit/tree/main/examples
- **Strands Framework**: https://github.com/anthropics/strands


## Cleanup

To delete both agents and clean up resources:

```bash
# Delete the Orchestrator agent
cd ~/agentcore-workshop/multi-agent-research/agents/orchestrator
agentcore destroy

# Delete the Search Specialist agent
cd ~/agentcore-workshop/multi-agent-research/agents/search_specialist
agentcore destroy
```

**Note**: The `agentcore destroy` command automatically removes:
- AgentCore Runtime
- Container images from ECR
- CloudWatch log groups
- Associated IAM roles (if auto-created)
- .bedrock_agentcore.yml

## Summary

✅ You understand the orchestrator/specialist pattern
✅ You created an orchestrator agent
✅ You created a search specialist agent
✅ You enabled a2a protocol communication between agents
✅ You deployed and tested the multi-agent system
✅ You configured IAM permissions for secure a2a invocation

---

**Workshop Complete!** 🎉

You've successfully built a multi-agent research system using AgentCore. You now have the foundation to build sophisticated AI agent applications.

Thank you for participating in this workshop!
