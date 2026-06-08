# MCP Gateway Setup Guide

This guide shows how to connect external research APIs (PubMed, etc.) to your agents using AgentCore's MCP Gateway.

## What is MCP Gateway?

MCP (Model Context Protocol) Gateway is an AgentCore service that transforms external APIs into agent-callable tools. It handles:
- AgentCore Browser - Built-in web search and browsing capabilities
- Citation Management - Custom tool for managing research citations
- MCP Gateway - Connecting external research APIs
- Tool Patterns - Best practices for building and composing tools

## Prerequisites

Completed Tutorial 03 (Multi-Agent Coordination)

## Architecture

```
              ┌────────────────────────┐
              │   Research Agent       │
              │                        │
              │  • Web Search          │
              │  • Citation Manager    │
              │  • Tool Composition    │
              └───────────┬────────────┘
                          │
                          ▼
              ┌────────────────────────┐
              │    MCP Gateway         │
              │    (AgentCore)         │
              │                        │
              │  • API Authentication  │
              │  • Rate Limiting       │
              │  • Request Transform   │
              │  • Error Handling      │
              └──┬──────────┬──────┬───┘
                 │          │      │
        ┌────────┘          │      └────────┐
        │                   │               │
        ▼                   ▼               ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  Lambda      │   │ External     │   │  MCP Tools   │
│  Functions   │   │ APIs         │   │  & Servers   │
│              │   │              │   │              │
│ • Research   │   │ • PubMed     │   │ • Citation   │
│ • Analysis   │   │ • Scholar    │   │ • Browser    │
│ • Synthesis  │   │              │   │ • Custom     │
└──────────────┘   └──────────────┘   └──────────────┘
```

## Prerequisites

- AgentCore CLI installed
- AWS credentials configured
- External API keys (PubMed, etc.)

## Step 1: Define Your API Schema

Create the directory structure and OpenAPI specification for the external API:

```bash
# Create directory structure
cd ~/agentcore-workshop
mkdir -p agents_and_tools/tools
```

copy agentcore-tutorial/04-research-tools/tools/pubmed-api.yaml inside the agents_and_tools directory

**Directory structure:**
```
agents_and_tools/
├── gateway_info.json        # Gateway info (created in Step 2)
└── tools/
    └── pubmed-api.yaml      # PubMed API spec
```

**Note:** You can create additional API specifications following the same pattern for other external services (Google Scholar, Semantic Scholar, etc.). Just place them in the `agents_and_tools/tools/` directory.

## Step 2: Deploy MCP Gateway

**📁 Run these commands from:** `~/agentcore-workshop/agents_and_tools` directory


```bash
# Navigate to the tutorial directory
cd ~/agentcore-workshop/agents_and_tools

AWS_ACCOUNT_NUMBER=$(aws sts get-caller-identity --query Account --output text)

# Step 1: Create the MCP Gateway with IAM authentication
aws bedrock-agentcore-control create-gateway \
  --name research-tool-gateway \
  --role-arn arn:aws:iam::$AWS_ACCOUNT_NUMBER:role/AgentCoreGatewayExecutionRole \
  --protocol-type MCP \
  --authorizer-type AWS_IAM \
  --protocol-configuration '{"mcp": {"searchType": "SEMANTIC"}}' \
  --region ap-southeast-2 > gateway_info.json  

# The gateway will use IAM SigV4 authentication. you can use oauth with cognito or any oauth provider you want to integrate.

# What "searchType": "SEMANTIC" does:
# Adds intelligent tool discovery
# - Adds a semantic search tool to the gateway
# - Allows agents to discover tools using natural language
# - Matches user intent to available API endpoints
# - Example: "find papers" → suggests searchPubMed
# - Default: enabled (recommended)

# View the gateway information
cat gateway_info.json

# Example `gateway_info.json` format:
{
  "id": "gateway-abc123",
  "arn": "arn:aws:bedrock-agentcore:ap-southeast-2:123456789012:gateway/gateway-abc123",
  "name": "research-tool-gateway",
  "url": "https://gateway-abc123.bedrock-agentcore.ap-southeast-2.amazonaws.com",
  "executionRoleArn": "arn:aws:iam::123456789012:role/AgentCore-Gateway-ExecutionRole-xyz",
  "status": "AVAILABLE",
  "createdAt": "2024-01-13T10:00:00Z"
}


# Extract from gateway_info.json
GATEWAY_ARN=$(cat ./gateway_info.json | jq -r .gatewayArn)
GATEWAY_URL=$(cat ./gateway_info.json | jq -r .gatewayUrl)
ROLE_ARN=$(cat ./gateway_info.json | jq -r .roleArn)

# Verify values are loaded
echo "Gateway ARN: $GATEWAY_ARN"
echo "Gateway URL: $GATEWAY_URL"
echo "Role ARN: $ROLE_ARN"

# IMPORTANT: Verify gateway exists before proceeding
agentcore gateway get-mcp-gateway --name research-tool-gateway --region ap-southeast-2

# If you get ResourceNotFoundException, the gateway wasn't created successfully
# Check the gateway_info.json file for error messages
```


