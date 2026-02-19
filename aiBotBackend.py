from langgraph.graph import StateGraph,START,END
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.prompts import PromptTemplate
from langchain_huggingface import HuggingFaceEndpoint,ChatHuggingFace
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_xai import ChatXAI
from typing import TypedDict,Annotated
from langchain_core.output_parsers import StrOutputParser
from langchain_ollama import ChatOllama

class chatState(TypedDict):
    user_input: str
    question :str
    bot_response: str
def ChatNode(state: chatState) -> chatState:
    user_input = state["user_input"]
    question = state["question"]
    model =  ChatOllama(model="ministral-3:3b")
    prompt = PromptTemplate(
        input_variables=["user_input","question"],
        template="You are a helpful DSA academic assistant. Respond to the user's input and guide them through this question's solving appproach WITHOUT GIVING FULL CODE, RESPOND IN HTML TAGS INSTEAD OF MARKDOWN : {question}\nUser: {user_input}")
    chain = prompt| model | StrOutputParser()
    response = chain.invoke({'user_input': user_input,'question': question})
    return {'bot_response':response}
graph = StateGraph(state_schema=chatState)
graph.add_node('ChatNode',ChatNode)
graph.add_edge(START,'ChatNode')
graph.add_edge('ChatNode',END)  
checkpointer = InMemorySaver()
chatbot = graph.compile(checkpointer=checkpointer)
