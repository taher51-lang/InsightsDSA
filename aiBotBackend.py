from langgraph.graph import StateGraph,START,END
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import SystemMessage,HumanMessage,AIMessage
from langchain_huggingface import HuggingFaceEndpoint,ChatHuggingFace
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_xai import ChatXAI
from typing import TypedDict,Annotated
from langgraph.graph.message import add_messages,BaseMessage
from pydantic import Field
from db import pool # Import the actual pool object
from langgraph.checkpoint.postgres import PostgresSaver

# Give LangGraph the whole valet service
checkpointer = PostgresSaver(pool)

# This sets up the 'checkpoints' tables automatically
with pool.connection() as conn:
    checkpointer.setup()
class chatState(TypedDict):
    question: str = Field(description="This is the DSA question description")
    messages : Annotated[list[BaseMessage],add_messages]
    user_api_key: str  # Added for BYOK
    provider: str      # Added to switch between Gemini/OpenAI
def ChatNode(state: chatState) -> chatState:
    user_key = state.get("user_api_key")
    provider = state.get("provider")

    # --- DYNAMIC MODEL INITIALIZATION ---
    if provider == 'gemini':
        model = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash", 
            google_api_key=user_key
        )
    elif provider == 'openai':
        model = ChatOpenAI(
            model="gpt-4o-mini", 
            openai_api_key=user_key
        )
    elif provider == 'grok':
        model = ChatXAI(
            model="grok-3", 
            xai_api_key=user_key
        )
    else:
        # Fallback or error handling
        print("Unsupported")
        error_msg = AIMessage(content="Error: Unsupported AI provider selected.")
        return {"messages": [error_msg]}
    history = state.get("messages", [])
    question_desc = state.get("question")
    
    # Create the System instructions dynamically
    system_prompt = f"""You are an elite DSA tutor for InsightsDSA. 
    Never give the direct answer. Only give hints.
    Here is the problem:
    {question_desc}"""
    
    sys_msg = SystemMessage(content=system_prompt)
    
    # The LLM gets the instructions + the strict BaseMessage history
    messages_for_llm = [sys_msg] + history
    response = model.invoke(messages_for_llm)
    return {'messages': [response]}
graph = StateGraph(state_schema=chatState)
graph.add_node('ChatNode',ChatNode)
graph.add_edge(START,'ChatNode')
graph.add_edge('ChatNode',END)  
# checkpointer = InMemorySaver()
chatbot = graph.compile(checkpointer=checkpointer)
