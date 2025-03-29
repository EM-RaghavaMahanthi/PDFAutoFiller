import os
import json
import re
from math import ceil
from src.llm.llm_selector import ClaudeLLM   

class SemanticMapper:
    def __init__(self, llm: ClaudeLLM, chunk_size: int = 12):
        self.llm = llm
        self.chunk_size = chunk_size

    def prepare_updated_input_data(self, input_data):
        """Keep checkbox values, blank others."""
        updated = {}
        for key, value in input_data.items():
            if "check" in key.lower() or "checkbox" in key.lower():
                updated[key] = value
            else:
                updated[key] = ""
        return updated
    
    def get_page_chunk_context(self, extracted_data, start_page, end_page, tokenizer=None):
        """
        Concatenates text elements (ordered by gid) from start_page to end_page.
        Returns the combined text and prints token count.
        """
        
        total_pages = len(extracted_data["pages"])
        start_page = max(1, start_page)
        end_page = min(total_pages, end_page)

        combined_lines = []


        for page in extracted_data["pages"][start_page - 1 : end_page]:
            sorted_lines = sorted(page["text_elements"], key=lambda x: x["gid"])
            for line in sorted_lines:
                combined_lines.append(line["text"])

        combined_text = "\n".join(combined_lines)

        if tokenizer:
            token_count = len(tokenizer.encode(combined_text))
        else:
            token_count = len(combined_text.split())

        print(f"\n[INFO] Pages {start_page} to {end_page}: Total Tokens = {token_count}")
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
        """Prepare clean LLM prompt."""
        prompt = f"""
You need to populate fields in a PDF form based on the provided text context and input data.

**Text Context:**
{context_text}

The text contains line-by-line extracted content from the PDF.  
Form fields are marked as:
- [FIELD:{{fid}}]
- [BLANK_FIELD:{{fid}}]
- [TABLE_CELL_FIELD:{{fid}}]
- [CHECKBOX_FIELD:{{fid}}]

Each `fid` is a unique field identifier.

**Input Data:**
A flat dictionary of key-value pairs:
{json.dumps(input_data, indent=2)}

Rules:
1. For each `fid`, infer semantic meaning.
2. For BLANK_FIELD, TABLE_CELL_FIELD, FIELD → match key meaning only.
3. For CHECKBOX_FIELD → match key meaning + input value.
4. If no clear match → matched_key & matched_value = null, confidence = 0.
5. Confidence is score between 0 and 1 based on key name meaning.

Output format:
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
  }}
}}

Only return valid JSON.
Start now.
"""
        return prompt

    def process_and_save(self, pdf_path, input_json_path, output_dir="data/temp"):
        """Main function: run mapping & save result."""
        os.makedirs(output_dir, exist_ok=True)
        pdf_name = os.path.basename(pdf_path).replace(".pdf", "")
        extracted_path = f"{output_dir}/extracted_{pdf_name}.json"
        mapping_path = f"{output_dir}/mappings_{pdf_name}.json"
        debug_path = f"{output_dir}/raw_llm_responses_{pdf_name}.jsonl"

        # Load data
        with open(extracted_path, "r", encoding="utf-8") as f:
            extracted_data = json.load(f)
        with open(input_json_path, "r", encoding="utf-8") as f:
            input_data = json.load(f)

        # Prepare updated input
        m_input_data = self.prepare_updated_input_data(input_data)

        # Prepare context
        context_dict, _ = self.generate_context_and_stats(extracted_data)

        # Process
        final_output = {}

        with open(debug_path, "w") as dbg_f:
            for i, (chunk_key, context_text) in enumerate(context_dict.items()):
                print(f"\n[Chunk {i+1}] Processing {chunk_key}...")

                prompt = self.prepare_prompt(context_text, m_input_data)
                response = self.llm.complete(prompt)

                # raw_response = """
                #     ```json
                #     {
                #     "117": {
                #         "matched_key": "director4_occupation",
                #         "matched_value": "Engineer",
                #         "confidence": 0.95
                #     },
                #     "118": {
                #         "matched_key": "director4_dob",
                #         "matched_value": "1980-12-10",
                #         "confidence": 0.97
                #     },
                #     "119": {
                #         "matched_key": "beneficial_owner1_name",
                #         "matched_value": "John Doe",
                #         "confidence": 0.99
                #     }
                # }"""

                

                raw_response = response.text if hasattr(response, 'text') else response
                dbg_f.write(json.dumps({
                    "chunk": chunk_key,
                    "raw_response": raw_response
                }) + "\n")

                cleaned_dict = {}
                try:
                    cleaned_json = re.sub(r"^```json\n?|```$", "", raw_response.strip(), flags=re.MULTILINE)
                    parsed = json.loads(cleaned_json)

                    for fid, info in parsed.items():
                        key = info.get("matched_key")
                        value = info.get("matched_value")
                        confidence = info.get("confidence", 0)

                        if key and value is None:
                            value = input_data.get(key)

                        cleaned_dict[fid] = (key, value, confidence)

                except json.JSONDecodeError:
                    print(f"[Warning] Failed to parse LLM JSON in chunk {chunk_key}. Check debug file.")

                final_output[chunk_key] = cleaned_dict

        # Save
        with open(mapping_path, "w") as f:
            json.dump(final_output, f, indent=2)

        print(f"\nSaved raw LLM responses to: {debug_path}")
        print(f"Saved cleaned field mappings to: {mapping_path}")

        return mapping_path
