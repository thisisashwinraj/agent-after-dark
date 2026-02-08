import os
import logging
import warnings
from dotenv import load_dotenv

from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.planners import BuiltInPlanner
from google.adk.tools import google_search
from google.adk.tools.agent_tool import AgentTool

from google.genai import types

from .callbacks import before_model_callback
from .config import GEMINI_SAFETY_CONFIGURATIONS
from .prompts import GLOBAL_INSTRUCTIONS
from .prompts import ROOT_AGENT_INSTRUCTION, ROOT_AGENT_DESCRIPTION
from .prompts import WEB_SEARCH_AGENT_DESCRIPTION, WEB_SEARCH_AGENT_INSTRUCTION
from .tools import generate_recipe_document


load_dotenv()
warnings.filterwarnings("ignore", category=UserWarning, module=".*pydantic.*")
logger = logging.getLogger(__name__)


web_search_agent = LlmAgent(
    name="web_search_agent",
    model=Gemini(
        model=os.getenv("WEB_SEARCH_AGENT_MODEL"),
        use_interactions_api=False,
        retry_options=types.HttpRetryOptions(initial_delay=1, attempts=2),
    ),
    description=WEB_SEARCH_AGENT_DESCRIPTION,
    instruction=WEB_SEARCH_AGENT_INSTRUCTION,
    tools=[google_search]
)

root_agent = LlmAgent(
    name="recipe_agent",
    model=Gemini(
        model=os.getenv("ROOT_AGENT_MODEL"),
        use_interactions_api=False,
        retry_options=types.HttpRetryOptions(initial_delay=1, attempts=2),
    ),
    description=ROOT_AGENT_DESCRIPTION,
    instruction=ROOT_AGENT_INSTRUCTION,
    include_contents="default",
    generate_content_config=types.GenerateContentConfig(
        temperature=os.getenv("ROOT_AGENT_TEMPERATURE"),
        max_output_tokens=os.getenv("ROOT_AGENT_MAX_TOKENS"),
        seed=os.getenv("ROOT_AGENT_SEED"),
        safety_settings=GEMINI_SAFETY_CONFIGURATIONS,
    ),
    disallow_transfer_to_peers=False,
    disallow_transfer_to_parent=False,
    planner=BuiltInPlanner(
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,
            thinking_budget=os.getenv("ROOT_AGENT_THINKING_BUDGET"),
        )
    ),
    global_instruction=GLOBAL_INSTRUCTIONS,
    tools=[
        AgentTool(agent=web_search_agent),
        generate_recipe_document
    ],
    before_model_callback=before_model_callback,
)
