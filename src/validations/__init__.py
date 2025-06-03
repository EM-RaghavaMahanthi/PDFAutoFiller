# src/validators/__init__.py
from src.validations.type_validator import TypeValidator
from src.validations.embed_validator import EmbedValidator


def get_validator_by_name(name: str, config: dict):
    if name == "type_validator":
        return TypeValidator(config)
    elif name == "embed_validator":
        return EmbedValidator(config)
    else:
        raise ValueError(f"Unknown validator method: {name}")
