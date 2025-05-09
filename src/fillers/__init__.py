from src.fillers.fitz_filler import FitzFiller

def get_filler_by_name(name: str, config: dict):
    if name == "fitz":
        return FitzFiller(config)
    else:
        raise ValueError(f"Unknown filler method: {name}")
