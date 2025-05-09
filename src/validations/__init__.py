# src/validators/__init__.py
from src.validations.type_validator import TypeValidator

def get_validator_by_name(name: str, config: dict):
    if name == "type_validator":
        return TypeValidator(config)
    else:
        raise ValueError(f"Unknown validator method: {name}")