```bash
# Step 2: Add PubMed target

# Upload specs to S3 first
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
S3_BUCKET="agentcore-gateway-specs-${AWS_ACCOUNT_ID}"

# Create bucket if doesn't exist
aws s3 mb s3://${S3_BUCKET} --region ap-southeast-2 || true

# Upload specs
aws s3 cp tools/pubmed-api.yaml s3://${S3_BUCKET}/pubmed-api.yaml


# Add PubMed target using S3
# For public APIs like PubMed, provide a dummy credential
# PubMed will ignore the extra header
agentcore gateway create-mcp-gateway-target \
  --gateway-arn "$GATEWAY_ARN" \
  --gateway-url "$GATEWAY_URL" \
  --role-arn "$ROLE_ARN" \
  --name pubmed \
  --region ap-southeast-2 \
  --target-type openApiSchema \
  --target-payload "{\"s3\": {\"uri\": \"s3://${S3_BUCKET}/pubmed-api.yaml\"}}" \
  --credentials '{"api_key": "not-required", "credential_location": "HEADER", "credential_parameter_name": "X-API-Key"}'
```

**Verify deployment:**
```bash
# List all gateways
agentcore gateway list-mcp-gateways --region ap-southeast-2

# Get gateway details
agentcore gateway get-mcp-gateway --name research-tool-gateway --region ap-southeast-2

# List gateway targets
agentcore gateway list-mcp-gateway-targets --name research-tool-gateway --region ap-southeast-2
```

## Test Gateway Directly

To test an IAM-authenticated gateway, use **awscurl** which signs requests with SigV4:

```bash
# List available tools
awscurl --service bedrock-agentcore \
  --region ap-southeast-2 \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "tools/list", "id": 1}' \
  $GATEWAY_URL | jq .

# Test PubMed search (note: db parameter is required)
awscurl --service bedrock-agentcore \
  --region ap-southeast-2 \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "pubmed___searchPubMed",
      "arguments": {
        "db": "pubmed",
        "term": "machine learning",
        "retmax": 5
      }
    },
    "id": 1
  }' \
  $GATEWAY_URL | jq .
```

**Notes**:
- `awscurl` is a command-line tool (installed via `pip install awscurl`) that automatically uses your AWS credentials to sign requests with SigV4
- This method tests the gateway directly using MCP JSON-RPC protocol

### Test Gateway via agent

## Test the agent on local (which will use the cloud gateway)

```bash
# Start agent on local
cd ~/agentcore-workshop/multi-agent-research/agents/search_specialist

# Export environment variables (required for agent to discover gateway)
export RESEARCH_GATEWAY_URL=$(cat ../../../agents_and_tools/gateway_info.json | jq -r .gatewayUrl)
export AWS_REGION="ap-southeast-2"

# Verify the URL is set
echo "Gateway URL: $RESEARCH_GATEWAY_URL"

# Start agent with gateway integration, Ignore warnings. you should see 
# INFO:search_specialist:MCP Gateway client configured successfully
agentcore dev --port 9000
```

On different terminal 

```bash
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
            "text": "Search internet and academic publications for recent research papers on machine learning in healthcare"
          }
        ]
      }
    }
  }'
```

**Expected response:**
```
Found results on Recent ML Healthcare Research:\\n- Medical Imaging AI: New deep learning models are achieving breakthrough
accuracy in detecting diseases from medical images, particularly in radiology and pathology (PubMed ID: 39301200)\\n- Precision Medicine: 
Research shows ML algorithms are improving patient outcome predictions and treatment recommendations by analyzing genetic and clinical 
data\\n- Healthcare Operations: Studies demonstrate successful implementation of ML in reducing hospital wait times and optimizing resource 
allocation\\n\\nSources:\\n- PubMed database shows 253 recent academic papers specifically from 2023-2024\\n- Latest publications indexed 
under IDs: 39301200, 39295895, 39100505, etc.\\n- Note: Web search results are from mock data (example.com URLs)\\n\\nThe high number of 
recent publications (253 papers in just the last year) indicates this is a very active research area. For more detailed information about 
any specific aspect or to focus on a particular application area, please let me 
know.
```

