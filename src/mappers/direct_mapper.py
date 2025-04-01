import os
import json
import re
import tiktoken
from math import ceil
from src.llm.llm_selector import ClaudeLLM
from src.utils.logger import logger
from src.utils.timing import timing_decorator

class SemanticMapper:
    def __init__(self, llm: ClaudeLLM, chunk_size: int = 12):
        self.llm = llm
        self.chunk_size = chunk_size
        self.tokenizer = tiktoken.encoding_for_model("gpt-3.5-turbo")  # Closest to Claude

    def prepare_updated_input_data(self, input_data):
        """Keep checkbox values, blank others."""
        updated = {}
        for key, value in input_data.items():
            if "check" in key.lower() or "checkbox" in key.lower():
                updated[key] = value
            else:
                updated[key] = ""
        return updated

    def get_page_chunk_context(self, extracted_data, start_page, end_page):
        """Concatenate text elements for given chunk."""
        total_pages = len(extracted_data["pages"])
        start_page = max(1, start_page)
        end_page = min(total_pages, end_page)
        combined_lines = []

        for page in extracted_data["pages"][start_page - 1 : end_page]:
            sorted_lines = page["text_elements"]
            for line in sorted_lines:
                combined_lines.append(line["text"])

        combined_text = "\n".join(combined_lines)
        token_count = len(self.tokenizer.encode(combined_text))

        logger.info(f"Chunk Pages {start_page}-{end_page}: Tokens = {token_count}")
        return combined_text

    def generate_context_and_stats(self, extracted_data):
        """Generate context per chunk."""
        total_pages = len(extracted_data["pages"])
        num_chunks = ceil(total_pages / self.chunk_size)
        context_dict = {}
        stats_dict = {}

        for i in range(num_chunks):
            start_page = i * self.chunk_size + 1
            end_page = min((i + 1) * self.chunk_size, total_pages)
            context = self.get_page_chunk_context(extracted_data, start_page, end_page)
            key = f"Page {start_page}-{end_page}"
            context_dict[key] = context
            stats_dict[key] = (
                len(context.split()),
                sum(len(p["form_fields"]) for p in extracted_data["pages"][start_page - 1:end_page])
            )
        return context_dict, stats_dict

    def prepare_prompt(self, context_text, input_data):
        """Prepare LLM prompt."""
        prompt = f"""
You are assisting in filling fields in a PDF form.

**PDF Context:**
{context_text}

**Input Data:**
A flat dictionary of key-value pairs:
{json.dumps(input_data, indent=2)}

**Important Clarification:**
- **Input data is a dictionary in `key: value` format.**
- The `key` represents the semantic label.
- The `value` is the actual value to fill if the key matches.
- For most fields (BLANK_FIELD, TABLE_CELL_FIELD, FIELD), you should match based **only on the key name**.
- **Do not match based on input value.**
- Looks for DOBs or Data of births of Dtae of Birth. Inceptions dates are not date of births of person

**Checkbox Special Rule:**
- For `CHECKBOX_FIELD`, you must match based on both key and value:
    - If key matches and input value indicates Yes/True → `"matched_value": true`
    - If key matches but value indicates No/False → `"matched_value": false`
    - If unclear → `"matched_value": null`

**Instructions:**
1. Detect all field IDs in the context in format `[FIELD:{{fid}}]`, `[BLANK_FIELD:{{fid}}]`, `[TABLE_CELL_FIELD:{{fid}}]`, `[CHECKBOX_FIELD:{{fid}}]`.
2. For each field:
    - For non-checkbox → match **only key name meaning**
    - For checkbox → match **key name + input value**
3. If confident:
    - Return `"matched_key"`, `"matched_value"` (from input data), `"confidence"` (0 to 1, based only on key name match)
4. If no clear match:
    - `"matched_key": null`, `"matched_value": null`, `"confidence": 0`

**Output Format:**
Return only valid JSON:
{{
  "fid1": {{
    "matched_key": "input_key_name",
    "matched_value": "input_value",
    "confidence": 0.85
  }},
  "fid2": {{
    "matched_key": null,
    "matched_value": null,
    "confidence": 0
  }},
  "fid3": {{
    "matched_key": "input_key_name",
    "matched_value": true,
    "confidence": 0.92
  }}
}}
**Rules:**
- Always include all fids detected in context.
- No explanation, only valid JSON.

Start now.
"""
        return prompt

    @timing_decorator
    def process_and_save(self, pdf_path, input_json_path, output_dir="data/temp"):
        """Main function: run mapping & save result."""
        os.makedirs(output_dir, exist_ok=True)
        pdf_name = os.path.basename(pdf_path).replace(".pdf", "")
        extracted_path = f"{output_dir}/extracted_{pdf_name}.json"
        mapping_path = f"{output_dir}/mappings_{pdf_name}.json"
        debug_path = f"{output_dir}/raw_llm_responses_{pdf_name}.jsonl"

        logger.info(f"Starting Field Mapping for PDF: {pdf_path}")

        # Load data
        with open(extracted_path, "r", encoding="utf-8") as f:
            extracted_data = json.load(f)
        with open(input_json_path, "r", encoding="utf-8") as f:
            input_data = json.load(f)

        m_input_data = self.prepare_updated_input_data(input_data)
        context_dict, _ = self.generate_context_and_stats(extracted_data)

        final_output = {}
        total_fillable = 0

        with open(debug_path, "w") as dbg_f:
            for i, (chunk_key, context_text) in enumerate(context_dict.items()):
                logger.info(f"[Chunk {i+1}] Processing {chunk_key}")

                # -- Chunk timing --
                import time
                chunk_start = time.time()

                prompt = self.prepare_prompt(context_text, m_input_data)
                input_tokens = len(self.tokenizer.encode(prompt))

                # LLM call
                response = self.llm.complete(prompt)
                raw_response = response.text if hasattr(response, 'text') else response
                output_tokens = len(self.tokenizer.encode(raw_response))

                logger.info(f"{chunk_key}: Input Tokens = {input_tokens}, Output Tokens = {output_tokens}")

                dbg_f.write(json.dumps({
                    "chunk": chunk_key,
                    "raw_response": raw_response
                }) + "\n")

                cleaned_dict = {}
                try:
                    cleaned_json = re.sub(r"^```json\n?|```$", "", raw_response.strip(), flags=re.MULTILINE)
                    parsed = json.loads(cleaned_json)

                    fillable_count = 0
                    for fid, info in parsed.items():
                        key = info.get("matched_key")
                        value = info.get("matched_value")
                        confidence = info.get("confidence", 0)

                        if key is not None and (value is None or value == ''):
                            value = input_data.get(key)

                        if value not in [None, ""]:
                            fillable_count += 1

                        cleaned_dict[fid] = (key, value, confidence)

                    logger.info(f"{chunk_key}: Fields Detected = {len(parsed)}, Fillable Fields = {fillable_count}")
                    total_fillable += fillable_count

                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse LLM JSON in chunk {chunk_key}. Check debug file.")

                final_output[chunk_key] = cleaned_dict

                # -- Chunk timing end --
                chunk_end = time.time()
                logger.info(f"{chunk_key}: Chunk processed in {(chunk_end - chunk_start):.2f} seconds.")

        # Save
        with open(mapping_path, "w") as f:
            json.dump(final_output, f, indent=2)

        logger.info(f"Saved raw LLM responses to: {debug_path}")
        logger.info(f"Saved cleaned field mappings to: {mapping_path}")
        logger.info(f"Total Fillable Fields across all chunks: {total_fillable}")

        return mapping_path

