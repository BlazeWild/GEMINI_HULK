from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
from langchain_community.tools import DuckDuckGoSearchResults
from langchain_experimental.utilities import PythonREPL
from langchain_core.tools import tool, Tool
from together import Together
import os
from dotenv import load_dotenv
import requests
import pandas as pd
from sqlalchemy import create_engine, text, Engine
from langgraph.types import Command
from langchain_core.tools.base import InjectedToolCallId
from .env_variables import SUPABASE_URL, GOOGLE_API_KEY, LANGSMITH_API_KEY, TOGETHER_API_KEY, DATABASE_URI
from typing import Annotated
from langchain_core.messages import ToolMessage
import io
from contextlib import redirect_stdout, redirect_stderr

print("GOOGLE_API_KEY", GOOGLE_API_KEY)
print("LANGSMITH_API_KEY", LANGSMITH_API_KEY)
print("TOGETHER_API_KEY", TOGETHER_API_KEY)
print("DATABASE_URI", DATABASE_URI)
print("SUPABASE_URL", SUPABASE_URL)
# Load environment variables
load_dotenv()

# --- ServerSession and DB Tools ---
class ServerSession:
    """A session for server-side state management and operations.
    In practice, this would be a separate service from where the agent is running and the agent would communicate with it using a REST API. In this simplified example, we use it to persist the db engine and data returned from the query_db tool.
    """
    def __init__(self):
        self.engine: Engine = None
        self.df: pd.DataFrame = None
        # You need to define env.SUPABASE_URL or replace it with your actual URL
        # For this example, let's assume it's set up in your environment
        # or replaced by a placeholder.
        # Ensure 'env' is accessible or pass the URL directly.
        # For demonstration, let's use a dummy URL if env is not defined
        supabase_url = SUPABASE_URL
        print(f"Connecting to database at {supabase_url}")
        self.engine = create_engine(
            supabase_url,
            pool_size=5,
            max_overflow=5,
            pool_timeout=10,
            pool_recycle=1800,
            pool_pre_ping=True,
            pool_use_lifo=True,
            connect_args={
                "application_name": "creator",
                "options": "-c statement_timeout=30000",
                "keepalives": 1,
                "keepalives_idle": 60,
                "keepalives_interval": 30,
                "keepalives_count": 3
            }
        )

# Create a global instance of the ServerSession
session = ServerSession()

@tool
def query_db(query: str) -> str:
    """Query the database using Postgres SQL.
    Args:
        query: The SQL query to execute. Must be a valid postgres SQL string that can be executed directly.
    Returns:
        str: The query result as a markdown table.
    """
    try:
        with session.engine.connect().execution_options(
            isolation_level="READ COMMITTED"
        ) as conn:
            result = conn.execute(text(query))
            columns = list(result.keys())
            rows = result.fetchall()
            df = pd.DataFrame(rows, columns=columns)
            session.df = df
            conn.close()
        return df.to_markdown(index=False)
    except Exception as e:
        return f"Error executing query: {str(e)}"

