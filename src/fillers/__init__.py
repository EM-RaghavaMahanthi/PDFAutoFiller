from src.fillers.fitz_filler import FitzFiller
from src.fillers.fitz_embed_filler import FitzEmbedFiller

def get_filler_by_name(name: str, config: dict):
    if name == "fitz":
        return FitzFiller(config)
    elif name == "fitzEmbed":
        return FitzEmbedFiller(config)
    else:
        raise ValueError(f"Unknown filler method: {name}")