## Deploy the agent to agentcore (which will use the cloud gateway)

```bash
cd ~/agentcore-workshop/multi-agent-research/agents/search_specialist
agentcore deploy --env RESEARCH_GATEWAY_URL=$RESEARCH_GATEWAY_URL

# run the call against the agent core search agent

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
            "text": "Search internet and academic publications for recent research papers on machine learning in healthcare"
          }
        ]
      }
    }
  }'
```

this will return 

```
Invocation failed: An error occurred (424) when calling the InvokeAgentRuntime operation: 
```

if you look at the log you will see something similar

```
| httpx.HTTPStatusError: Client error '403 Forbidden' for url 'https://research-tool-gateway-ckbltztcjg.gateway.bedrock-agentcore.ap-southeast-2.amazonaws.com/mcp'
```
here is why

**How IAM Authentication Works:**

1. **Local Development**: The agent uses your local AWS credentials (from `aws configure`) to sign requests with SigV4
2. **Deployed Agent**: When deployed to AgentCore Runtime, the agent automatically uses its execution role's credentials
3. **No tokens needed**: Unlike OAuth, there are no client IDs, secrets, or tokens to manage


## Step 4: IAM Permissions

Your agent's IAM execution role (or your local AWS credentials) needs these permissions:

```bash
cd ~/agentcore-workshop/multi-agent-research/agents/search_specialist

# Construct the gateway ARN (MUST be the specific gateway ARN, not a wildcard)
GATEWAY_ARN=$(cat ../../../agents_and_tools/gateway_info.json | jq -r .gatewayArn)
echo "Gateway ARN: $GATEWAY_ARN"

# Get the search_specialist's execution role name
ROLE_ARN=$(agentcore status --verbose 2>&1 | grep -A 1 "execution_role" | grep "arn:" | tr -d ' ",')
ROLE_NAME=$(basename "$ROLE_ARN")
echo "Execution Role: $ROLE_NAME"

# Grant InvokeGateway permission with the specific gateway ARN
aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name GatewayInvokePermission \
  --policy-document "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [
      {
        \"Sid\": \"AllowGatewayInvocation\",
        \"Effect\": \"Allow\",
        \"Action\": \"bedrock-agentcore:InvokeGateway\",
        \"Resource\": \"${GATEWAY_ARN}\"
      }
    ]
  }"

```

**What this does:**
- Gets the specific gateway ARN (NOT a wildcard - IAM requires exact ARN)
- Grants the agent's execution role permission to invoke the specific MCP Gateway
- Uses IAM authentication (SigV4) for secure access
- Automatically detects your AWS account ID and gateway ID

**Verify the policy was added:**
```bash
aws iam get-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name GatewayInvokePermission
```
Lets ry running the search agent  again

```bash
# run the call against the agent core search agent

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
            "text": "Search internet and academic publications for recent research papers on machine learning in healthcare"
          }
        ]
      }
    }
  }'
  ```

now you should receive 

```json
{"id":2,"jsonrpc":"2.0","result":{"artifacts":[{"artifactId":"3b224007-67a7-48a1-918d-cef0817762c6","name":"agent_response","parts":[{"kind"
:"text","text":"Found results on Machine Learning in Healthcare:\n- Machine learning models are increasingly being deployed for clinical 
decision support, particularly in diagnostic imaging and predictive analytics\n- Recent focus on federated learning approaches to preserve 
patient privacy while allowing collaborative model training across healthcare institutions\n- Emergence of multimodal ML systems that 
combine different data types (imaging, electronic health records, genomics) for more comprehensive analysis\n\nSources: \nNote: Using mock 
data for demonstration as the function implementation is simulated. In a production environment, this would return actual recent research 
papers from:\n- PubMed ID: 41533277, 41533054, 41533053\n- Academic search results\n- Web search results from medical journals and research 
institutions\n\nFor actual research papers and detailed findings, I recommend consulting PubMed Central, Google Scholar, or specific medical
journals 
directly.\n"
```

