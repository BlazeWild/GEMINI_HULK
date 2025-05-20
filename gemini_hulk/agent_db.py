from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool, Tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent, ToolNode
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, BaseMessage, AIMessageChunk
from langgraph.graph import MessagesState, StateGraph, START, END, add_messages
from IPython.display import display, Markdown, Image, HTML
from typing_extensions import Literal
from typing import List, Annotated, Generator
from langgraph.checkpoint.memory import MemorySaver
from gemini_hulk.utils.tools import all_tools
from pydantic import BaseModel
from gemini_hulk.utils.prompt import prompt

from IPython.display import display, Image

import base64
import json
import requests
import os
from dotenv import load_dotenv
load_dotenv()

class GeminiState(BaseModel):
    messages: Annotated[List[BaseMessage], add_messages] = []
    chart_json: str = ""
    image_json: str = ""
    
class Agent:
    """
    Agent class for implementing Langgraph agents.

    Attributes:
        name: The name of the agent.
        tools: The tools available to the agent.
        model: The model to use for the agent.
        system_prompt: The system prompt for the agent.
        temperature: The temperature for the agent.
    """
    def __init__(
        self, 
        name: str,
        tools: List[Tool] = all_tools,
        model:str ="gemini-2.0-flash",
        system_prompt: str = "You are a helpful assistant.",
        temperature: float = 0.7,
    ):
        self.name = name
        self.tools = tools
        self.model = model
        self.system_prompt = system_prompt
        self.temperature = temperature
        
        self.llm = ChatGoogleGenerativeAI(
            model = self.model,
            temperature = self.temperature,
            # max_output_tokens = 2000,
        ).bind_tools(tools)
        self.tools_by_name = {tool.name: tool for tool in tools}
        
        
    def build_graph(self):
        """
        Build the LangGraph application.
        """
        def gemini_node(state: GeminiState):
            response = self.llm.invoke(
                [SystemMessage(content=self.system_prompt)] + state.messages
            )
            state.messages = state.messages + [response]
            return state

        def router(state: GeminiState) -> str:
            last_message = state.messages[-1]
            if last_message.tool_calls:
                return "tools" # Go to tools if LLM asks for them
            else:
                return END    # End if LLM provides a final answer

        # --- FIX STARTS HERE: Correct Indentation ---
        builder = StateGraph(GeminiState) # This line should be here, not inside router
        builder.add_node("gemini", gemini_node)
        builder.add_node("tools", ToolNode(self.tools))

        builder.add_edge(START, "gemini")
        builder.add_conditional_edges(
            "gemini",
            router,
            {
                "tools": "tools",
                END: END,
            }
        )
        builder.add_edge("tools", "gemini") # After tools, go back to Gemini to process output

        self.runnable = builder.compile()
        return self.runnable # Return the compiled graph
    
    def inspect_graph(self):
        """
        Visualize the graph using the mermaid.ink API.
        """
        graph = self.build_graph()
        display(Image(graph.get_graph(xray=True).draw_mermaid_png()))
        
    def invoke(self, message:str, **kwargs)-> str:
        """Synchronously invoke the graph.

        Args:
            message: The user message.

        Returns:
            str: The LLM response.
        """
        result = self.runnable.invoke(
            input = {
                "messages": [HumanMessage(content=message)]
            },
            **kwargs
        )

        return result["messages"][-1].content
    
    def stream(self, message: str, **kwargs) -> Generator[str, None, None]:
        """Synchronously stream the results of the graph run.

        Args:
            message: The user message.

        Returns:
            str: The final LLM response or tool call response
        """
        for message_chunk, metadata in self.runnable.stream(
            input = {
                "messages": [HumanMessage(content=message)]
            },
            stream_mode="messages",
            **kwargs
        ):
            if isinstance(message_chunk, AIMessageChunk):
                if message_chunk.response_metadata:
                    finish_reason = message_chunk.response_metadata.get("finish_reason", "")
                    if finish_reason == "tool_calls":
                        yield "\n\n"

                if message_chunk.tool_call_chunks:
                    tool_chunk = message_chunk.tool_call_chunks[0]

                    tool_name = tool_chunk.get("name", "")
                    args = tool_chunk.get("args", "")

                    
                    if tool_name:
                        tool_call_str = f"\n\n< TOOL CALL: {tool_name} >\n\n"

                    if args:
                        tool_call_str = args
                    yield tool_call_str
                else:
                    yield message_chunk.content
                continue
            

# Define and instantiate the agent 
agent = Agent(
        name="gemini_HULK",
        system_prompt=prompt
        )
gemini_hulk = agent.build_graph()




# gemini_hulk = agent_builder.compile()




