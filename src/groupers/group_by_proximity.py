# src/groupers/group_by_proximity.py
from .base import BaseGrouper
from collections import defaultdict
from itertools import combinations

class DSU:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        if x not in self.parent:
            self.parent[x] = x
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x, y):
        self.parent[self.find(x)] = self.find(y)

class GroupByProximityGrouper(BaseGrouper):
    def __init__(self, extracted_data: dict, x_tol=5, y_gap=20, y_tol=5, x_gap=180):
        super().__init__(extracted_data)
        self.x_tol = x_tol
        self.y_gap = y_gap
        self.y_tol = y_tol
        self.x_gap = x_gap

    def group(self):
        dsu = DSU()
        fid_to_page = {}
        fid_to_bbox = {}

        for page in self.extracted_data.get("pages", []):
            page_num = page["page_number"]
            for field in page["form_fields"]:
                if field["field_type"] in ["button", "choice"]:
                    fid = field["fid"]
                    fid_to_page[fid] = page_num
                    fid_to_bbox[fid] = field["bbox"]

        fids = list(fid_to_bbox.keys())

        def are_connected(fid1, fid2):
            b1 = fid_to_bbox[fid1]
            b2 = fid_to_bbox[fid2]

            vertical = abs(b1["left"] - b2["left"]) <= self.x_tol and abs(b1["bottom"] - b2["top"]) <= self.y_gap
            vertical_rev = abs(b2["left"] - b1["left"]) <= self.x_tol and abs(b2["bottom"] - b1["top"]) <= self.y_gap

            horizontal = abs(b1["top"] - b2["top"]) <= self.y_tol and abs(b1["right"] - b2["left"]) <= self.x_gap
            horizontal_rev = abs(b2["top"] - b1["top"]) <= self.y_tol and abs(b2["right"] - b1["left"]) <= self.x_gap

            return vertical or vertical_rev or horizontal or horizontal_rev

        for fid1, fid2 in combinations(fids, 2):
            if fid_to_page[fid1] != fid_to_page[fid2]:
                continue
            if are_connected(fid1, fid2):
                dsu.union(fid1, fid2)

        groups = defaultdict(list)
        for fid in fids:
            root = dsu.find(fid)
            groups[root].append((fid, fid_to_page[fid]))

        return list(groups.values())
