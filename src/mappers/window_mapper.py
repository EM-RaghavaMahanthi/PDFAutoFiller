import os
import json
import re
import tiktoken
from src.utils.logger import logger
from src.utils.timing import timing_decorator
from src.llm.llm_selector import ClaudeLLM

class SemanticMapperWindow:
    def __init__(self, llm: ClaudeLLM, lines_limit = 400, gid_window_size: int = 10):
        self.llm = llm
        self.gid_window_size = gid_window_size
        self.lines_limit = lines_limit
        self.tokenizer = tiktoken.encoding_for_model("gpt-3.5-turbo")

    def prepare_updated_input_data(self, input_data):
        updated = {}
        for key, value in input_data.items():
            if "check" in key.lower() or "checkbox" in key.lower():
                updated[key] = value
            else:
                updated[key] = ""
        return updated
    
    def build_fid_gid_window_map(self, extracted_data, threshold=10):
        """
        Builds a mapping of fid → {gid, window (start_gid, end_gid)}.
        """

        gid_has_field = {}
        all_gids = []
        sgids = []

        # Collect all gids from text elements
        for page in extracted_data["pages"]:
            for line in page["text_elements"]:
                gid = line["gid"]
                gid_has_field[gid] = False
                all_gids.append(gid)
                sgids.append(gid)
            for field in page["form_fields"]:
                fid_gid = field["gid"]
                gid_has_field[fid_gid] = True

        all_gids.sort()

        prev_true = {}
        last_true = -1
        for gid in all_gids:
            if gid_has_field.get(gid, False):
                last_true = gid
            prev_true[gid] = last_true

        next_true = {}
        next_t = -1
        for gid in reversed(all_gids):
            if gid_has_field.get(gid, False):
                next_t = gid
            next_true[gid] = next_t

        fid_window_map = {}
        
        for page in extracted_data["pages"]:
            for field in page["form_fields"]:
                fid = str(field["fid"])
                gid = field["gid"]
                start = min(prev_true.get(gid, -1), gid - threshold) if prev_true.get(gid, -1) != -1 else gid - threshold
                end = max(next_true.get(gid, -1), gid + threshold) if next_true.get(gid, -1) != -1 else gid + threshold

                fid_window_map[fid] = {
                    "gid": gid,
                    "window": (start, end)
                }

        return fid_window_map, sgids


    def get_gid_chunks_with_text_context(self, extracted_data, fid_window_map):
        chunks = self.chunk_fids_by_gid_context_linear(fid_window_map, self.lines_limit)
        gid_to_line = {}
        for page in extracted_data["pages"]:
            for line in page["text_elements"]:
                gid_to_line[line["gid"]] = line["text"]

        result = {}
        for i, chunk in enumerate(chunks):
            chunk_gids = set()
            for start, end in chunk["window_ranges"]:
                chunk_gids.update(range(start, end + 1))

            sorted_gids = sorted(chunk_gids)
            text_lines = [gid_to_line[gid] for gid in sorted_gids if gid in gid_to_line]
            context_text = "\n".join(text_lines)

            chunk_key = f"chunk_{i+1}"
            result[chunk_key] = {
                "context": context_text,
                "fids": chunk["fids"],
                "gids": sorted_gids,
                "num_lines": len(text_lines)
            }

        return result

    def chunk_fids_by_gid_context_linear(self, fid_window_map, lines_limit):
        fids = list(fid_window_map.keys())
        chunks = []
        current_fids = []
        current_gid_set = set()
        current_window_ranges = []

        i = 0
        while i < len(fids):
            fid = fids[i]
            win = fid_window_map[fid]["window"]
            new_gids = set(range(win[0], win[1] + 1))
            combined_gids = current_gid_set.union(new_gids)

            if len(combined_gids) <= lines_limit:
                current_fids.append(fid)
                current_window_ranges.append(win)
                current_gid_set = combined_gids
                i += 1
            else:
                chunks.append({
                    "fids": current_fids,
                    "window_ranges": current_window_ranges,
                    "total_lines": len(current_gid_set)
                })
                current_fids = []
                current_window_ranges = []
                current_gid_set = set()

        if current_fids:
            chunks.append({
                "fids": current_fids,
                "window_ranges": current_window_ranges,
                "total_lines": len(current_gid_set)
            })

        return chunks

    def prepare_prompt(self, context_text, input_data):
        prompt = f"""
You are tasked with intelligently filling fields in a complex PDF form based on the provided text context and structured input data.

---

**PDF Context:**
The following is the extracted line-by-line text content from the PDF form pages:
-----
{context_text}
-----

Each form field in the context is marked in one of the following formats:
- `[FIELD:{{fid}}]`
- `[BLANK_FIELD:{{fid}}]`
- `[TABLE_CELL_FIELD:{{fid}}]`
- `[CHECKBOX_FIELD:{{fid}}]`

Each `fid` represents a **unique Field ID**.

---

**Input Data:**
You are also provided with a flat dictionary of key-value pairs:
{json.dumps(input_data, indent=2)}

- The **key** is a semantic label.
- The **value** is the actual information that can be used to fill a form field **only if the key matches**.

---

**Your Objective:**
Your task is to semantically analyze the PDF context around each field and map it to the most relevant key from the input data.

You need to infer:
- What information is expected to be filled in each field.
- Whether it can be matched to a key in the input data.
- Whether the corresponding value can be used to fill it.

---

**Important Clarifications & Rules:**
1. **Non-Checkbox Fields (BLANK_FIELD, TABLE_CELL_FIELD, FIELD):**
    - You must match the **semantic meaning** of the field with the **key name only**.
    - The input value should **not** influence your matching.
    - If the field meaning is ambiguous or no relevant key is found, return `"matched_key": null, "matched_value": null, "confidence": 0`.

2. **Checkbox Fields (CHECKBOX_FIELD):**
    - Match the field using **both key name meaning** and corresponding **input value**.
    - If the input value indicates "Yes", "True", or equivalent → `"matched_value": true`.
    - If the input value indicates "No", "False", or equivalent → `"matched_value": false`.
    - If unclear or key not found → return `"matched_value": null`.

3. **Special Clarification - Date fields:**
    - **"Date of Birth", "DOB"** refers to a **person's birth date**.
    - **"Inception Date" or similar** refers to **company/entity registration date**.

4. **If no clear match:**
    - Return `"matched_key": null, "matched_value": null, "confidence": 0`.

5. **Confidence Score:**
    - Assign a **confidence score (0 to 1)** based **only** on how well the field meaning matches the key meaning.
    - Do not include the input value when deciding confidence.

6. **Properly differentiate between person and companies/entities and assign values of their respectives ones accordingly.

7.** even sometimes, checkboxes are labelled as blanks, in that case tell it is yes or no.
---

**Output Format:**
Return a **valid JSON** object in the following format:
{{
  "fid1": {{
    "matched_key": "input_key_name",
    "matched_value": "input_value",
    "confidence": 0.92
  }},
  "fid2": {{
    "matched_key": null,
    "matched_value": null,
    "confidence": 0
  }},
  "fid3": {{
    "matched_key": "input_key_name",
    "matched_value": true,
    "confidence": 0.95
  }}
}}

---

**Rules:**
- Include **all Field IDs (`fid`) detected in the context.**
- Return only valid JSON output.
- **Do not add any explanation, extra text, or comments.**
- Ensure the JSON is properly formatted.

---

**Begin now and strictly follow the instructions.**
"""
        return prompt

    @timing_decorator
    def process_and_save(self, pdf_path, input_json_path, output_dir="data/temp"):
        os.makedirs(output_dir, exist_ok=True)
        pdf_name = os.path.basename(pdf_path).replace(".pdf", "")
        extracted_path = f"{output_dir}/extracted_{pdf_name}.json"
        mapping_path = f"{output_dir}/mappings_{pdf_name}.json"
        debug_path = f"{output_dir}/raw_llm_responses_{pdf_name}.jsonl"

        logger.info(f"Starting Window Field Mapping for PDF: {pdf_path}")

        with open(extracted_path, "r", encoding="utf-8") as f:
            extracted_data = json.load(f)
        with open(input_json_path, "r", encoding="utf-8") as f:
            input_data = json.load(f)

        m_input_data = self.prepare_updated_input_data(input_data)
        fid_window_map, _ = self.build_fid_gid_window_map( extracted_data, self.gid_window_size)
        context_chunks = self.get_gid_chunks_with_text_context(extracted_data, fid_window_map)

        final_output = {}
        total_fillable = 0

        with open(debug_path, "w") as dbg_f:
            for i, (chunk_key, info) in enumerate(context_chunks.items()):
                logger.info(f"[Chunk {i+1}] Processing {chunk_key}")

                import time
                chunk_start = time.time()

                context_text = info["context"]
                fids_in_chunk = set(info["fids"])

                prompt = self.prepare_prompt(context_text, m_input_data)
                input_tokens = len(self.tokenizer.encode(prompt))
                response = self.llm.complete(prompt)
                raw_response = response.text if hasattr(response, 'text') else response
                output_tokens = len(self.tokenizer.encode(raw_response))

                logger.info(f"{chunk_key}: Input Tokens = {input_tokens}, Output Tokens = {output_tokens}")
                dbg_f.write(json.dumps({"chunk": chunk_key, "raw_response": raw_response}) + "\n")

                cleaned_dict = {}
                try:
                    cleaned_json = re.sub(r"^```json\n?|```$", "", raw_response.strip(), flags=re.MULTILINE)
                    parsed = json.loads(cleaned_json)
                    fillable_count = 0

                    for fid, info in parsed.items():
                        if fid not in fids_in_chunk:
                            continue

                        key = info.get("matched_key")
                        value = info.get("matched_value")
                        confidence = info.get("confidence", 0)

                        if key is not None and (value is None or value == ''):
                            value = input_data.get(key)

                        if value not in [None, ""]:
                            fillable_count += 1

                        cleaned_dict[fid] = (key, value, confidence)

                    logger.info(f"{chunk_key}: Fields Detected = {len(cleaned_dict)}, Fillable Fields = {fillable_count}")
                    total_fillable += fillable_count

                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse LLM JSON in chunk {chunk_key}. Check debug file.")

                final_output[chunk_key] = cleaned_dict
                
                chunk_end = time.time()
                logger.info(f"{chunk_key}: Chunk processed in {(chunk_end - chunk_start):.2f} seconds.")

        with open(mapping_path, "w") as f:
            json.dump(final_output, f, indent=2)

        logger.info(f"Saved raw LLM responses to: {debug_path}")
        logger.info(f"Saved cleaned field mappings to: {mapping_path}")
        logger.info(f"Total Fillable Fields across all chunks: {total_fillable}")

        return mapping_path