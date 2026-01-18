from langchain.agents import create_agent
from dotenv import load_dotenv
from typing import Callable

load_dotenv()


def init_agent(
    model: str = "openai",
    tools: list[Callable] = [],
    system_prompt: str = "You are a helpful assistant",
):
    if model == "openai":
        model = "gpt-4.1"
    elif model == "google":
        model = "gemini-2.5-flash-lite"

    return create_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
    )


def run_agent(agent, messages: list[dict]) -> str:
    results = agent.invoke({"messages": messages})
    return results
