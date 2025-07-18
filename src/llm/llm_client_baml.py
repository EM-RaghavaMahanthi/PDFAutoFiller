import os
from typing import Optional
from baml_py import ClientRegistry
from src.utils.logger import logger

def make_llm_registry(
    provider: str,
    *,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    region: Optional[str] = None,
    profile: Optional[str] = None,
    api_key_env: str = "OPENAI_API_KEY",
    set_primary: bool = True
) -> ClientRegistry:
    """
    Returns a ClientRegistry with the selected LLM provider/model set as primary.
    Supported providers: "openai", "aws-bedrock"

    Args:
        provider: "openai" or "aws-bedrock"
        model: Model string (e.g., "gpt-4o", "anthropic.claude-3-7-sonnet-20250219-v1:0")
        temperature: float (optional)
        max_tokens: int (optional, Bedrock only)
        region: str (Bedrock only, e.g., "us-east-2")
        profile: str (Bedrock only, e.g., "default")
        api_key_env: str (name of env var for OpenAI key)
        set_primary: bool (call set_primary on created client)

    Returns:
        ClientRegistry ready to use in BAML calls.
    """
    cr = ClientRegistry()
    client_name = None

    # OpenAI setup
    if provider == "openai":
        client_name = "OpenAIClient"
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise RuntimeError(f"Environment variable {api_key_env} not set.")
        options = {
            "model": model or "gpt-4o",
            "temperature": temperature if temperature is not None else 0.0,
            "api_key": api_key
        }
        cr.add_llm_client(
            name=client_name,
            provider="openai",
            options=options
        )
    # AWS Bedrock setup
    elif provider == "aws-bedrock":
        client_name = "BedrockClaudeClient"
        options = {
            "model": model or "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
            "region": region or "us-east-2",
            "profile": profile or "default",
            "inference_configuration": {
                "max_tokens": max_tokens if max_tokens is not None else 20000,
                "temperature": temperature if temperature is not None else 0.0
            }
        }
        cr.add_llm_client(
            name=client_name,
            provider="aws-bedrock",
            options=options
        )
    else:
        raise ValueError(f"Unsupported provider: {provider}")

    if set_primary and client_name:
        logger.info(f"We are using the client [{client_name}] from registry")
        cr.set_primary(client_name)

    return cr
