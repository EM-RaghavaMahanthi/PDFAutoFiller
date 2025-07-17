

def transform_group_fields_output(new_response) -> dict:
    # Convert output model to dict first
    data = new_response.model_dump()
    groups = data.get("groups", [])
    out = {}
    for idx, group in enumerate(groups, 1):
        out[f"group_{idx}"] = {
            "radiobutton_fields": group.get("field_ids", []),
            "export_values": group.get("export_values", []),
            "description": group.get("description", "")
        }
    return out