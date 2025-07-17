import re
import json
from .base import BaseGrouper
from src.llm.llm_selector import LLMSelector
from src.utils.logger import logger
import asyncio

class GroupByLLM(BaseGrouper):
    def __init__(self, extracted_data: dict, **kwargs):
        super().__init__(extracted_data, **kwargs)
        self.field_type = self.params.get("field_type", "RADIOBUTTON")
        self.threshold = self.params.get("threshold", 2)
        self.llm = self.params.get("llm", None)
        self.keys_data = self.params.get("keys_data", {})
        from baml_client.async_client import b as b_async
        self.baml_client = b_async

    def get_context_lines(self):
        radio_gids = set()
        # Step 1: Collect all RADIOBUTTON field GIDs
        for page in self.extracted_data["pages"]:
            for field in page.get("form_fields", []):
                if field.get("field_type", "").upper() == self.field_type.upper():
                    radio_gids.add(field["gid"])

        # Step 2: Expand to nearby GIDs based on threshold
        context_gid_set = set()
        for gid in radio_gids:
            context_gid_set.update(range(gid - self.threshold, gid + self.threshold + 1))

        # Step 3: Collect lines from text_elements if gid in context set
        collected_lines = []
        for page in self.extracted_data["pages"]:
            for text in page.get("text_elements", []):
                if text["gid"] in context_gid_set:
                    collected_lines.append((text["gid"], text["text"]))

        # Step 4: Sort by GID and return only text
        sorted_lines = [text for gid, text in sorted(collected_lines)]
        return sorted_lines

    async def group_fields_from_text(self, lines):
        # Prepare keys_data in the format expected by BAML
        keys_data = self.keys_data or {}

        try:
            groups = await self.baml_client.GroupFieldsFromText(
                lines=lines,
                field_type=self.field_type.lower(),
                field_type_upper=self.field_type.upper(),
                field_type_lower=self.field_type.lower(),
                keys_data=keys_data
            )
            return groups
        except Exception as e:
            logger.error(f"Error in group_fields_from_text BAML call: {e}")
            raise



    async def group(self):
        lines = self.get_context_lines()
        return await self.group_fields_from_text(lines)

