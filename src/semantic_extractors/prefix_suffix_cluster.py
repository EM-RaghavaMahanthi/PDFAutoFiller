from src.semantic_extractors.base import BaseSemanticExtractor
import json
import re

class PrefixSuffixClusterExtractor(BaseSemanticExtractor):
    def __init__(self, extracted_data, window=10, llm=None):
        """
        Args:
            extracted_data: The parsed PDF data from extractor.
            window: Number of surrounding lines to use for context.
            llm: An initialized LLMSelector instance or model with `.generate()` method.
        """
        super().__init__(extracted_data)
        self.window = window
        self.llm = llm

    def get_context_for_fid(self, fid):
        form_info = None
        for field_type in ["blank_input", "checkbox", "table_cell"]:
            if fid in self.forms_dict[field_type]:
                form_info = self.forms_dict[field_type][fid]
                break

        if not form_info:
            return "", "", None

        form_line_gid = form_info[0]
        sorted_gids = sorted(self.lines_info.keys())

        if form_line_gid not in sorted_gids:
            return "", "", form_line_gid

        index = sorted_gids.index(form_line_gid)
        prefix_gids = sorted_gids[max(0, index - self.window): index + 1]
        suffix_gids = sorted_gids[index + 1: index + 1 + self.window]

        prefix = "\n".join(self.lines_info[gid] for gid in prefix_gids)
        suffix = "\n".join(self.lines_info[gid] for gid in suffix_gids)

        return prefix, suffix, form_line_gid

    def infer_semantic_context_for_fid(self, fid, prefix, suffix):
        prompt = f"""
        You are analyzing a PDF form. In the following context, several form fields are represented using the format [FIELD:{{fid}}].

        Your task is to identify the **exact semantic meaning** of each field, including:
        - What type of information is expected (e.g. \"Name\", \"Address\", \"DOB\")
        - And **who** the field refers to, if it's implied (e.g. \"Director 2's Name\", \"Beneficial Owner 3's Residential Address\")

        Instructions:
        - Use **prefix context** primarily to derive meaning.
        - Use suffix context only when prefix isn't clear.
        - Make your answer **precise and human-readable**.
        - Return only a **JSON** mapping of `fid` to its meaning.

        Example:
        {{
          "101": "Beneficial Owner 1 Name",
          "102": "Beneficial Owner 1 Residential Address",
          "105": "Authorized Representative Phone Number"
        }}

        Prefix Context:
        {prefix}

        Suffix Context:
        {suffix}

        Respond with JSON only:
        """

        response = self.llm.complete(prompt)
        return response.text.strip()

    def extract_all_semantics(self):
        all_fids = [
            fid
            for section in self.forms_dict.values()
            for fid in section.keys()
        ]

        for fid in all_fids:
            prefix, suffix, _ = self.get_context_for_fid(fid)
            raw_output = self.infer_semantic_context_for_fid(fid, prefix, suffix)
            cleaned = re.sub(r"^```(?:json)?\n?", "", raw_output.strip())
            cleaned = re.sub(r"\n?```$", "", cleaned.strip())

            try:
                parsed = json.loads(cleaned)
                if isinstance(parsed, dict):
                    for k, v in parsed.items():
                        if k.isdigit():
                            self.output_semantics[int(k)] = v
            except json.JSONDecodeError:
                continue

        return self.output_semantics
