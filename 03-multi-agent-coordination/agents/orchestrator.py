"""
Orchestrator Agent - A2A Server

This agent coordinates the research workflow using a2a protocol by:
1. Determining if a query needs specialist help
2. Delegating to the Search Specialist via cloud-agnostic a2a protocol
3. Handling simple queries directly

When deployed with --protocol A2A, AgentCore Runtime automatically:
- Serves the agent on port 9000
- Generates Agent Card at /.well-known/agent-card.json
- Handles JSON-RPC 2.0 protocol
"""

from strands import Agent, tool
from strands.multiagent.a2a import A2AServer
import uvicorn
from fastapi import Request
from fastapi.responses import RedirectResponse, JSONResponse
import os
from uuid import uuid4
import httpx
import logging

# Import A2A client components for agent-to-agent communication
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import Message, Part, Role, TextPart
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse

# Import AWS SigV4 authentication
import boto3
from aws_requests_auth.aws_auth import AWSRequestsAuth
from urllib.parse import urlparse

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SigV4HttpxAuth(httpx.Auth):
    """httpx Auth class using aws-requests-auth for proper SigV4 signing"""

    def __init__(self, service_name: str = "bedrock-agentcore"):
        """
        Initialize SigV4 auth using aws-requests-auth

        Args:
            service_name: AWS service name for signing (default: bedrock-agentcore)
        """
        self.service_name = service_name
        # Get AWS credentials from boto3 session
        session = boto3.Session()
        self.credentials = session.get_credentials()
        # Get region from the session
        self.region = session.region_name or os.environ.get('AWS_REGION', 'ap-southeast-2')
        self.aws_host = None  # Will be set per-request

        if not self.credentials:
            logger.error("NO CREDENTIALS FOUND! Check your AWS configuration.")

    def auth_flow(self, request):
        """Sign the request with SigV4 using aws-requests-auth"""
        # Parse the URL to get the host and region
        parsed_url = urlparse(str(request.url))
        hostname = parsed_url.hostname or ""

        # SigV4 signing only applies to the deployed AgentCore Runtime endpoint
        # (bedrock-agentcore.{region}.amazonaws.com). Local dev servers
        # (localhost / 127.0.0.1) need no signing — sending the request unsigned
        # avoids passing aws_host=None into AWSRequestsAuth, which would raise
        # "can only concatenate str (not NoneType) to str".
        if 'amazonaws.com' not in hostname:
            yield request
            return

        # Extract region from the AWS endpoint hostname
        # Format: bedrock-agentcore.{region}.amazonaws.com
        parts = hostname.split('.')
        if len(parts) >= 3:
            self.region = parts[1]  # Extract region
        self.aws_host = hostname

        # Create aws-requests-auth object
        aws_auth = AWSRequestsAuth(
            aws_access_key=self.credentials.access_key,
            aws_secret_access_key=self.credentials.secret_key,
            aws_token=self.credentials.token if self.credentials.token else None,
            aws_host=self.aws_host,
            aws_region=self.region,
            aws_service=self.service_name
        )

        # Convert httpx request to requests-compatible format for signing
        # aws-requests-auth uses the requests library signing approach
        import requests
        from requests.models import PreparedRequest

        # Create a PreparedRequest for signing
        prep_request = PreparedRequest()
        prep_request.method = request.method
        prep_request.url = str(request.url)
        prep_request.headers = dict(request.headers)

        # Add body if present
        if request.content:
            prep_request.body = request.content
        else:
            prep_request.body = None

        # Apply AWS auth to the prepared request
        aws_auth(prep_request)

        # Copy signed headers back to httpx request
        request.headers.clear()
        for key, value in prep_request.headers.items():
            request.headers[key] = value

        yield request

# Use the complete runtime URL from environment variable, fallback to local
runtime_url = os.environ.get('AGENTCORE_RUNTIME_URL', 'http://127.0.0.1:9000/')

# Get Search Specialist URL from environment variable
# This can be any a2a-compliant endpoint (AWS, GCP, Azure, on-prem, etc.)
SEARCH_SPECIALIST_URL = os.environ.get('SEARCH_SPECIALIST_URL')

