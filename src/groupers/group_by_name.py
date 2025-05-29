# src/groupers/group_by_name.py
from .base import BaseGrouper
from collections import defaultdict

class GroupByNameGrouper(BaseGrouper):
    def __init__(self, extracted_data: dict):
        super().__init__(extracted_data)

    def group(self):
        """
        Groups 'choice' and 'button' type form fields based on identical field names.
        Returns a dict: {field_name: [(fid, page_num), ...]}
        """
        groups = defaultdict(list)

        for page in self.extracted_data.get("pages", []):
            page_num = page.get("page_number", 0)
            for field in page.get("form_fields", []):
                field_type = field.get("field_type")
                if field_type not in ["choice", "button"]:
                    continue

                field_name = field.get("field_name")
                fid = field.get("fid")

                if field_name and fid is not None:
                    groups[field_name].append((fid, page_num))

        return list(groups.values())
