from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_xai import ChatXAI
from langchain_core.messages import HumanMessage
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

class CoachSchema(BaseModel):
    diagnostic: str = Field(..., description="2 sentences analyzing their strengths and weaknesses based on the data.")
    predictor: str = Field(..., description="2 sentences predicting their interview readiness for top tech roles.")

class InsightCoach:
    def __init__(self, api_key, provider):
        self.api_key = api_key
        self.provider = provider.lower()
        self.model = self._initialize_model()

    def _initialize_model(self):
        if self.provider == "openai":
            base = ChatOpenAI(model="gpt-4o-mini", openai_api_key=self.api_key, timeout=20)
        elif self.provider == "gemini":
            base = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=self.api_key, timeout=20)
        elif self.provider == "grok":
            base = ChatXAI(model="grok-3", xai_api_key=self.api_key, timeout=20)
        else:
            return None

        # Bind the new Coach schema!
        return base.with_structured_output(CoachSchema)

    def get_summary(self, stats_string):
        if not self.model: 
            return None
        
        system_prompt = f"""You are an elite, brutally honest Senior Engineering Manager evaluating a candidate's DSA progress. 
        Analyze this user's data: {stats_string}
        
        Rules:
        1. Diagnostic: Point out exactly what they are good at and what they are failing at. Name the concepts.(Do not use demotivating tone)
        2. Predictor: Tell them exactly how they would fare in a FAANG interview right now. Be specific, name drop companies if applicable (e.g., "Ready for Amazon, but Meta will crush you on Graphs").
        3. Do NOT use markdown. Write plain, punchy text.
        4. Add few motivative sentences at the end according to the data(e.g consistency)
        5. 
        """
        try:
            return self.model.invoke(system_prompt)
        except Exception as e:
            print(f"Coach AI Error: {e}")
            return None