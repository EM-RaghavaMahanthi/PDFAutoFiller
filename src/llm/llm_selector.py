import os
from llama_index.llms.gemini import Gemini

class LLMSelector:
    def __init__(self, provider="gemini", model="models/gemini-1.5-pro", api_key=None):
        self.provider = provider.lower()
        self.model = model
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.llm = self._load_model()

    def _load_model(self):
        if self.provider == "gemini":
            return Gemini(model=self.model, api_key=self.api_key)
        elif self.provider == "openai":
            raise NotImplementedError("OpenAI not yet integrated.")
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    def complete(self, prompt: str, **kwargs):
        """Standardized method to call the LLM."""
        return self.llm.complete(prompt, **kwargs)