How about our orchestrator agent. will it work with the new search agent?

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

it worked!!!! You should expect similar output like below 

```json
{"id":2,"jsonrpc":"2.0","result":{"artifacts":[{"artifactId":"c0321ffb-9fdd-4817-b83e-b3a934ea1054","name":"agent_response","parts":[{"kind"
:"text","text":"Based on the search results, here's a comprehensive overview of multi-agent systems (MAS):\n\nDefinition:\n- Multi-agent 
systems are networks of multiple interacting intelligent agents that work together to solve complex problems\n- Each agent is autonomous and
can interact with both other agents and their environment\n- They tackle problems that would be difficult or impossible for individual 
agents to solve alone\n\nKey Applications:\n1. Manufacturing and Logistics\n2. Smart Grid Management and Energy Distribution\n3. Traffic 
Control and Transportation Systems\n4. Healthcare Monitoring and Patient Care Coordination\n5. Robotics and Swarm Intelligence 
Applications\n\nCurrent Developments:\n1. Integration with AI and Machine Learning for enhanced decision-making\n2. Blockchain-based 
multi-agent systems for secure and decentralized operations\n3. Applications in IoT environments for smart cities and homes\n4. Development 
of sophisticated coordination and negotiation protocols between agents\n\nThe field is actively evolving with new applications emerging in 
various domains, particularly in AI integration, distributed systems, and autonomous operations. These systems are becoming increasingly 
important as we move towards more complex, interconnected technological 
solutions.\n"
```


## Best Practices

1. **Rate Limiting** - Configure appropriate rate limits to respect API quotas
2. **Caching** - Enable response caching for frequently accessed data
3. **Error Handling** - Implement retries with exponential backoff
4. **Monitoring** - Set up CloudWatch alarms for gateway errors
5. **Security** - Use AgentCore Identity for all API keys
6. **Regional Deployment** - Deploy gateway in same region as agents


### 5. Exposing Lambda functions as MCP tools to the agents

Create a citation management tool that tracks and formats research sources. In this section we will create a lambda function using SAM and attach it to gateway using agentcore. Let's start.

Install SAM cli from https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/manage-sam-cli-versions.html

copy ~/multi-agent-research-workshop/tutorials/04-research-tools/tools/lambda_citation_manager folder under ~/agentcore-workshop/agents_and_tools/tools/lambda_citation_manager


### Deploy with SAM

```bash
cd ~/agentcore-workshop/agents_and_tools/tools/lambda_citation_manager
uv pip install pip
# Build
sam build

# Deploy
sam deploy \
  --guided \
  --stack-name research-agent-stack \
  --capabilities CAPABILITY_IAM

# Test Lambda function

# 1. Add a citation
aws lambda invoke \
    --function-name citation-manager-dev \
    --cli-binary-format raw-in-base64-out \
    --payload '{"action":"add_citation","parameters":{"title":"Machine Learning in Healthcare: A Comprehensive Review","url":"https://pubmed.ncbi.nlm.nih.gov/39301200","authors":["Smith, J.","Doe, A.","Johnson, R."],"publication_date":"2024","publisher":"Nature Medicine","doi":"10.1038/s41591-024-12345","citation_type":"article"}}' \
    response.json && cat response.json

# Expected output:
# {"statusCode": 200, "body": "{\"message\": \"Citation added successfully\", \"citation_id\": \"cite_1234\"}"}

# 2. Get citation in different formats
aws lambda invoke \
    --function-name citation-manager-dev \
    --cli-binary-format raw-in-base64-out \
    --payload '{"action":"get_citation","parameters":{"citation_id":"cite_1234","format":"apa"}}' \
    response.json && cat response.json

# Try MLA format
aws lambda invoke \
    --function-name citation-manager-dev \
    --cli-binary-format raw-in-base64-out \
    --payload '{"action":"get_citation","parameters":{"citation_id":"cite_1234","format":"mla"}}' \
    response.json && cat response.json

# 3. List all citations
aws lambda invoke \
    --function-name citation-manager-dev \
    --cli-binary-format raw-in-base64-out \
    --payload '{"action":"list_citations","parameters":{"format":"apa"}}' \
    response.json && cat response.json

# 4. Search citations
aws lambda invoke \
    --function-name citation-manager-dev \
    --cli-binary-format raw-in-base64-out \
    --payload '{"action":"search_citations","parameters":{"query":"machine learning"}}' \
    response.json && cat response.json

# 5. Health check
aws lambda invoke \
    --function-name citation-manager-health-dev \
    response.json && cat response.json
```

