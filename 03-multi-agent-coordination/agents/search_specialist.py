"""
Search Specialist Agent - A2A Server

This agent performs web searches and returns formatted results.
When deployed with --protocol A2A, AgentCore Runtime automatically:
- Serves the agent on port 9000
- Generates Agent Card at /.well-known/agent-card.json
- Handles JSON-RPC 2.0 protocol
"""

import logging
import os
from strands import Agent, tool
from strands.multiagent.a2a import A2AServer
import uvicorn
from fastapi import Request
from fastapi.responses import RedirectResponse

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use the complete runtime URL from environment variable, fallback to local
runtime_url = os.environ.get('AGENTCORE_RUNTIME_URL', 'http://127.0.0.1:9000/')

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

# Create the specialist agent with NullConversationManager for stateless A2A requests
search_agent = Agent(
    name="Search Specialist",
    description="A specialist agent that performs web searches and returns formatted results",
    model="au.anthropic.claude-haiku-4-5-20251001-v1:0",
    system_prompt="""You are a search specialist. Be EXTREMELY brief.

    1. Use web_search tool
    2. List 2-3 bullet points maximum
    3. Include source URLs

    Example response:
    "Found 2 results on [topic]:
    - Key point 1
    - Key point 2

    Sources: [url1], [url2]"

    KEEP IT SHORT.""",
    tools=[web_search],
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
