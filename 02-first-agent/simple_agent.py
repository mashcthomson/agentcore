from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models.anthropic import AnthropicModel

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
        model=AnthropicModel(model_id="claude-haiku-4-5-20251001", max_tokens=1024),
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
