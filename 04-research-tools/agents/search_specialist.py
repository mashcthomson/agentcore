"""
Search Specialist Agent - A2A Server

This agent performs web searches using a mock search tool and discovers PubMed tools from MCP Gateway.
The mock search tool simulates web search results for testing and demonstrations.

When deployed with --protocol A2A, AgentCore Runtime automatically:
- Serves the agent on port 9000
- Generates Agent Card at /.well-known/agent-card.json
- Handles JSON-RPC 2.0 protocol
"""

import logging
import os
from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client
from strands import Agent, tool
from strands.multiagent.a2a import A2AServer
from strands.tools.mcp import MCPClient
import uvicorn
from fastapi import Request
from fastapi.responses import RedirectResponse

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use the complete runtime URL from environment variable, fallback to local
runtime_url = os.environ.get('AGENTCORE_RUNTIME_URL', 'http://127.0.0.1:9000/')

# Gateway URL from deployment (optional)
GATEWAY_URL = os.environ.get('RESEARCH_GATEWAY_URL')

# AWS Region
AWS_REGION = os.environ.get('AWS_REGION', 'ap-southeast-2')

# Mock search tool for testing (replaces browser)
@tool
def web_search(query: str, max_results: int = 5) -> list:
    """
    Perform a web search and return results.

    NOTE!!!: This is a simulated implementation for workshop demonstration.
    In production, replace with AgentCore Browser for real web searches:
        from bedrock_agentcore.tools import Browser
        browser = Browser()
        results = browser.search(query, max_results=max_results)
        return results

    Args:
        query: Search query string
        max_results: Maximum number of results to return (default: 5)

    Returns:
        List of search results with title, url, and snippet
    """
    # Simulated search results - kept minimal for demo
    return [
        {
            "title": f"Research on {query}",
            "url": f"https://example.com/{i+1}",
            "snippet": "Key findings on this topic."
        }
        for i in range(min(max_results, 2))  # Only 2 results to keep responses short
    ]


# Build tools list with mock search
tools = [web_search]
logger.info("Initialized Mock Web Search tool")

# Add MCP Gateway client if configured
if GATEWAY_URL:
    try:
        logger.info(f"Configuring MCP Gateway client for: {GATEWAY_URL}")
        # Create MCP client to discover tools from gateway using AWS IAM authentication
        # Strands MCPClient wraps the MCP transport (aws_iam_streamablehttp_client)
        # This will automatically discover PubMed and other tools exposed by the gateway
        # Using managed integration (experimental) - connection lifecycle managed automatically
        mcp_gateway_client = MCPClient(lambda: aws_iam_streamablehttp_client(
            endpoint=GATEWAY_URL,
            aws_region=AWS_REGION,
            aws_service="bedrock-agentcore"
        ))
        tools.append(mcp_gateway_client)
        logger.info("✅ MCP Gateway client configured successfully")
        logger.info(f"Agent will have {len(tools)} tool sources: Mock Search + MCP Gateway (PubMed)")
    except Exception as e:
        logger.warning(f"❌ Failed to configure MCP Gateway client: {e}")
        logger.info("Agent will run with Mock Search tool only")
else:
    logger.info("⚠️  RESEARCH_GATEWAY_URL not set. Agent will run with Mock Search tool only")

# Create the specialist agent with mock search and optionally MCP Gateway client
# The agent will discover PubMed tools automatically from the gateway on first use (if configured)
search_agent = Agent(
    name="Search Specialist",
    description="A specialist agent with mock web search and PubMed research capabilities via MCP Gateway",
    model="au.anthropic.claude-haiku-4-5-20251001-v1:0",
    system_prompt="""You are a search specialist with access to research tools.

    you can do web search or academic paper search to fulfil the request.
    
    RESPONSE FORMAT (be concise):
    "Found results on [topic]:
    - Key finding 1 with brief details
    - Key finding 2 with brief details
    - Key finding 3 with brief details

    Sources: [citations or URLs]"

    Always cite sources and indicate if using mock data.""",
    tools=tools,
    callback_handler=None
)

host, port = "0.0.0.0", 9000

# Create A2A server with runtime URL and serve at root
a2a_server = A2AServer(
    agent=search_agent,
    http_url=runtime_url,
    serve_at_root=True  # Serves locally at root (/) regardless of remote URL path complexity
)

# Get the A2A server's FastAPI app and add our custom routes
app = a2a_server.to_fastapi_app()

@app.get("/ping")
def ping():
    return {"status": "healthy"}

@app.post("/invocations")
async def invocations_redirect(request: Request):
    """Redirect /invocations to root for compatibility"""
    return RedirectResponse(url="/", status_code=307)

if __name__ == "__main__":
    # Detect if running in AgentCore (deployed) vs local development
    is_deployed = os.environ.get('AWS_EXECUTION_ENV') is not None
    logger.info(f"Agent is {'deployed' if is_deployed else 'local'} mode")
    uvicorn.run(app, host=host, port=port)
