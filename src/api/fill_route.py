from fastapi import APIRouter
from src.models.request_models import FillRequest
from src.fillers.fitz_filler import FitzFiller

router = APIRouter()

@router.post("/fill")
def fill_pdf(request: FillRequest):
    pdf_path = request.pdf_path

    file_name = pdf_path.split("/")[-1].replace(".pdf", "")
    extracted_path = f"data/temp/extracted_{file_name}.json"
    mapping_path = f"data/temp/mappings_{file_name}.json"

    filler = FitzFiller()
    result = filler.fill_pdf(pdf_path, extracted_path, mapping_path)

    return {
        "message": "PDF Filling Completed",
        "output_pdf": result["output_pdf"],
        "filled_fields": result["filled_count"],
        "total_fields": result["total_count"],
        "fill_percentage": result["percentage"]
    }
