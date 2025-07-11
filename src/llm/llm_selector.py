import os
import json
import boto3
from botocore.config import Config
from llama_index.llms.gemini import Gemini
import openai
from src.utils.config_loader import load_config

class LLMSelector:
    def __init__(self, provider=None):
        config = load_config()
        llm_config = config["llm"]
        self.provider = provider or llm_config.get("current_provider")
        self.max_threads = llm_config.get("max_threads",10)

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

        elif self.provider == "llama3":
            llama_cfg = llm_config["llama3"]
            self.model = llama_cfg["model_id"]
            self.region = llama_cfg["region"]
            self.max_tokens = llama_cfg["max_tokens"]
            self.temperature = llama_cfg["temperature"]
            self.top_p = llama_cfg.get("top_p",0.9)
            self.llm = self._load_llama3()

        elif self.provider == "deepseek":
            ds_cfg = llm_config["deepseek"]
            self.model = ds_cfg["model_id"]
            self.region = ds_cfg["region"]
            self.max_tokens = ds_cfg["max_tokens"]
            self.temperature = ds_cfg["temperature"]
            self.top_p = ds_cfg.get("top_p", 1.0)
            self.llm = self._load_deepseek()

        elif self.provider == "openai":
            openai_cfg = llm_config["openai"]
            self.model = openai_cfg["model_id"]
            self.api_key = openai_cfg["api_key"]
            self.temperature = openai_cfg.get("temperature", 0.1)
            self.max_tokens = openai_cfg.get("max_tokens", 2048)
            self.llm = self._load_openai()


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
    
    def _load_llama3(self):
        config = Config(region_name=self.region, read_timeout=300, connect_timeout=60)
        bedrock = boto3.client("bedrock-runtime", config=config)

        return Llama3LLM(
            bedrock_client=bedrock,
            model_id=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            top_p=self.top_p
        )
    
    def _load_deepseek(self):
        config = Config(region_name=self.region, read_timeout=300, connect_timeout=60)
        bedrock = boto3.client("bedrock-runtime", config=config)

        return DeepSeekLLM(
            bedrock_client=bedrock,
            model_id=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            top_p=self.top_p
        )
    
    def _load_openai(self):
        return OpenAILLM(
            model_id=self.model,
            api_key=self.api_key,
            temperature=self.temperature,
            max_tokens=self.max_tokens
    )



    def complete(self, prompt: str, session_messages=None):
        return self.llm.complete(prompt, session_messages=session_messages)


class ClaudeLLM:
    def __init__(self, bedrock_client, model_id, temperature=0.1, max_tokens=20000):
        self.bedrock = bedrock_client
        self.model_id = model_id
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.session_messages = []

    def complete(self, prompt, session_messages=None):
        if session_messages:
            messages = session_messages + [{"role": "user", "content": prompt}]
        else:
            messages = [{"role": "user", "content": prompt}]

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "messages": messages,
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
            content = result["content"][0]["text"]

            if session_messages is not None:
                session_messages.append({"role": "user", "content": prompt})
                session_messages.append({"role": "assistant", "content": content})

            class LLMResponse:
                def __init__(self, text):
                    self.text = text

            return LLMResponse(content)

        except Exception as e:
            print(f"[ERROR] Claude API Call failed: {e}")
            return None



class Llama3LLM:
    def __init__(self, bedrock_client, model_id, temperature=0.5, max_tokens=512, top_p=1.0):
        self.bedrock = bedrock_client
        self.model_id = model_id
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p


    def complete(self, prompt, session_messages=None):
        # Format the prompt in LLaMA 3 instruct format
        formatted_prompt = f"""
<|begin_of_text|><|start_header_id|>user<|end_header_id|>
{prompt}
<|eot_id|>
<|start_header_id|>assistant<|end_header_id|>
"""
        body = {
            "prompt": formatted_prompt,
            "max_gen_len": self.max_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p
        }

        try:
            response = self.bedrock.invoke_model(
                modelId=self.model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(body)
            )
            result = json.loads(response["body"].read())
            return type("LLMResponse", (), {"text": result["generation"]})

        except Exception as e:
            print(f"[ERROR] LLaMA 3 API Call failed: {e}")
            return None

class DeepSeekLLM:
    def __init__(self, bedrock_client, model_id, temperature=0.5, max_tokens=512, top_p=0.9):
        self.bedrock = bedrock_client
        self.model_id = model_id
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p

    def complete(self, prompt, session_messages=None):
        # Proper DeepSeek-R1 prompt format without <think> to get direct answer
        formatted_prompt = f"<｜begin▁of▁sentence｜><｜User｜>{prompt}<｜Assistant｜>"

        body = {
            "prompt": formatted_prompt,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p
        }

        try:
            response = self.bedrock.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json"
            )

            model_response = json.loads(response["body"].read())
            choices = model_response.get("choices", [])
            if not choices:
                raise ValueError("No response choices returned from DeepSeek.")

            choice = choices[0]
            text = choice.get("text", "").strip()
            stop_reason = choice.get("stop_reason", "")

            class LLMResponse:
                def __init__(self, text, stop_reason):
                    self.text = text
                    self.stop_reason = stop_reason

            return LLMResponse(text, stop_reason)

        except Exception as e:
            print(f"[ERROR] DeepSeek API Call failed: {e}")
            return None



class OpenAILLM:
    def __init__(self, model_id, api_key, temperature=0.7, max_tokens=2048):
        self.model_id = model_id
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Create an OpenAI client instance
        self.client = openai.OpenAI(api_key=self.api_key)

    def complete(self, prompt, session_messages=None):
        try:
            # Build message format expected by OpenAI chat models
            messages = session_messages if session_messages else []
            messages.append({"role": "user", "content": prompt})

            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )

            return type("LLMResponse", (), {
                "text": response.choices[0].message.content
            })

        except Exception as e:
            print(f"[ERROR] OpenAI API Call failed: {e}")
            return None

