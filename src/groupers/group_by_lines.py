import re
from collections import defaultdict
from src.groupers.base import BaseGrouper

class GroupByLinesGrouper(BaseGrouper):
    def __init__(self, extracted_data, **kwargs):
        self.extracted_data = extracted_data

    def group(self):
        """
        Groups choice/button fields line-by-line by combining fids present on the same or consecutive lines.
        Returns a list of groups where each group is a list of (fid, page_number).
        """
        pattern = re.compile(r"\[(CHOICE_FIELD|BUTTON_FIELD):(\d+)\]")
        all_groups = []
        current_group = []
        last_page = None
        last_gid = None

        for page in self.extracted_data.get("pages", []):
            page_num = page["page_number"]
            lines = sorted(page.get("text_elements", []), key=lambda l: l.get("gid", 0))

            for line in lines:
                matches = pattern.findall(line.get("text", ""))

                if not matches:
                    if current_group:
                        all_groups.append(current_group)
                        current_group = []
                    continue

                fids = [int(fid) for _, fid in matches]
                current_fid_tuples = [(fid, page_num) for fid in fids]

                if current_group and (last_page != page_num or abs(line.get("gid", 0) - last_gid) > 1):
                    all_groups.append(current_group)
                    current_group = current_fid_tuples
                else:
                    current_group.extend(current_fid_tuples)

                last_page = page_num
                last_gid = line.get("gid", 0)

        if current_group:
            all_groups.append(current_group)

        return all_groups