@tool
def generate_visualization(
    name: str,
    sql_query: str,
    plotly_code: str,
    tool_call_id: Annotated[str, InjectedToolCallId]
    ) -> Command: # Return type changed to Command as per your original code
    '''Generate a visualization using Python, SQL, and Plotly. If the visualizaton is successfully generated, it's automatically rendered for the user on the frontend.
    Args:
        name: The name of the visualization. Should be a short name with underscores and no spaces.
        sql_query: The SQL query to retrieve data for the visualization. Must be a valid postgres SQL string that can be executed directly. The query will be executed and the result will be loaded into a DataFrame named 'df'.
        plotly_code: Python code that generates a Plotly figure. The code should create a variable named 'fig' that contains the Plotly figure object.
    Returns:
        Command: A LangGraph Command object if successful, or an error string if unsuccessful.
    ## Assumptions
    Assume the data is already loaded into a DataFrame named 'df' and the following libraries are already imported for immediate use:
    import pandas as pd
    import plotly.express as px
    import plotly.graph_objects as go
    import plotly
    ## Example:
    User asks "Show me the top 5 creators by revenue"
    sql_query = "SELECT c.id, c.first_name, c.last_name, SUM(t.amount_usd) AS total_revenue\nFROM creators c\nJOIN transactions t ON c.id = t.creator_id\nGROUP BY c.id, c.first_name, c.last_name\nORDER BY total_revenue DESC\nLIMIT 5;"
    plotly_code = "fig = px.bar(df, x='first_name', y='total_revenue', title='Top 5 Creators by Revenue')\nfig.update_layout(xaxis_title='Creator', yaxis_title='Total Revenue ($)')"
    '''
    import io
    import os
    from contextlib import redirect_stdout, redirect_stderr

    os.makedirs("output", exist_ok=True)
    file_path = f"output/{name}.json"
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    pre_code = f'''
from sqlalchemy import text
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import plotly
# Generated SQL
df = pd.read_sql(text("""{sql_query}"""), engine)
# Generated plotly code
'''
    post_code = f'''
# Save the figure to JSON
if 'fig' in locals() or 'fig' in globals():
    fig_json = pio.to_json(fig)
    with open('{file_path}', 'w') as f:
        f.write(fig_json)
'''
    code = pre_code + plotly_code + post_code
    exec_globals = {}
    if "engine" in code:
        exec_globals['engine'] = session.engine # Pass the global engine

    try:
        print(f"Executing code: \n\n{code}\n\n")
        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            exec(code, exec_globals, {})

        print(f"STDOUT: \n\n{stdout_capture.getvalue()}\n")
        print(f"STDERR: \n\n{stderr_capture.getvalue()}\n")

        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                fig_json = f.read()
            return Command(
                update={
                    "chart_json": fig_json,
                    "messages": [
                        ToolMessage(
                            "Visualization created successfully.",
                            tool_call_id=tool_call_id
                        )
                    ],
                }
            )
        else:
            raise Exception(f"Error: Failed to generate visualization.\n\n\n{stderr_capture.getvalue()}\n")
    except Exception as e:
        error_message = str(e)
        return f"Error executing visualization code: {error_message}"

wrapper = DuckDuckGoSearchAPIWrapper(max_results=5)
duckduckgo_search = DuckDuckGoSearchResults(api_wrapper=wrapper)

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
    if not WOLFRAM_ALPHA_APPID:
        return {"error": "WOLFRAM_ALPHA_APPID environment variable not set."}
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

@tool
def generate_flux_image(prompt:str)->str:
    """
    Function to generate an image using the FLUX model from Together.
    Parameters:
    - prompt (str): The prompt for the image generation.
    Returns:
    - str: url of the generated image.
    """
    together_api_key = os.getenv("TOGETHER_API_KEY")
    if not together_api_key:
        return "TOGETHER_API_KEY environment variable not set."
    client = Together(api_key=together_api_key)
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

# # Python REPL
# def python_repl(code: str) -> str:
#     """
#     Function to execute Python code in a REPL environment.
#     Args:
#         code: The Python code to execute.
#     Returns:
#         str: The output of the executed code.
#     """
#     python_repl = PythonREPL()
#     with redirect_stdout(io.StringIO()) as stdout, redirect_stderr(io.StringIO()) as stderr:
#         try:
#             python_repl.run(code)
#             return stdout.getvalue() + stderr.getvalue()
#         except Exception as e:
#             return f"Error executing Python code: {str(e)}"
        

python_repl = PythonREPL()
repl_tool = Tool(
    name="python_repl",
    description="A Python shell. Use this to execute python commands. Input should be valid python commands. ALWAYS print ANY results out with `print(...)`",
    func=python_repl.run,
)

# Collect all tools into a list
all_tools = [
    query_db,
    generate_visualization,
    duckduckgo_search,
    wolfram_alpha_llm_api,
    generate_flux_image,
    repl_tool,
]

# Now, `all_tools` is a list of Tool objects that you can pass to your LangChain agent or LangGraph.