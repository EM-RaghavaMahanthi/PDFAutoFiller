from fastapi import APIRouter
from src.models.request_models import ValidateRequest
from src.validations.type_validator import TypeValidator
from src.utils.logger import logger

router = APIRouter()

@router.post("/validate")
def validate_fields(request: ValidateRequest):
    mapping_path = request.mapping_file_path
    validation_path = request.validation_file_path
    output_path = request.stats_output_path

    validator = TypeValidator(validation_path, mapping_path)
    df = validator.save_to_csv(output_path)

    logger.info(f"Validation stats saved to: {output_path}")

    return {
        "message": "Validation completed",
        "output_path": output_path,
        "rows": len(df),
        "columns": list(df.columns)
    }
