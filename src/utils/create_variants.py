import json
import re
import math
from src.utils.logger import logger
from src.utils.timing import timing_decorator
import tiktoken


def generate_prompt_for_input_key_variants(chunk_dict, nvariants):
    """
    Construct a prompt string for generating semantic variants for input keys.
    """
    return f"""
Focus on:
- Meaning of the field (e.g. Name, Address, DOB, SSN, etc.)
- Whom the field refers to (e.g., Director 1, Beneficial Owner 2, etc.)
- Use common abbreviations, label expansions, alternative phrasing, etc.
- Directors, beneficiaries, investors are different — focus on accurate semantics.
- Adjectives should be prioritized for differentiation.

-------------------

You are given an input_data JSON object consisting of key-value pairs:
{json.dumps(chunk_dict, indent=2)}

Your task is to generate **{nvariants} semantically equivalent but differently worded representations** of each key's meaning.

---------------------

Format your response strictly in this JSON format:
{{
  "key1": [
    "Version 1",
    "Version 2",
    ...
    "Version k",
    "key1"
  ],
  ...
}}

Only return JSON:
"""


@timing_decorator
def generate_input_key_variants(input_data, llm, nvariants=5, chunk_size=10):
    """
    Generates semantic variants for input JSON keys using LLM.
    """
    keys = list(input_data.keys())
    total_chunks = math.ceil(len(keys) / chunk_size)

    logger.info(f"Total input keys: {len(keys)}, Chunk size: {chunk_size}, Total chunks: {total_chunks}")
    all_variants = {}

    tokenizer = tiktoken.encoding_for_model("gpt-3.5-turbo")

    for i in range(total_chunks):
        chunk_keys = keys[i * chunk_size:(i + 1) * chunk_size]
        chunk_dict = {k: input_data[k] for k in chunk_keys}

        prompt = generate_prompt_for_input_key_variants(chunk_dict, nvariants)

        logger.info(f"[Chunk {i + 1}] Generating variants for {len(chunk_dict)} keys")

        try:
            input_tokens = len(tokenizer.encode(prompt))
            response = llm.complete(prompt)
            raw_text = response.text if hasattr(response, 'text') else response
            output_tokens = len(tokenizer.encode(raw_text))

            logger.info(f"[Chunk {i + 1}] Input Tokens: {input_tokens}, Output Tokens: {output_tokens}")

            cleaned_json = re.sub(r"^```json\n?|```$", "", raw_text.strip(), flags=re.MULTILINE)
            parsed = json.loads(cleaned_json)
            all_variants.update(parsed)
            logger.info(f"[Chunk {i + 1}] Successfully parsed {len(parsed)} variant entries")
        except Exception as e:
            logger.warning(f"[Chunk {i + 1}] Failed to process: {e}")

    logger.info(f"Total input key variant entries generated: {len(all_variants)}")
    return all_variants


def extract_fid_key_map_from_extracted(extracted_data):
    """
    Extract fid → [field_name, field_type] from extracted_data's form_fields.
    """
    fid_map = {}
    for page in extracted_data.get("pages", []):
        for field in page.get("form_fields", []):
            fid = str(field.get("fid"))
            field_name = field.get("field_name", "")
            field_type = field.get("field_type", "")
            if fid and field_name:
                fid_map[fid] = [field_name, field_type]
    logger.info(f"Extracted {len(fid_map)} fid → [field_name, field_type] entries from extracted data")
    return fid_map

def generate_prompt_for_fid_variants(chunk_dict, nvariants):
    """
    Construct a prompt string for generating semantic variants for fid context.
    """
    return f"""
Focus on:
- Meaning of the field (e.g. Name, Address, DOB, SSN, etc.)
- Whom the field refers to (e.g., Director 1, Beneficial Owner 2, etc.)
- Use common abbreviations, label expansions, alternative phrasing, etc.
- Directors, beneficiaries, investors are different — focus on accurate semantics.
- Adjectives should be prioritized for differentiation.

-------------------

You are given a JSON object where keys are numeric field IDs (fid) and values describe the field name and type:
{json.dumps(chunk_dict, indent=2)}

Your task is to generate **{nvariants} semantically equivalent but differently worded representations** of each fid's meaning.

---------------------

Format your response strictly in this JSON format:
{{
  "fid1": [
    "Version 1",
    "Version 2",
    ...
    "Version k",
    "original"
  ],
  ...
}}

Only return JSON:
"""

def generate_field_variants_from_fid_map(fid_map, llm, nvariants=5, chunk_size=10):
    """
    Generates semantic variants for each fid's field_name using LLM.
    """
    
    keys = list(fid_map.keys())
    total_chunks = math.ceil(len(keys) / chunk_size)

    logger.info(f"Total fids: {len(keys)}, Chunk size: {chunk_size}, Total chunks: {total_chunks}")
    all_variants = {}

    tokenizer = tiktoken.encoding_for_model("gpt-3.5-turbo")

    for i in range(total_chunks):
        chunk_keys = keys[i * chunk_size:(i + 1) * chunk_size]
        chunk_dict = {fid: f"{fid_map[fid][0]} ({fid_map[fid][1]})" for fid in chunk_keys}

        prompt = generate_prompt_for_fid_variants(chunk_dict, nvariants)

        logger.info(f"[Chunk {i + 1}] Generating variants for {len(chunk_dict)} fids")

        try:
            input_tokens = len(tokenizer.encode(prompt))
            response = llm.complete(prompt)
            raw_text = response.text if hasattr(response, 'text') else response
            output_tokens = len(tokenizer.encode(raw_text))

            logger.info(f"[Chunk {i + 1}] Input Tokens: {input_tokens}, Output Tokens: {output_tokens}")

            cleaned_json = re.sub(r"^```json\n?|```$", "", raw_text.strip(), flags=re.MULTILINE)
            parsed = json.loads(cleaned_json)
            all_variants.update(parsed)
            logger.info(f"[Chunk {i + 1}] Successfully parsed {len(parsed)} variant entries")
        except Exception as e:
            logger.warning(f"[Chunk {i + 1}] Failed to process: {e}")

    logger.info(f"Total field variant entries generated: {len(all_variants)}")
    return all_variants
