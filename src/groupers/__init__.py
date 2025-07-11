from .group_by_name import GroupByNameGrouper
from .group_by_proximity import GroupByProximityGrouper
from .group_by_lines import GroupByLinesGrouper

def get_grouper_by_name(name: str, extracted_data: dict, **kwargs):
    if name == "name":
        return GroupByNameGrouper(extracted_data, **kwargs)
    elif name == "proximity":
        return GroupByProximityGrouper(extracted_data, **kwargs)
    elif name == "lines":
        return GroupByLinesGrouper(extracted_data, **kwargs)
    else:
        raise ValueError(f"Unknown grouper type: {name}")
