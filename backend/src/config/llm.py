from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import os

load_dotenv()

class LLM:
    def __init__(self, provider: str = "openai", model: str = None, temperature: float = 0.0):

        self.provider = provider.lower().strip()

        if self.provider == "google":
            self.model = model or "gemini-2.5-pro"
            self.api_key = os.getenv("GOOGLE_API_KEY")
            if not self.api_key:
                raise ValueError("Missing GOOGLE_API_KEY in environment")
            self.client = ChatGoogleGenerativeAI(
                model=self.model,
                temperature=temperature,
                google_api_key=self.api_key,
            )

        elif self.provider == "openai":
            self.model = model or "gpt-4o-mini"
            self.api_key = os.getenv("OPENAI_API_KEY")
            if not self.api_key:
                raise ValueError("Missing OPENAI_API_KEY in environment")
            self.client = ChatOpenAI(
                model=self.model,
                temperature=temperature,
                openai_api_key=self.api_key,
            )

        else:
            raise ValueError(f"Unsupported provider: {provider}")

    def __call__(self, messages):
        """Shortcut so you can call LLM like a function."""
        return self.client.invoke(messages)

    def get_client(self):
        """Return the underlying LangChain chat model instance."""
        return self.client



llm_client = LLM(provider="openai", model="gpt-4o-mini", temperature=0).get_client()
