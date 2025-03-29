from fastapi import APIRouter
from src.models.request_models import MapFieldsRequest
from src.mappers.direct_mapper import SemanticMapper  # You named it direct_mapper but you meant semantic_mapper
from src.llm.llm_selector import LLMSelector

router = APIRouter()

@router.post("/map-fields")
def map_fields(request: MapFieldsRequest):
    pdf_path = request.pdf_path
    input_json_path = request.input_json_path

    llm_selector = LLMSelector()  
    llm = llm_selector.llm        
    mapper = SemanticMapper(llm)

    mapping_path = mapper.process_and_save(pdf_path, input_json_path)

    return {
        "message": "Field mapping completed",
        "mapping_path": mapping_path
    }
