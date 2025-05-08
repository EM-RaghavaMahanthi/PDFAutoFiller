import os
import json
import re
import tiktoken
from math import ceil
from src.llm.llm_selector import ClaudeLLM
from src.utils.logger import logger
from src.utils.timing import timing_decorator
import time
from src.chunkers import get_chunker

class SemanticMapper:
    def __init__(self, llm: ClaudeLLM, config: dict):
        self.llm = llm
        self.tokenizer = tiktoken.encoding_for_model("gpt-3.5-turbo")
        self.config = config

        strategy = config.get("name", "page")  
        self.chunker = get_chunker(strategy, self.tokenizer, **config)
        
    def prepare_updated_input_data(self, input_data):
        """Only keep list of keys, ignore values."""
        return list(input_data.keys())

    def prepare_prompt(self, context_text, input_keys, fid_start, fid_end):
        prompt = f"""
You are a highly reliable document assistant that must semantically fill fields in a PDF form using the provided field context and a list of known keys.

You must follow all instructions very carefully. Do not infer values, do not hallucinate, and do not change the required structure under any circumstance.

Only give the fids between fid_start and fid_end very strict. Don't include extra fids in output

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

Fid start: {fid_start} and Fid end:{fid_end}

Only give the fids between fid_start and fid_end very strict. Don't include extra fids in output

---


Your Task:
1. For each tagged field (e.g., [BLANK_FIELD:12]) found in the context, analyze the surrounding label to determine what it is asking for.
1.1 Return only and exactly the fids (field IDs) present in the context. Do not add any fids that are not explicitly tagged in the context text, even if you think they are related
2. Based on the semantic meaning of that field label, identify the best-matching key from the input list.
3. Then, place that matched key (exact string) in the "key" field for that fid. Do not use the label itself.
4. If no strong match exists, set "key": null and "con": 0.

---

Field ID Format:
- The keys in your output JSON must be the raw integer fid values from the context.
- For example, if the tag is [BLANK_FIELD:11], your JSON should have:
  "11": {{ "key": ..., "con": ... }}
- Never write "fid11" or similar. Use "11" as the string key.
- Output key = field number only.

Key Matching from Input Only:
- You must identify what the field is asking for, then select the corresponding label from the input_keys list.
- The "key" must be a value from the input list only.
- Do not write inferred or paraphrased labels like "Amount of Investment" unless that exact string is in input_keys.
- Always return the best matching input key from the list, or null if no clear match.

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

Do not assign high confidence unless the match is clear and unambiguous.

---

Expected Output Format:
Return JSON structured exactly like this:

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
- Only return field IDs that appear in the provided context chunk not more not less( very strict)Return only and exactly the fids (field IDs) present in the context. Do not add any fids that are not explicitly tagged in the context text, even if you think they are related.
- Do not return any extra or missing fids.
- Do not include any other text, explanation, or comments. Only valid JSON.
- Only give the fids between fid_start and fid_end very strict. Don't include extra fids in output

---

Final Reminders:
- Only use keys found in the input list
- Output keys = numeric fids (e.g., "11"), not "fid11"
- Confidence score must reflect real certainty
- Return only fids tagged in the current context
- Do not guess, hallucinate, reword, or over-infer
- Only give the fids between fid_start and fid_end very strict. Don't include extra fids in output
Now begin and return only valid JSON.
"""
        return prompt


    @timing_decorator
    def process_and_save(self, pdf_path, input_json_path, output_dir="data/temp"):
        os.makedirs(output_dir, exist_ok=True)
        pdf_name = os.path.basename(pdf_path).replace(".pdf", "")
        extracted_path = f"{output_dir}/extracted_{pdf_name}.json"
        mapping_path = f"{output_dir}/mappings_{pdf_name}.json"
        debug_path = f"{output_dir}/raw_llm_responses_{pdf_name}.jsonl"

        logger.info(f"Starting Field Mapping for PDF: {pdf_path}")

        with open(extracted_path, "r", encoding="utf-8") as f:
            extracted_data = json.load(f)
        with open(input_json_path, "r", encoding="utf-8") as f:
            input_data = json.load(f)

        keys_only = self.prepare_updated_input_data(input_data)
        context_dict, _ = self.chunker.generate_context_and_stats(extracted_data)
        final_output = {}
        final_flat_mapping = {}

        with open(debug_path, "w", encoding="utf-8") as dbg_f:
            for i, (chunk_key, chunk_info) in enumerate(context_dict.items()):
                logger.info(f"[Chunk {i+1}] Processing {chunk_key}")

                context_text = chunk_info["context"]
                start_fid = chunk_info["start_fid"]
                end_fid = chunk_info["end_fid"]

                logger.info(f"start fid: {start_fid}\tend fid: {end_fid}")

                if not context_text.strip() or start_fid<0:
                    logger.warning(f"{chunk_key}: Skipping empty context or nor fields")
                    continue

                chunk_start = time.time()
                prompt = self.prepare_prompt(context_text, keys_only, start_fid, end_fid)
                input_tokens = len(self.tokenizer.encode(prompt))

                response = self.llm.complete(prompt)
                raw_response = response.text if hasattr(response, 'text') else response
                output_tokens = len(self.tokenizer.encode(raw_response))

                logger.info(f"{chunk_key}: Input Tokens = {input_tokens}, Output Tokens = {output_tokens}")

                dbg_f.write(json.dumps({
                    "chunk": chunk_key,
                    "raw_response": raw_response
                }) + "\n")

                try:
                    cleaned_json = re.sub(r"^```json\n?|```$", "", raw_response.strip(), flags=re.MULTILINE)
                    parsed = json.loads(cleaned_json)

                    for fid, info in parsed.items():
                        key = info.get("key")
                        confidence = info.get("con", 0)
                        value = input_data.get(key) if key in input_data else None
                        final_flat_mapping[fid] = (key, value, confidence)

                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse LLM JSON in chunk {chunk_key}. Check debug file.")

                logger.info(f"{chunk_key}: Chunk processed in {(time.time() - chunk_start):.2f} seconds.")

        with open(mapping_path, "w", encoding="utf-8") as f:
            json.dump(final_flat_mapping, f, indent=2)

        logger.info(f"Saved raw LLM responses to: {debug_path}")
        logger.info(f"Saved cleaned (deduplicated) field mappings to: {mapping_path}")

        return mapping_path
