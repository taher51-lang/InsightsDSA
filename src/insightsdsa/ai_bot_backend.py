import os
from typing import Annotated

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_xai import ChatXAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import Field
from typing_extensions import TypedDict

from .config import settings

_USE_MEMORY = os.getenv("INSIGHTSDSA_USE_MEMORY_CHECKPOINTER", "").lower() in (
    "1",
    "true",
    "yes",
    "on",
)

if _USE_MEMORY:
    from langgraph.checkpoint.memory import MemorySaver

    pool = None
    checkpointer = MemorySaver()
else:
    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg_pool import ConnectionPool

    CHECKPOINT_DB_URI = settings.checkpoint_postgres_uri
    pool = ConnectionPool(
        conninfo=CHECKPOINT_DB_URI,
        min_size=settings.checkpoint_pool_min_size,
        max_size=settings.checkpoint_pool_max_size,
        kwargs={
            "autocommit": False,
            "connect_timeout": settings.checkpoint_connect_timeout,
        },
    )
    migration_setup_connection = pool.getconn()
    migration_checkpointer = PostgresSaver(migration_setup_connection)
    migration_checkpointer.setup()
    pool.putconn(migration_setup_connection)
    checkpointer = PostgresSaver(pool)


class chatState(TypedDict):
    question: str = Field(description="This is the DSA question description")
    messages: Annotated[list[BaseMessage], add_messages]
    user_api_key: str
    provider: str


def ChatNode(state: chatState) -> chatState:
    user_key = state.get("user_api_key")
    provider = state.get("provider")

    if provider == "gemini":
        model = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=user_key,
        )
    elif provider == "openai":
        model = ChatOpenAI(
            model="gpt-4o-mini",
            openai_api_key=user_key,
        )
    elif provider == "grok":
        model = ChatXAI(
            model="grok-3",
            xai_api_key=user_key,
        )
    else:
        print("Unsupported")
        error_msg = AIMessage(content="Error: Unsupported AI provider selected.")
        return {"messages": [error_msg]}
    history = state.get("messages", [])
    question_desc = state.get("question")

    system_prompt = f"""You are an elite DSA tutor for InsightsDSA.
    Never give the direct answer. Only give hints.
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
