"""LangGraph chatbot with BYOK (Bring Your Own Key) multi-provider support."""

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import SystemMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_xai import ChatXAI
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages, BaseMessage
from pydantic import Field
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row
from langgraph.checkpoint.postgres import PostgresSaver

from .config import settings

# Use the checkpoint Postgres URI (raw psycopg, not SQLAlchemy)
_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=settings.checkpoint_postgres_uri,
            min_size=1,
            max_size=4,
            kwargs={"autocommit": True, "row_factory": dict_row, "connect_timeout": 10},
        )
    return _pool


pool = _get_pool()
checkpointer = PostgresSaver(pool)
with pool.connection() as conn:
    checkpointer.setup()


class chatState(TypedDict):
    question: str
    messages: Annotated[list[BaseMessage], add_messages]
    user_api_key: str
    provider: str


def ChatNode(state: chatState) -> chatState:
    user_key = state.get("user_api_key")
    provider = state.get("provider")

    # --- DYNAMIC MODEL INITIALIZATION ---
    if provider == "gemini":
        model = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash", google_api_key=user_key
        )
    elif provider == "openai":
        model = ChatOpenAI(model="gpt-4o-mini", openai_api_key=user_key)
    elif provider == "grok":
        model = ChatXAI(model="grok-3", xai_api_key=user_key)
    else:
        error_msg = AIMessage(content="Error: Unsupported AI provider selected.")
        return {"messages": [error_msg]}

    history = state.get("messages", [])
    question_desc = state.get("question")

    system_prompt = f"""You are an elite DSA tutor for InsightsDSA. 
    Never give the direct answer or only if explicitly asked and begged for, until then Only give hints.
    Here is the problem:
    {question_desc}"""

    sys_msg = SystemMessage(content=system_prompt)
    messages_for_llm = [sys_msg] + history
    response = model.invoke(messages_for_llm)
    return {"messages": [response]}


graph = StateGraph(state_schema=chatState)
graph.add_node("ChatNode", ChatNode)
graph.add_edge(START, "ChatNode")
graph.add_edge("ChatNode", END)
chatbot = graph.compile(checkpointer=checkpointer)
