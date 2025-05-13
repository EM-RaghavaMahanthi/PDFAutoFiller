import os
import json
import numpy as np
from src.utils.logger import logger
from src.utils.config_loader import load_config
from openai import OpenAI

class EmbedModelSelector:
    def __init__(self, embedding_config: dict):
        self.provider = embedding_config.get("current_provider", "huggingface").lower()
        self.full_config = load_config().get("embedding", {})
        print(self.full_config)
        self.provider_config = self.full_config.get(self.provider, {})
        print(self.provider_config)
        self.model_name = self.provider_config.get("model_id")
        self.model = self._load_model()
        logger.info(f"[EmbedModel] Initialized → Provider: {self.provider}, Model: {self.model_name}")

    def _load_model(self):
        if self.provider == "huggingface":
            from sentence_transformers import SentenceTransformer
            return SentenceTransformer(self.model_name)

        elif self.provider == "google":
            from google.generativeai import embed_content
            return embed_content

        elif self.provider == "bedrock":
            import boto3
            return boto3.client("bedrock-runtime")

        elif self.provider == "openai":
            env_var = self.provider_config.get("api_key", "OPENAI_API_KEY")
            api_key = os.getenv(env_var) or self.provider_config.get("api_key")
            if not api_key:
                raise ValueError(f"OpenAI API key not found in env '{env_var}' or config.")
            return OpenAI(api_key=api_key)
        else:
            raise ValueError(f"Unsupported embedding provider: {self.provider}")

    def encode(self, texts: list[str]) -> np.ndarray:
        if self.provider == "huggingface":
            return self.model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)

        elif self.provider == "google":
            return np.array([
                self.model(model=self.model_name, content=text, task_type="retrieval_document")["embedding"]
                for text in texts
            ], dtype="float32")

        elif self.provider == "bedrock":
            return np.array([
                self._get_bedrock_embedding(text)
                for text in texts
            ], dtype="float32")

        elif self.provider == "openai":
            embeddings = []
            for text in texts:
                response = self.model.embeddings.create(
                    model=self.model_name,
                    input=text
                )
                embeddings.append(response.data[0].embedding)
            return np.array(embeddings, dtype="float32")


    def _get_bedrock_embedding(self, text: str) -> list:
        body = {
            "inputText": text,
            "dimensions": 512,
            "normalize": True
        }
        response = self.model.invoke_model(
            modelId=self.model_name,
            contentType="application/json",
            accept="*/*",
            body=json.dumps(body)
        )
        return json.loads(response["body"].read().decode())["embedding"]
