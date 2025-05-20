from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import MessagesState, StateGraph, START, END
from IPython.display import display, Markdown, Image, HTML
from typing_extensions import Literal
from gemini_hulk.utils.tools import wolfram_alpha_llm_api, generate_flux_image, repl_tool, duckduckgo_search

import base64
import json
import requests
import os
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
llm = ChatGoogleGenerativeAI(
    model = "gemini-2.0-flash",
    temperature = 0.7,
    # max_output_tokens = 2000,
    api_key = api_key,
)
# Define list of tools
tools=[wolfram_alpha_llm_api, duckduckgo_search, generate_flux_image, repl_tool]
tools_by_name = {tool.name: tool for tool in tools}
llm_with_tools = llm.bind_tools(tools)


system_prompt="Ensure your generation of the image URL is exact, add an extra space after it to ensure no new lines mess it up. Always use Wolfram Alpha for Math questions, no matter how basic. Always print executed python statements for logging."
#Nodes
def llm_call(state: MessagesState):
    """_summary_

    Args:
        state (MessagesState): _description_
    """
    return {
        "messages":[
            llm_with_tools.invoke(
                [SystemMessage(content=system_prompt)]
                + state["messages"]
            )
        ]
    }
    
def tool_node(state: dict):
    """Performs the tool call."""
    result = []
    for tool_call in state["messages"][-1].tool_calls:
        tool = tools_by_name[tool_call["name"]]
        observation = tool.invoke(tool_call["args"])
        result.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))
    return {"messages": result}

def should_continue(state: MessagesState) -> Literal["Action", "END"]:
    """
    Decide if we should continue the loop or stop based on
    whether the LLM made a tool call.
    """
    messages = state["messages"]
    last_message = messages[-1]

    if last_message.tool_calls:
        return "Action"
    return "END"

agent_builder = StateGraph(MessagesState)
agent_builder.add_node("Agent", llm_call)
agent_builder.add_node("Tools", tool_node)
agent_builder.add_edge(START, "Agent")
agent_builder.add_conditional_edges(
    "Agent",
    should_continue,
    {
        "Action": "Tools",
        "END": END,
    }
)
agent_builder.add_edge("Tools", "Agent")


gemini_hulk = agent_builder.compile()




