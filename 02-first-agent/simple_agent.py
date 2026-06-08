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
        # Newer Claude models require a cross-region inference profile, not a raw
        # model ID. The prefix matches your region AND model generation: in
        # ap-southeast-2, Claude 4.5+ uses `au.` while older 3.x uses `apac.`
        # (`us.`/`eu.` in those regions). Verify with:
        #   aws bedrock list-inference-profiles --region ap-southeast-2
        model="au.anthropic.claude-haiku-4-5-20251001-v1:0",
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
