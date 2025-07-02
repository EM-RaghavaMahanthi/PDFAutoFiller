import os
import json
import re
import tiktoken
from math import ceil
from src.llm.llm_selector import LLMSelector
from src.utils.logger import logger
from src.utils.timing import timing_decorator
import time
from src.chunkers import get_chunker
from src.utils.storage import save_json

import aiofiles

import asyncio
from functools import partial
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor()


class SemanticMapper:
    def __init__(self, method_config: dict, chunking_section: dict):

        # Initialize LLM
        llm_name = method_config.get("llm", "claude")  
        LLM =  LLMSelector(provider=llm_name)
        self.llm = LLM.llm
        self.max_threads = LLM.max_threads

        self.confidence_threshold = method_config.get("confidence_threshold", "0.7")

        self.include_key_variants = method_config.get("include_key_variants", 0)
        self.include_field_name_variants = method_config.get("include_field_name_variants", 0)
        self.include_description = method_config.get("include_description", 0)

        # Initialize tokenizer
        self.tokenizer = tiktoken.encoding_for_model("gpt-3.5-turbo")

        # Setup chunking strategy
        strategy = chunking_section.get("current_strategy")

        strategy_config = next(
            (s for s in chunking_section.get("strategies", []) if s.get("name") == strategy),
            {}
        )
        strategy_config["name"] = strategy  
        self.chunker = get_chunker(strategy, self.tokenizer, **strategy_config)
        
    def prepare_updated_input_data(self, input_data):
        """Only keep list of keys, ignore values."""
        return list(input_data.keys())
    
    def prepare_updated_input_data_with_description(self, input_data) -> dict:
        return {
            key: [info["description"]] 
            for key, info in input_data.items()
            if "description" in info
        }
    
    def flatten_enriched_data(self, enriched: dict) -> dict:
        return {
            key: info["value"]
            for key, info in enriched.items()
            if isinstance(info, dict) and "value" in info
        }

    
    def build_input_key_section(self, input_keys: list, key_variants: dict = None) -> str:
        if not key_variants:
            if self.include_description == 1:
                return f"""
            ---
            Input Keys:
            You are given a dictionary where each key maps to a list containing its description:
            {json.dumps(input_keys, indent=2)}

            - These keys are the only allowed labels for matching.
            - Do not invent, reword, interpret, or create new labels.
            - Only return exact matches from this list in your output's "key" field.
            - Each key has a corresponding description to clarify its meaning.
            - Make use of the description to understand the intent behind each key and guide accurate mapping, check for paranthesis for special instruction in descriptions
            """
            else:
                return f"""
            ---
            Input Keys:
            You are given a flat list of semantic keys:
            {json.dumps(input_keys, indent=2)}

            - These are the only allowed key labels.
            - Do not invent, reword, interpret, or create new labels.
            - Only return exact matches from this list in your output's "key" field.
            """
        else:
            return f"""
    ---
    Input Key Variants:
    You are given a dictionary of semantic key variants.
    Each key has multiple equivalent phrasings that may be used in form labels:

    {json.dumps(key_variants, indent=2)}

    - You must match the field context to one of the variants.
    - Then, return the original key corresponding to that variant.
    - Do not return the variant — only the original key.
    - Only use keys from the original input_keys list.
    """


    def build_key_matching_rules(self, key_variants: dict = None) -> str:
        if not key_variants:
            return """
    ---
    Key Matching from Input Only:
    - You must identify what the field is asking for, then select the corresponding label from the input_keys list.
    - The "key" must be a value from the input list only.
    - Do not write inferred or paraphrased labels like "Amount of Investment" unless that exact string is in input_keys.
    - Always return the best matching input key from the list, or null if no clear match.
    """
        else:
            return """
    ---
    Key Matching from Input Variants:
    - You are provided with multiple semantic variants (alternative phrasings) for each input key.
    - Your task is to match the semantic meaning of each field (based on its label/context) to the most relevant variant.
    - Then, return the original key whose variant had the best semantic match.
    - Do not invent or infer keys outside the provided list.
    - The "key" in your final output must be from the original input_keys list — even though matching is done on variants.
    - If none of the variants semantically match well, set "key": null and "con": 0.

    Example:
    If one of the input keys is "investor_full_name" and its variants include:
    - "Full Name of Investor"
    - "Name of the Individual Investor"
    - "Investor’s Legal Name"

    And the field label is "Investor Name", then you may semantically match it to one of these variants, and return:
    "key": "investor_full_name"
    """
        
    def build_field_name_variant_section(self, field_name_variants: dict) -> str:
        """
        Builds a section for the prompt describing semantic variants of field names per fid.

        Args:
            field_name_variants (dict): Dictionary where each key is fid (as str) and value is list of semantic variants,
                                        with the last item being the original field_name.

        Returns:
            str: A formatted section describing the variants for use in prompt instructions.
        """
        if not field_name_variants:
            return ""

        lines = [
            "---",
            "Field Name Variants:",
            "You are provided with multiple semantic variants for certain form fields (by fid).",
            "These are alternative phrasings of the field’s intent. The last item in each list is the original field_name.",
            "Use these to better understand the context, but do not use them as input keys.",
            "",
            "FID → Field Name and Variants:"
        ]

        for fid, variants in field_name_variants.items():
            original_field_name = variants[-1]
            lines.append(f"\nFID {fid} ({original_field_name}):")
            for variant in variants[:-1]:
                lines.append(f"- {variant}")
            lines.append(f"- {original_field_name} (original)")

        lines.append("\nUse these to improve your semantic judgment. Do not use them as keys in your output.")
        lines.append("---")

        return "\n".join(lines)



    def prepare_prompt(self, context_text, input_keys, fid_start, fid_end, key_variants, field_name_variants):
        instructions_header = """
    You are a highly reliable document assistant that must semantically fill fields in a PDF form using the provided field context and a list of known keys.

    You must follow all instructions very carefully. Do not infer values, do not hallucinate, and do not change the required structure under any circumstance.

    Only give the fids between fid_start and fid_end very strict. Don't include extra fids in output
    """

        pdf_context_section = f"""
    ---
    PDF Context:
    Below is the extracted, line-by-line text from the PDF. It includes tagged form fields that require semantic interpretation.

    -----
    {context_text}
    -----
    Each field tag is marked using one of the following formats:
    - [TEXT_FIELD:{{fid}}]
    - [TABLE_CELL_FIELD:{{fid}}]
    - [CHECKBOX_FIELD:{{fid}}]
    - [RADIOBUTTON_FIELD:{{fid}}]

    Each fid is a numeric field ID like 11, 12, 24, etc.
    """
        
        spacing_layout_section = """Field tags like `[BLANK_FIELD:{fid}]` are spaced based on their visual positions in the PDF — extra spaces are added according to gaps between elements.
        Minor spacing mismatches may still occur.Sometimes, the label (e.g., Name:) and its blank may not be on the same line — the blank could be above, below, or offset.
        There may also be multiple blanks on the same line or under labels.
        Use both horizontal and vertical alignment to infer mappings accurately. Don't assume blanks are always side-by-side with labels."""
        

        text_field_section = """
---
BLANK Fields:
These fields are represented as `[TEXT_FIELD:{fid}]` or `[TABLE_CELL_FIELD:{fid}]`.

- These are open-ended fields where a user needs to write something.
- You must analyze the surrounding context (prefix/suffix text, labels) to understand what is being asked.
- For `[TABLE_CELL_FIELD:{fid}]`, it may belong to a structured table. Consider the column name and any nearby header to infer the meaning.

Guidelines:
- Identify the most appropriate key from the input list that semantically represents the intent of the label around the field.
- Use line-level context and avoid guessing.
- Match based on semantic meaning, not just string similarity.
"""

        checkbox_field_section = """
---
CHOICE Fields:
These fields are represented as `[CHECKBOX_FIELD:{fid}]`.

- They represent dropdowns or selection lists.
- You must decide what kind of information is being selected here based on the label or line around it.

Additional Tips:
- Keys containing substrings like `check`, `dropdown`, `list`, `type`, `option`, or `selection` are usually better matches for CHOICE fields.
- These fields often appear **together in groups**, such as a series of related dropdowns on the same line or in a table.
- Such groupings may occur **recursively** or across lines, so keep that in mind when interpreting the context.

Guidelines:
- Match to input keys that imply a **selection**.
- Avoid guessing; prioritize semantic meaning based on visible label.
- Example: A label like "Select Investor Type" should match to a key like `investorType`.
"""

        radio_button_field_section = """
---
BUTTON Fields:
These fields are represented as `[RADIOBUTTON_FIELD:{fid}]`.

- These are checkboxes, toggle buttons, or yes/no fields.
- They typically represent binary decisions or confirmations.

Additional Tips:
- Fields with surrounding text containing words like `check`, `box`, `confirm`, `agree`, or `yes` are often buttons.
- These fields often appear **in groups** (e.g., a list of terms to agree or options to select), and this grouping may be **recursive** across lines or within table rows.
- Use this grouping behavior to guide how multiple buttons should be semantically mapped.

Guidelines:
- Match to input keys that expect a **yes/no** or **true/false** answer.
- Example keys: `isEntityConfirmed`, `hasAgreed`, `checkbox1`, etc.
- Only match if the label clearly implies a binary action or choice.
"""


        table_cell_field_section = """
---
TABLE CELL Fields:
These fields are part of a structured table and represented as `[TABLE_CELL_FIELD:{fid}]`.

- Each cell belongs to a row-column matrix.
- Contextual meaning is derived from the column header, nearby rows, and any title or label above the table.

Guidelines:
- Identify which **column** and **row context** the field belongs to.
- Use the field's row positioning and the text above the table to decide what kind of data is being filled.
- Not every cell in the table needs to be filled.
- Match each field to the most semantically appropriate key, based on what that column represents in the table.
"""



        input_keys_section = self.build_input_key_section(input_keys, key_variants)

        fid_range_info = f"""
    ---
    Fid start: {fid_start} and Fid end: {fid_end}

    Only give the fids between fid_start and fid_end very strict. Don't include extra fids in output
    """

        task_description = """
    ---
    Your Task:
    1. For each tagged field (e.g., [BLANK_FIELD:12]) found in the context, analyze the surrounding label to determine what it is asking for.
    1.1 Return only and exactly the fids (field IDs) present in the context. Do not add any fids that are not explicitly tagged in the context text, even if you think they are related.
    2. Based on the semantic meaning of that field label, identify the best-matching key from the input list.
    3. Then, place that matched key (exact string) in the "key" field for that fid. Do not use the label itself.
    4. If no strong match exists, set "key": null and "con": 0.
    """

        formatting_rules = """
    ---
    Field ID Format:
    - The keys in your output JSON must be the raw integer fid values from the context.
    - For example, if the tag is [BLANK_FIELD:11], your JSON should have:
    "11": { "key": ..., "con": ... }
    - Never write "fid11" or similar. Use "11" as the string key.
    - Output key = field number only.
    """

        key_matching_rules = self.build_key_matching_rules(key_variants)
        field_name_section = self.build_field_name_variant_section(field_name_variants)

        semantic_tips = """
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
    """

        confidence_score_rules = """
    ---
    Confidence Score:
    You must provide a "con" value with the following rules:
    - 0.90 – 1.00 → Very strong and clear semantic match
    - 0.60 – 0.89 → Moderate certainty
    - 0.30 – 0.59 → Weak match
    - 0.00 – 0.29 → No match → set "key": null

    Do not assign high confidence unless the match is clear and unambiguous.
    """

        output_format = """
    ---
    Expected Output Format:
    Return JSON structured exactly like this:

    {
    "11": {
        "key": "input_key_name",
        "con": 0.92
    },
    "12": {
        "key": null,
        "con": 0
    },
    "24": {
        "key": "another_input_key",
        "con": 0.88
    }
    }

    Rules:
    - Field IDs (keys) must be numeric strings like "11", "12", etc.
    - Only return field IDs that appear in the provided context chunk — not more, not less.
    - Do not return any extra or missing fids.
    - Do not include any other text, explanation, or comments. Only valid JSON.
    - Only give the fids between fid_start and fid_end very strict. Don't include extra fids in output
    """

        closing_note = """
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

        return "\n".join([
            instructions_header,
            pdf_context_section,
            input_keys_section,
            spacing_layout_section,
            text_field_section,
            checkbox_field_section,
            radio_button_field_section,
            table_cell_field_section,
            fid_range_info,
            task_description,
            formatting_rules,
            key_matching_rules,
            field_name_section,
            semantic_tips,
            confidence_score_rules,
            output_format,
            closing_note
        ])
    
    async def generate_key_descriptions_bulk(self, keys: list, llm) -> dict:
        prompt = f"""
    You are a helpful assistant. Given a list of JSON keys from a form or document input, generate a human-readable description for each key that clearly explains what the field represents.

    If the meaning of any key is unclear or ambiguous, return "undefined" for that key.

    Strictly return the output as a valid JSON object in the format:
    {{ "key": "description", ... }}

    Try adding better description not just paraphrasing, whos or who are important

    Also retain the numbering in ther say BOwnerCorporationFulllegalname4_ID, it is fourth BOwner...

    Also whenever you find Inception date, tell that it is not data of birth very clearly. 

    Do not include any extra commentary, markdown, or explanation — only valid JSON.

    Keys: {keys}

    Output:
    """
        raw_response = llm.complete(prompt)
        cleaned_json = re.sub(r"^```json\n?|```$", "", raw_response.text.strip(), flags=re.MULTILINE)
        parsed = json.loads(cleaned_json)
        return parsed
    
    async def enrich_input_data_llm(self, flat_json: dict, llm) -> dict:
        keys = list(flat_json.keys())
        descriptions =await self.generate_key_descriptions_bulk(keys, llm)

        enriched = {}
        for key, value in flat_json.items():
            enriched[key] = {
                "value": value,
                "description": descriptions.get(key, "undefined")
            }
        return enriched
    
    async def _process_chunk_async(
        self,
        chunk_key: str,
        chunk_info: dict,
        input_data: dict,
        keys_data: dict,
        input_variants: dict,
        field_name_variants_all: dict,
        dbg_f,
        semaphore
    ):
        logger.info(f"[{chunk_key}] Waiting for semaphore... (Available slots: {semaphore._value})")

        async with semaphore:
            start_time = time.time()
            logger.info(f"[{chunk_key}] Started async processing (Remaining slots: {semaphore._value})")

            context_text = chunk_info["context"]
            start_fid = chunk_info["start_fid"]
            end_fid = chunk_info["end_fid"]

            logger.info(f"[{chunk_key}] start fid: {start_fid} — end fid: {end_fid}")

            result_mapping = {}

            if not context_text.strip() or start_fid < 0:
                logger.warning(f"[{chunk_key}] Skipping due to empty context or no valid FIDs.")
                return result_mapping

            # Filter field name variants for this chunk
            field_name_variants_fids = {}
            for fid_str, variants in field_name_variants_all.items():
                try:
                    fid = int(fid_str)
                    if start_fid <= fid <= end_fid:
                        field_name_variants_fids[fid_str] = variants
                except ValueError:
                    logger.warning(f"[{chunk_key}] Skipping invalid fid in field variants: {fid_str}")

            # Prepare prompt
            prompt = self.prepare_prompt(
                context_text, keys_data, start_fid, end_fid, input_variants, field_name_variants_fids
            )

            input_tokens = len(self.tokenizer.encode(prompt))
            logger.info(f"[{chunk_key}] Prompt token count: {input_tokens}")

            try:
                # Send to LLM
                response = await asyncio.to_thread(self.llm.complete, prompt)
                raw_response = response.text if hasattr(response, 'text') else response
                output_tokens = len(self.tokenizer.encode(raw_response))
                total_tokens = input_tokens + output_tokens
                logger.info(f"[{chunk_key}] Output token count: {output_tokens}")
                logger.info(f"[{chunk_key}] Total tokens: {total_tokens}")

                # Save raw response for debug
                await dbg_f.write(json.dumps({
                    "chunk": chunk_key,
                    "raw_response": raw_response
                }) + "\n")

                # Parse LLM JSON
                cleaned_json = re.sub(r"^```json\n?|```$", "", raw_response.strip(), flags=re.MULTILINE)
                parsed = json.loads(cleaned_json)

                for fid, info in parsed.items():
                    key = info.get("key")
                    confidence = info.get("con", 0)
                    value = input_data.get(key) if key in input_data else None
                    result_mapping[fid] = (key, value, confidence)

            except json.JSONDecodeError:
                logger.warning(f"[{chunk_key}] Failed to parse LLM JSON. Check debug file.")
            except Exception as e:
                logger.error(f"[{chunk_key}] Unexpected error during LLM processing: {e}")

            logger.info(f"[{chunk_key}] Done in {time.time() - start_time:.2f} sec (Slots now: {semaphore._value})")

            return result_mapping


    @timing_decorator
    async def process_and_save(self, extracted_path, input_json_path, original_pdf_path, storage_config: dict, 
                        input_key_json_variants_path: str = None, field_names_json_variants_path: str = None,
                        output_dir="data/temp/"):

        mapping_path = storage_config.get("output_path")
        file_stub = os.path.splitext(os.path.basename(mapping_path))[0]
        debug_path = os.path.join(output_dir, f"raw_llm_responses_{file_stub}.jsonl")

        logger.info(f"Starting Field Mapping for: {extracted_path}")

        with open(extracted_path, "r", encoding="utf-8") as f:
            extracted_data = json.load(f)
        with open(input_json_path, "r", encoding="utf-8") as f:
            input_data = json.load(f)

        input_variants = {}
        if self.include_key_variants and input_key_json_variants_path and os.path.exists(input_key_json_variants_path):
            with open(input_key_json_variants_path, "r", encoding="utf-8") as vf:
                input_variants = json.load(vf)

        field_name_variants_all = {}
        if self.include_field_name_variants and field_names_json_variants_path and os.path.exists(field_names_json_variants_path):
            with open(field_names_json_variants_path, "r", encoding="utf-8") as fvf:
                field_name_variants_all = json.load(fvf)

        keys_data = self.prepare_updated_input_data(input_data)
        if self.include_description == 1:
            logger.info("Preparing & Including key descriptions in the prompt.")
            enriched_data = await self.enrich_input_data_llm(input_data, llm=self.llm)
            keys_data = self.prepare_updated_input_data_with_description(enriched_data)

        context_dict, _ = self.chunker.generate_context_and_stats(extracted_data)
        final_flat_mapping = {}

        semaphore = asyncio.Semaphore(self.max_threads)

        logger.info(f"We are running max threads of {self.max_threads}")

        async def run_all_chunks():
            tasks = []
            async with aiofiles.open(debug_path, "w", encoding="utf-8") as dbg_f:
                for i, (chunk_key, chunk_info) in enumerate(context_dict.items()):
                    task = self._process_chunk_async(
                        chunk_key, chunk_info,
                        input_data, keys_data,
                        input_variants,
                        field_name_variants_all,
                        dbg_f,
                        semaphore
                    )
                    tasks.append(task)
                results = await asyncio.gather(*tasks)
                for chunk_result in results:
                    final_flat_mapping.update(chunk_result)

        await run_all_chunks()

        save_json(final_flat_mapping, storage_config)

        logger.info(f"Saved field mappings to: {mapping_path}")
        logger.info(f"Saved raw LLM responses to: {debug_path}")
        return mapping_path

