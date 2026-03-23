from langgraph.graph import StateGraph,START,END
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.prompts import PromptTemplate
from langchain_huggingface import HuggingFaceEndpoint,ChatHuggingFace
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_xai import ChatXAI
from typing import TypedDict,Annotated
from langchain_core.output_parsers import StrOutputParser
from langchain_ollama import ChatOllama

class chatState(TypedDict):
    user_input: str
    question: str
    bot_response: str
    user_api_key: str  # Added for BYOK
    provider: str      # Added to switch between Gemini/OpenAI
def ChatNode(state: chatState) -> chatState:
    user_input = state["user_input"]
    question = state["question"]
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
    else:
        # Fallback or error handling
        print("Unsupported")
        return {'bot_response': "Error: Unsupported AI provider."}

    prompt = PromptTemplate(
        input_variables=["user_input", "question"],
        template="""
        You are a helpful DSA academic assistant. 
        Respond to the user's input and guide them through this question's solving approach 
        WITHOUT GIVING FULL CODE.
        
        STRICT RULE: RESPOND ONLY IN HTML TAGS (e.g., <p>, <ul>, <code>) instead of Markdown.
        
        Question Context: {question}
        User Query: {user_input}
        """
    )
    
    chain = prompt | model | StrOutputParser()
    response = chain.invoke({'user_input': user_input, 'question': question})
    return {'bot_response': response}
graph = StateGraph(state_schema=chatState)
graph.add_node('ChatNode',ChatNode)
graph.add_edge(START,'ChatNode')
graph.add_edge('ChatNode',END)  
checkpointer = InMemorySaver()
chatbot = graph.compile(checkpointer=checkpointer)
