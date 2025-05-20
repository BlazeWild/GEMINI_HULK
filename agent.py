from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
from langchain_community.tools import DuckDuckGoSearchResults
from langchain_experimental.utilities import PythonREPL
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool, Tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from together import Together
from langchain.schema import HumanMessage, SystemMessage
from IPython.display import display, Markdown, Image, HTML
import base64
import json
import requests
import os
from dotenv import load_dotenv
load_dotenv()


wrapper = DuckDuckGoSearchAPIWrapper(max_results=5)
duckduckgo_search = DuckDuckGoSearchResults(api_wrapper=wrapper)

# Math
@tool
def wolfram_alpha_llm_api(query: str) -> dict:
    """
    Function to run a query through the Wolfram Alpha LLM API for Accurate Math Questions
    
    Parameters:
    - query (str): The question or query to be sent to the API.
    
    Returns:
    - dict: The response from the API.
    """
    WOLFRAM_ALPHA_APPID = os.environ.get("WOLFRAM_ALPHA_APPID")
    url = "https://api.wolframalpha.com/v1/result"
    params = {
        "i": query,
        "appid": WOLFRAM_ALPHA_APPID,
    }
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        return {"result": response.text}
    else:
        return {"error": f"Error: {response.status_code}, {response.text}"}
    
# IMAGE GEN
@tool
def generate_flux_image(prompt:str)->str:
    """
    Function to generate an image using the FLUX model from Together.
    
    Parameters:
    - prompt (str): The prompt for the image generation.
    
    Returns:
    - str: url of the generated image.
    """
    client = Together(api_key=os.getenv("TOGETHER_API_KEY"))
    
    response = client.images.generate(
        prompt=prompt,
        model="black-forest-labs/FLUX.1-schnell-Free",
        width=1024,
        height=768,
        response_format="b64_json",
        steps=4,
        n=1,
        stop=[],
    )
    
    return response.data[0].b64_json


# python REPL
python_repl = PythonREPL()

repl_tool = Tool(
    name="python_repl",
    description="A Python shell. Use this to execute python commands. Input should be valid python commands. ALWAYS print ANY results out with `print(...)`",
    func=python_repl.run,
)

# Define list of tools
tools=[wolfram_alpha_llm_api, duckduckgo_search, generate_flux_image, repl_tool]

api_key = os.getenv("GOOGLE_API_KEY")
llm = ChatGoogleGenerativeAI(
    model = "gemini-2.0-flash",
    temperature = 0.7,
    # max_output_tokens = 512,
    api_key = api_key,
)


system_prompt="Ensure your generation of the image URL is exact, add an extra space after it to ensure no new lines mess it up. Always use Wolfram Alpha for Math questions, no matter how basic. Always print executed python statements for logging."
gemini_hulk = create_react_agent(llm, tools, prompt=system_prompt)