**Alternative: Using JSON files for complex payloads**

```bash
# Create payload file
cat > add_citation.json << 'EOF'
{
  "action": "add_citation",
  "parameters": {
    "title": "Deep Learning Applications in Medical Imaging",
    "url": "https://arxiv.org/abs/2301.12345",
    "authors": ["Chen, L.", "Wang, X.", "Liu, Y."],
    "publication_date": "2023",
    "publisher": "arXiv",
    "doi": "10.48550/arXiv.2301.12345",
    "citation_type": "preprint"
  }
}
EOF

# Invoke with file
aws lambda invoke \
    --function-name citation-manager-dev \
    --payload file://add_citation.json \
    response.json && cat response.json
```

**Console Testing** (Optional): Check and test your Lambda function in the AWS Console:
https://ap-southeast-2.console.aws.amazon.com/lambda/home?region=ap-southeast-2#/functions/citation-manager-dev?tab=testing

## Integrating Lambda to Your Gateway

Now that the citation manager Lambda is deployed, add it as an MCP Gateway target so agents can discover and use it.

### Step 1: Get Gateway Details

```bash
# Get your existing gateway information
cd ~/agentcore-workshop/agents_and_tools

# View gateway details
cat gateway_info.json

# Extract needed values
GATEWAY_ARN=$(cat gateway_info.json | jq -r .gatewayArn)
GATEWAY_URL=$(cat gateway_info.json | jq -r .gatewayUrl)
GATEWAY_ROLE=$(cat gateway_info.json | jq -r .roleArn)

echo "Gateway ARN: $GATEWAY_ARN"
echo "Gateway URL: $GATEWAY_URL"
echo "Gateway Role: $GATEWAY_ROLE"
```

### Step 2: Add Lambda as Gateway Target

```bash
# Get Lambda ARN
LAMBDA_ARN=$(aws cloudformation describe-stacks \
    --stack-name research-agent-stack \
    --query 'Stacks[0].Outputs[?OutputKey==`FunctionArn`].OutputValue' \
    --output text)

echo "Lambda ARN: $LAMBDA_ARN"

# Add Lambda as gateway target
agentcore gateway create-mcp-gateway-target \
    --gateway-arn "$GATEWAY_ARN" \
    --gateway-url "$GATEWAY_URL" \
    --role-arn "$GATEWAY_ROLE" \
    --name citation-manager-target \
    --target-type lambda \
    --region ap-southeast-2 \
    --target-payload "{
        \"lambdaArn\": \"${LAMBDA_ARN}\",
        \"toolSchema\": {
            \"inlinePayload\": [{
                \"name\": \"citation_manager\",
                \"description\": \"Manage research citations in APA, MLA, and Chicago formats. Supports actions: add_citation (with title, url, authors, publication_date, publisher, doi, citation_type), get_citation (citation_id, format), list_citations (format), search_citations (query), remove_citation (citation_id). Formats: apa, mla, chicago, json.\",
                \"inputSchema\": {
                    \"type\": \"object\",
                    \"properties\": {
                        \"action\": {
                            \"type\": \"string\",
                            \"description\": \"Action to perform: add_citation, get_citation, list_citations, search_citations, or remove_citation\"
                        },
                        \"parameters\": {
                            \"type\": \"object\",
                            \"description\": \"Action-specific parameters\"
                        }
                    },
                    \"required\": [\"action\"]
                }
            }]
        }
    }"
```

### Step 4: Grant Gateway Permission to Invoke Lambda

The gateway needs permission to invoke your Lambda function:

```bash
# Get gateway execution role name
GATEWAY_ROLE_NAME=$(basename "$GATEWAY_ROLE")

# Add Lambda invoke permission to gateway role
aws iam put-role-policy \
    --role-name "$GATEWAY_ROLE_NAME" \
    --policy-name CitationManagerLambdaInvoke \
    --policy-document "{
        \"Version\": \"2012-10-17\",
        \"Statement\": [
            {
                \"Effect\": \"Allow\",
                \"Action\": \"lambda:InvokeFunction\",
                \"Resource\": \"${LAMBDA_ARN}\"
            }
        ]
    }"

echo "✅ Gateway can now invoke citation manager Lambda"
```

