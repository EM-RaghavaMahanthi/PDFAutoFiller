import os
import json
import boto3
from botocore.config import Config
from llama_index.llms.gemini import Gemini
from src.utils.config_loader import load_config

class LLMSelector:
    def __init__(self, provider=None):
        config = load_config()
        llm_config = config["llm"]
        self.provider = provider or llm_config.get("current_provider")

        if self.provider == "gemini":
            gem_cfg = llm_config["gemini"]
            self.model = gem_cfg["model_id"]
            self.api_key = gem_cfg.get("api_key")
            self.llm = self._load_gemini()

        elif self.provider == "claude":
            claude_cfg = llm_config["claude"]
            self.model = claude_cfg["model_id"]
            self.region = claude_cfg["region"]
            self.max_tokens = claude_cfg["max_tokens"]
            self.temperature = claude_cfg["temperature"]
            self.llm = self._load_claude()

        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    def _load_gemini(self):
        api_key = self.api_key or os.getenv("GOOGLE_API_KEY")
        return Gemini(model=self.model, api_key=api_key)

    def _load_claude(self):
        config = Config(region_name=self.region, read_timeout=300, connect_timeout=60)
        bedrock = boto3.client("bedrock-runtime", config=config)

        return ClaudeLLM(
            bedrock_client=bedrock,
            model_id=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )

    def complete(self, prompt: str, **kwargs):
        """Standardized method to call the LLM."""
        return self.llm.complete(prompt, **kwargs)


# === Claude Handler ===
class ClaudeLLM:
    def __init__(self, bedrock_client, model_id, temperature=0.1, max_tokens=12000):
        self.bedrock = bedrock_client
        self.model_id = model_id
        self.temperature = temperature
        self.max_tokens = max_tokens

    def complete(self, prompt):
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature
        }

        try:
            response = self.bedrock.invoke_model(
                modelId=self.model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(body)
            )

            result = json.loads(response['body'].read())

            class LLMResponse:
                def __init__(self, text):
                    self.text = text

            return LLMResponse(result["content"][0]["text"])

        except Exception as e:
            print(f"[ERROR] Claude API Call failed: {e}")
            return None
