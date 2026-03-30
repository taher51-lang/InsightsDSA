from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_xai import ChatXAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from pydantic import Field, BaseModel

# 1. The Schema remains your "Source of Truth"
class AnalystSchema(BaseModel):
    mastery_score: int = Field(..., ge=0, le=5, description="Technical mastery score.")
    clarity_score: int = Field(..., ge=0, le=5, description="Logical flow score.")
    reasoning: str = Field(..., description="Justification.")

class Analyst:
    def __init__(self, api_key, provider):
        self.api_key = api_key
        self.provider = provider.lower()
        # This calls the method below and saves the result to self.model
        self.model = self._initialize_model()

    def _initialize_model(self):
        """Initializes the model with a safety timeout and binds the schema."""
        # We add request_timeout or timeout depending on the provider
        if self.provider == "openai":
            base = ChatOpenAI(model="gpt-4o-mini", openai_api_key=self.api_key, timeout=30)
        elif self.provider == "gemini":
            base = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=self.api_key, timeout=30)
        elif self.provider == "grok":
            base = ChatXAI(model="grok-3", xai_api_key=self.api_key, timeout=30)
        else:
            return None

        # BIND THE SCHEMA HERE: This makes the model return AnalystSchema objects directly
        return base.with_structured_output(AnalystSchema)

    def get_response(self, question_text, transcript):
        """The One-Click Invoke."""
        if not self.model: 
            return None
        
        # Convert message objects to a simple string for the AI to read
        chat_str = "\n".join([f"{'Student' if isinstance(m, HumanMessage) else 'Tutor'}: {m.content}" for m in transcript])
        
        system_prompt = f"""You are a DSA Knowledge Analyst. 
        Analyze the student's understanding of this question: {question_text}
        
        Conversation History:
        {chat_str}
        """

        try:
            # Because we used .with_structured_output, this returns an AnalystSchema object!
            # No parsers or templates required.
            return self.model.invoke(system_prompt)
        except Exception as e:
            print(f"AI Analyst Timeout or Error: {e}")
            return None