### Step 5: Verify Gateway Integration

```bash
# List gateway targets
agentcore gateway list-mcp-gateway-targets \
    --name research-tool-gateway \
    --region ap-southeast-2

# You should see:
# - pubmed target (if you added PubMed earlier)
# - citation-manager-target (newly added)
```

### Step 6: Test Agent with Citation Manager

```bash
cd ~/agentcore-workshop/multi-agent-research/agents/search_specialist

# Restart agent to discover new tools
export RESEARCH_GATEWAY_URL=$(cat ../../../agents_and_tools/gateway_info.json | jq -r .gatewayUrl)
export AWS_REGION="ap-southeast-2"

agentcore dev --port 9000

# In another terminal, test the agent
agentcore invoke --dev --port 9000 '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "id": 3,
    "params": {
      "message": {
        "messageId": "msg-003",
        "role": "user",
        "parts": [
          {
            "kind": "text",
            "text": "Search PubMed for a paper on machine learning in healthcare, then add it as a citation in APA format"
          }
        ]
      }
    }
  }'
```

**Expected Result**: The agent will:
1. Use PubMed tool to search for papers
2. Use citation_manager tool to add the citation
3. Return the formatted citation

```bash
# agent output
{"id":3,"jsonrpc":"2.0","result":{"artifacts":[{"artifactId":"eb7ef7e5-a2fd-45c9-b33e-3c27da25a85d","name":"agent_response","parts":[{"kind
":"text","text":"Found results on machine learning in healthcare:\\n- Located a systematic review paper on machine learning applications in 
healthcare\\n- Successfully added the citation to the citation manager\\n- Generated APA format citation for the paper\\n\\nSource: Smith, 
J. & Johnson, M.. (2023). Applications of Machine Learning in Healthcare: A Systematic Review. Journal of Medical Informatics. 
https://doi.org/10.1234/jmi.2023.123456\\n\\nNote: This example uses simulated citation data for demonstration 
purposes.\\n"}



# Lamda logs
[INFO]	2026-01-19T07:49:45.710Z	b841bfde-2202-4758-bf53-c06db192fc4c	Lambda invoked with event: 
{
    "action": "add_citation",
    "parameters": {
        "citation_type": "journal",
        "publication_date": "2023",
        "publisher": "Journal of Medical Informatics",
        "title": "Applications of Machine Learning in Healthcare: A Systematic Review",
        "url": "https://doi.org/10.1234/jmi.2023.123456",
        "authors": [
            "Smith, J.",
            "Johnson, M."
        ],
        "doi": "10.1234/jmi.2023.123456"
    }
}


[INFO] 2026-01-19T07:49:45.710Z b841bfde-2202-4758-bf53-c06db192fc4c Lambda invoked with event: {"action": "add_citation", "parameters": {"citation_type": "journal", "publication_date": "2023", "publisher": "Journal of Medical Informatics", "title": "Applications of Machine Learning in Healthcare: A Systematic Review", "url": "https://doi.org/10.1234/jmi.2023.123456", "authors": ["Smith, J.", "Johnson, M."], "doi": "10.1234/jmi.2023.123456"}}
2026-01-19T07:49:45.712Z
END RequestId: b841bfde-2202-4758-bf53-c06db192fc4c
2026-01-19T07:49:45.712Z
REPORT RequestId: b841bfde-2202-4758-bf53-c06db192fc4c Duration: 1.90 ms Billed Duration: 105 ms Memory Size: 256 MB Max Memory Used: 37 MB Init Duration: 102.39 ms XRAY TraceId: 1-696de219-4c5164b7028d20ee266362ee Sampled: true
2026-01-19T07:49:48.112Z
START RequestId: f20fc982-9c63-468e-83e4-2a57e9699b5f Version: $LATEST
2026-01-19T07:49:48.112Z
[INFO]	2026-01-19T07:49:48.112Z	f20fc982-9c63-468e-83e4-2a57e9699b5f	Lambda invoked with event: 
{
    "action": "get_citation",
    "parameters": {
        "format": "apa",
        "citation_id": "cite_2218"
    }
}
```

### Creating an MCP Server
Expose your research tools as an MCP server that can be used by other applications (Claude Desktop, IDEs, etc.).

**Key Concepts:**
- MCP server protocol
- Tool exposure via MCP
- Resource management
- Integration with desktop applications

### What is an MCP Server?