# Global A2A client (initialized once at startup)
_a2a_client = None
_httpx_client = None

async def initialize_a2a_client():
    """Initialize the A2A client once at startup"""
    global _a2a_client, _httpx_client

    if not SEARCH_SPECIALIST_URL:
        logger.warning("SEARCH_SPECIALIST_URL not set - search specialist unavailable")
        return

    try:
        # Create persistent httpx client with SigV4 auth
        _httpx_client = httpx.AsyncClient(
            timeout=300,
            auth=SigV4HttpxAuth(),
            headers={'X-Amzn-Bedrock-AgentCore-Runtime-Session-Id': str(uuid4())}
        )

        # Resolve agent card
        resolver = A2ACardResolver(httpx_client=_httpx_client, base_url=SEARCH_SPECIALIST_URL)
        agent_card = await resolver.get_agent_card()

        # Create A2A client
        config = ClientConfig(
            httpx_client=_httpx_client,
            streaming=False
        )
        factory = ClientFactory(config)
        _a2a_client = factory.create(agent_card)

        logger.info("A2A client initialized")
    except Exception as e:
        logger.error(f"Failed to initialize A2A client: {e}", exc_info=True)

@tool
async def search_specialist(query: str) -> str:
    """
    Delegate search queries to the Search Specialist agent via A2A protocol.

    Use this tool when the user asks for research, web searches, or current information.

    Args:
        query: The search query or research question

    Returns:
        Search results and analysis from the specialist
    """
    # The one-shot startup init can fail (e.g. IAM permissions not yet
    # propagated at cold start), leaving _a2a_client None. Retry lazily here so
    # the agent self-heals once permissions are in place instead of staying
    # permanently "not configured".
    if not _a2a_client:
        logger.info("A2A client not initialized; retrying initialization now")
        await initialize_a2a_client()
    if not _a2a_client:
        return "Error: Search specialist not configured. Check logs for initialization errors."

    try:
        # Build message
        msg = Message(
            kind="message",
            role=Role.user,
            parts=[Part(TextPart(kind="text", text=query))],
            message_id=uuid4().hex,
        )

        # Send message and get response
        async for event in _a2a_client.send_message(msg):
            # Handle Message response
            if isinstance(event, Message):
                response_text = event.model_dump_json(exclude_none=True, indent=2)
                if response_text:
                    return response_text
                else:
                    return "Error: Empty response"

            # Handle (Task, UpdateEvent) tuple response
            elif isinstance(event, tuple) and len(event) == 2:
                task, update_event = event
                return task
            else:
                return "Error: No response received from search specialist"

    except Exception as e:
        logger.error(f"Error calling search specialist: {str(e)}", exc_info=True)
        return f"Error calling search specialist: {str(e)}"

# Create the orchestrator agent
orchestrator = Agent(
    name="Research Orchestrator",
    description="An orchestrator agent that routes queries and delegates to specialist agents",
    model="au.anthropic.claude-haiku-4-5-20251001-v1:0",
    system_prompt="""You are a research orchestrator. Your role is to:

    1. Analyze incoming queries
    2. For SIMPLE questions (greetings, basic facts), answer directly
    3. For RESEARCH questions (requiring web search, current information),
       use the search_specialist tool
    4. Always provide clear, helpful responses

    Examples:
    - "Hello" -> Answer directly
    - "What is 2+2?" -> Answer directly
    - "What are recent developments in AI agents?" -> Use search_specialist tool
    - "Find information about multi-agent systems" -> Use search_specialist tool
    """,
    tools=[search_specialist]
)

# --- Create the Application Wrapper ---

host, port = "0.0.0.0", 9000
# This wraps your agent in a web server so it can receive requests via HTTP.
a2a_server = A2AServer(
    agent=orchestrator,
    http_url=runtime_url,
    serve_at_root=True  # Serves locally at root (/) regardless of remote URL path complexity
)

# Get the A2A server's FastAPI app and add our custom routes
app = a2a_server.to_fastapi_app()

@app.on_event("startup")
async def startup_event():
    """Initialize A2A client when server starts"""
    await initialize_a2a_client()

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

