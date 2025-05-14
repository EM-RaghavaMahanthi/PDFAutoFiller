import os
import json
import re
import time
import tiktoken
from src.llm.llm_selector import LLMSelector
from src.utils.logger import logger
from src.utils.timing import timing_decorator
from src.utils.storage import save_json
from src.chunkers import get_chunker
from src.mappers.semantic_mapper import SemanticMapper


class FeedbackSemanticMapper(SemanticMapper):
    def __init__(self, method_config: dict, chunking_section: dict):
        self.config = method_config

        llm1_name = method_config.get("llm1", "claude")
        llm2_name = method_config.get("llm2", "llama3")
        self.llm1 = LLMSelector(provider=llm1_name).llm
        self.llm2 = LLMSelector(provider=llm2_name).llm

        # Tokenizer
        self.tokenizer = tiktoken.encoding_for_model("gpt-3.5-turbo")

        # Chunking strategy setup
        strategy = chunking_section.get("current_strategy")
        strategy_config = next(
            (s for s in chunking_section.get("strategies", []) if s.get("name") == strategy),
            {}
        )
        strategy_config["name"] = strategy
        self.chunker = get_chunker(strategy, self.tokenizer, **strategy_config)

        # Log which LLMs and strategy are used
        logger.info(f"FeedbackSemanticMapper initialized with LLM1: {llm1_name}, LLM2: {llm2_name}")
        logger.info(f"Chunking strategy selected: {strategy}")

    def prepare_feedback_prompt(self, context_text, input_keys, initial_mapping, fid_start, fid_end):
        prompt = f"""
You are a highly reliable document assistant acting as a feedback corrector.

You are given:
1. A list of known semantic input keys.
2. PDF context text which includes form field markers.
3. An initial field-to-key mapping predicted by another LLM (called "initial mapping").

Your task is to re-evaluate the initial mapping and correct any mistakes. 
If a field is already mapped correctly to the right input key, retain it. 
If the mapping seems wrong, replace it with the best-matching input key.
If no confident match is found, set "key": null and "con": 0.

Initial Mapping Format (you are expected to overwrite this if needed):
{json.dumps(initial_mapping, indent=2)}

Only modify the mappings of fields explicitly found in the context between fid_start and fid_end.

---
---

PDF Context:
Below is the extracted, line-by-line text from the PDF. It includes tagged form fields that require semantic interpretation.

-----
-----
{context_text}
-----
-----

Each field tag is marked using one of the following formats:
- [FIELD:{{fid}}]
- [BLANK_FIELD:{{fid}}]
- [TABLE_CELL_FIELD:{{fid}}]
- [CHECKBOX_FIELD:{{fid}}]

Each fid is a numeric field ID like 11, 12, 24, etc.

---

Input Keys:
You are given a flat list of semantic keys:
{json.dumps(input_keys, indent=2)}

- These are the only allowed key labels.
- Do not invent, reword, interpret, or create new labels.
- Only return exact matches from this list in your output's "key" field.

---

---

Fid start: {fid_start} and Fid end: {fid_end}

Only give the fids between fid_start and fid_end very strict. Don't include extra fids in output

---


Your Task:
1. Review the previous mapping.
2. For each tagged field in the context, determine whether the initially mapped key is the best match.
3. If it's wrong, replace it with the correct one from the input key list.
4. If you're not confident, set "key": null and "con": 0.
5. Return the output in exactly the same JSON format.

---

Field ID Format:
- The keys in your output JSON must be the raw integer fid values from the context.
- For example, if the tag is [BLANK_FIELD:11], your JSON should have:
  "11": {{ "key": ..., "con": ... }}
- Never write "fid11" or similar. Use "11" as the string key.

---

Semantic Matching:
- Use only the line of text that contains the [FIELD:X] tag to understand its label.
- Do not use unrelated or far-away lines.
- Do not assume meaning. Only use what is clearly visible and relevant.

Person vs. Entity Detection:
- If the label includes terms like "person", "individual", "investor", "whose", or "applicant", it likely refers to a human.
- If it includes "company", "organization", or "fund", it likely refers to an entity.
- Use this judgment when mapping date fields or identity fields.

Special Date Rule:
- "Date of Birth" refers to a person's birth date only.
- "Inception Date", "Formation Date", etc., refer to companies or entities only.
- Never match a Date of Birth field to any key that contains "InceptionDate".
- If unsure, return "key": null.

Checkbox Handling:
- If a label implies Yes/No (like "I confirm", "Is this correct?"), you may treat blanks as checkboxes.
- Still, match only by the label’s semantic meaning to a valid key.

---

Confidence Score:
You must provide a "con" value with the following rules:
- 0.90 – 1.00 → Very strong and clear semantic match
- 0.60 – 0.89 → Moderate certainty
- 0.30 – 0.59 → Weak match
- 0.00 – 0.29 → No match → set "key": null

---

Expected Output Format:
{{
  "11": {{
    "key": "input_key_name",
    "con": 0.92
  }},
  "12": {{
    "key": null,
    "con": 0
  }},
  "24": {{
    "key": "another_input_key",
    "con": 0.88
  }}
}}

Rules:
- Field IDs (keys) must be numeric strings like "11", "12", etc.
- Only return field IDs that appear in the provided context chunk not more not less (very strict).
- Do not return any extra or missing fids.
- Do not include any other text, explanation, or comments. Only valid JSON.

---

Final Reminders:
- Use only keys from the input list
- Keep field keys numeric (e.g., "11"), not "fid11"
- Match only the fields in the context and within fid_start and fid_end
- Do not hallucinate, guess, or over-infer

Now begin and return only valid JSON.
"""
        return prompt

    @timing_decorator
    def process_and_save(self, extracted_path, input_json_path, storage_config: dict, output_dir="data/temp/"):
        mapping_path = storage_config.get("output_path")
        file_stub = os.path.splitext(os.path.basename(mapping_path))[0]
        debug_path = os.path.join(output_dir, f"raw_llm_responses_{file_stub}.jsonl")

        logger.info(f"Starting Feedback Mapping for extracted file: {extracted_path}")

        with open(extracted_path, "r", encoding="utf-8") as f:
            extracted_data = json.load(f)
        with open(input_json_path, "r", encoding="utf-8") as f:
            input_data = json.load(f)

        keys_only = self.prepare_updated_input_data(input_data)
        context_dict, _ = self.chunker.generate_context_and_stats(extracted_data)
        final_flat_mapping = {}

        with open(debug_path, "w", encoding="utf-8") as dbg_f:
            for i, (chunk_key, chunk_info) in enumerate(context_dict.items()):
                logger.info(f"[Chunk {i + 1}] Processing {chunk_key}")

                context_text = chunk_info["context"]
                start_fid = chunk_info["start_fid"]
                end_fid = chunk_info["end_fid"]

                logger.info(f"start fid: {start_fid}\tend fid: {end_fid}")

                if not context_text.strip() or start_fid < 0:
                    logger.warning(f"{chunk_key}: Skipping empty context or no fields")
                    continue

                chunk_start = time.time()

                # Step 1: Initial mapping with llm1 (from parent)
                prompt1 = self.prepare_prompt(context_text, keys_only, start_fid, end_fid)
                input_tokens_1 = len(self.tokenizer.encode(prompt1))
                response1 = self.llm1.complete(prompt1)
                raw_response1 = response1.text if hasattr(response1, 'text') else response1
                output_tokens_1 = len(self.tokenizer.encode(raw_response1))

                logger.info(f"{chunk_key}: LLM1 Input Tokens = {input_tokens_1}, Output Tokens = {output_tokens_1}")

                try:
                    cleaned1 = re.sub(r"^```json\n?|```$", "", raw_response1.strip(), flags=re.MULTILINE)
                    parsed1 = json.loads(cleaned1)
                except json.JSONDecodeError:
                    logger.warning(f"{chunk_key}: Failed to parse LLM1 JSON")
                    continue

                # Step 2: Refined mapping with llm2
                prompt2 = self.prepare_feedback_prompt(context_text, keys_only, parsed1, start_fid, end_fid)
                input_tokens_2 = len(self.tokenizer.encode(prompt2))
                response2 = self.llm2.complete(prompt2)
                raw_response2 = response2.text if hasattr(response2, 'text') else response2
                output_tokens_2 = len(self.tokenizer.encode(raw_response2))

                logger.info(f"{chunk_key}: LLM2 Input Tokens = {input_tokens_2}, Output Tokens = {output_tokens_2}")

                try:
                    cleaned2 = re.sub(r"^```json\n?|```$", "", raw_response2.strip(), flags=re.MULTILINE)
                    parsed2 = json.loads(cleaned2)

                    for fid, info in parsed2.items():
                        key = info.get("key")
                        confidence = info.get("con", 0)
                        value = input_data.get(key) if key in input_data else None
                        final_flat_mapping[fid] = (key, value, confidence)

                except json.JSONDecodeError:
                    logger.warning(f"{chunk_key}: Failed to parse LLM2 JSON")

                dbg_f.write(json.dumps({
                    "chunk": chunk_key,
                    "llm1": raw_response1,
                    "llm2": raw_response2
                }) + "\n")

                logger.info(f"{chunk_key}: Feedback Chunk processed in {(time.time() - chunk_start):.2f} seconds.")

        save_json(final_flat_mapping, storage_config)
        logger.info(f"Saved Feedback Mapping to: {mapping_path}")
        return mapping_path