An MCP (Model Context Protocol) server allows you to expose tools and resources to MCP clients like:
- Claude Desktop app
- IDEs with MCP support
- Other AI applications

### Implementation

The MCP server exposes your research tools through the Model Context Protocol: Copy ~/agent-experiments/multi-agent-research-workshop/tutorials/04-research-tools/tools/mcp_server/summary_mcp_server.py to ~/agentcore-workshop/agents_and_tools/tools

### Inspecting and Testing the MCP Server

Before deploying to AgentCore, verify your MCP server works correctly:

#### 1. Install FastMCP

```bash
cd ~/agentcore-workshop/agents_and_tools/tools

# Install fastmcp
uv add fastmcp
```

#### 2. Test MCP Server Tools

Open a new terminal and test the server using the MCP Inspector:

```bash
# run MCP Inspector (if not already installed)
npx @modelcontextprotocol/inspector uv run python ~/agentcore-workshop/agents_and_tools/tools/summary_mcp_server.py

```

A web interface opens (usually http://localhost:6274) where you can:
- View all available tools and their schemas
- Test tool invocations interactively
- View resources exposed by the server
- See request/response logs

### Deploying MCP Server to AgentCore Gateway

You can deploy an MCP server as a gateway target, allowing agents to access it through the AgentCore Gateway.

#### Step 1: Deploy FastMCP Server to AgentCore

AgentCore supports deploying FastMCP servers using the MCP protocol:

**Prerequisites:**

**Deploy to AgentCore:**

```bash
cd ~/agentcore-workshop/agents_and_tools/tools
# Configure and deploy the MCP server with MCP protocol
agentcore configure \
  --entrypoint summary_mcp_server.py \
  --protocol MCP \
  --name paper_summaries_mcp \
  --region ap-southeast-2

# This will:
# 1. Package your FastMCP server
# 2. Deploy it to AgentCore Runtime
# 3. Make it accessible via HTTP endpoint with MCP protocol support
```

**Verify deployment:**

```bash
# Check the deployment status
agentcore status --name paper_summaries_mcp --region ap-southeast-2

# Get the MCP server endpoint
agentcore get-agent-runtime-endpoint \
    --name paper-summaries-mcp \
    --region ap-southeast-2
```

**Test the deployed MCP server:**

```bash
# Invoke the MCP server via AgentCore
agentcore invoke \
    --name paper-summaries-mcp \
    --region ap-southeast-2 \
    --input '{
        "tool": "add_paper_summary",
        "arguments": {
            "title": "Machine Learning in Healthcare",
            "authors": ["Smith, J.", "Doe, A."],
            "url": "https://example.com/paper",
            "summary": "This paper explores ML applications in healthcare."
        }
    }'

# List all summaries
agentcore invoke \
    --name paper-summaries-mcp \
    --region ap-southeast-2 \
    --input '{"tool": "list_summaries", "arguments": {}}'

# Search summaries
agentcore invoke \
    --name paper-summaries-mcp \
    --region ap-southeast-2 \
    --input '{
        "tool": "search_summaries",
        "arguments": {"query": "healthcare"}
    }'
```

#### Step 2: Register MCP Server as Gateway Target

Once deployed via AgentCore, register the MCP server with the gateway:

```bash
# Get the MCP server endpoint
MCP_ENDPOINT=$(agentcore get-agent-runtime-endpoint \
    --name paper-summaries-mcp \
    --region ap-southeast-2 \
    --query 'endpoint' \
    --output text)

# Set gateway variables (from earlier sections)
GATEWAY_ARN="<your-gateway-arn>"
GATEWAY_URL="<your-gateway-url>"
GATEWAY_ROLE="<your-gateway-role-arn>"

# Register MCP server as gateway target
agentcore gateway create-mcp-gateway-target \
    --gateway-arn "$GATEWAY_ARN" \
    --gateway-url "$GATEWAY_URL" \
    --role-arn "$GATEWAY_ROLE" \
    --name paper-summaries-mcp-target \
    --target-type mcp \
    --region ap-southeast-2 \
    --target-payload "{
        \"mcpServerUrl\": \"${MCP_ENDPOINT}\",
        \"transport\": \"http\"
    }"
```

**Verify gateway registration:**

```bash
# List gateway targets
agentcore gateway list-mcp-gateway-targets \
    --gateway-arn "$GATEWAY_ARN" \
    --region ap-southeast-2

# Test MCP server through gateway
agentcore gateway invoke-mcp-gateway-target \
    --gateway-arn "$GATEWAY_ARN" \
    --target-name paper-summaries-mcp-target \
    --region ap-southeast-2 \
    --input '{
        "tool": "search_summaries",
        "arguments": {"query": "healthcare"}
    }'
```

#### Step 3: Configure Agent to Use MCP Gateway Target

Update your agent configuration to use the MCP gateway target:

```python
# In your agent code
from strands.agent import Agent
from strands.mcp import MCPClient
from strands_aws.auth import aws_iam_streamablehttp_client

# Configure MCP Gateway client
mcp_gateway_client = MCPClient(
    lambda: aws_iam_streamablehttp_client(
        endpoint=GATEWAY_URL,
        aws_region="ap-southeast-2",
        aws_service="bedrock-agentcore"
    )
)

# Add to agent tools
agent = Agent(
    tools=[mcp_gateway_client, ...],
    ...
)
```

**Note**: MCP server deployment requires the server to be continuously running, unlike Lambda which is serverless. For production workloads, consider deploying the MCP server as a containerized service (ECS/EKS) or using Lambda with Function URLs for event-driven MCP servers.

## Tool Comparison

| Tool Type | Use Case | Complexity | Deployment |
|-----------|----------|------------|------------|
| **Built-in** (Browser) | Web search, scraping | Low | None - included |
| **Code annotation** @tool | Domain-specific logic | Low | Package with agent |
| **Lambda** | Stateless operations | Medium | Deploy to AWS + Gateway |
| **OpenAPI** | REST APIs | Medium | Deploy API + Gateway |
| **MCP Gateway** (APIs) | External services | High | Gateway + IAM Config |


## Best Practices

### Tool Design
1. **Single Responsibility** - Each tool should do one thing well
2. **Clear Interfaces** - Well-defined inputs and outputs
3. **Error Handling** - Graceful failures with helpful messages
4. **Documentation** - Docstrings for agent understanding

### Performance
1. **Caching** - Cache expensive operations
2. **Async Operations** - Use async/await for I/O
3. **Timeouts** - Set reasonable timeouts for external calls
4. **Rate Limiting** - Respect API limits

### Security
1. **Input Validation** - Validate all tool inputs
2. **API Keys** - Use AgentCore Identity for secrets
3. **Sandboxing** - Use AgentCore Code Interpreter for unsafe code
4. **Audit Logging** - Log tool usage with AgentCore Observability


### MCP Server Best Practices

1. **Tool Naming** - Use clear, descriptive names (e.g., `add_citation` not `add`)
2. **Input Schemas** - Define strict JSON schemas for validation
3. **Error Handling** - Return helpful error messages
4. **Resources** - Expose data as MCP resources for efficient access
5. **Logging** - Log tool calls for debugging

### MCP Resources

In addition to tools, you can expose resources (documents, data):

```python
@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """List available resources"""
    return [
        types.Resource(
            uri="citation://bibliography",
            name="Research Bibliography",
            description="All research citations",
            mimeType="application/json"
        )
    ]

@server.read_resource()
async def handle_read_resource(uri: str) -> str:
    """Read a resource by URI"""
    if uri == "citation://bibliography":
        citations = citation_manager.get_all()
        return json.dumps(citations, indent=2)

    raise ValueError(f"Unknown resource: {uri}")
```

## Destroy gateway and agents

agentcore gateway delete-mcp-gateway  --region ap-southest-2 --arn "arn:aws:bedrock-agentcore:ap-southeast-2:872970450826:gateway/research-tool-gateway-2bvt3xmrkn"

## Next Steps

- **Tutorial 05**: Memory Integration - Persist tool results
- **Tutorial 06**: RAG Implementation - Combine tools with knowledge retrieval
- **Advanced**: Build custom MCP servers for your APIs

## Resources

- [AgentCore Browser Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-browser.html)
- [MCP Protocol Specification](https://spec.modelcontextprotocol.io/)
- [Strands Tools Guide](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/tools/)
- [AgentCore Best Practices](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-best-practices.html)

## Support

For issues or questions:
- Check the [AgentCore Starter Kit Examples](https://github.com/aws-samples/amazon-bedrock-agentcore-starter-kit)
- Review [Common Patterns](../common-patterns.md)
- Join the [AgentCore Community](https://github.com/aws/amazon-bedrock-agentcore/discussions)
