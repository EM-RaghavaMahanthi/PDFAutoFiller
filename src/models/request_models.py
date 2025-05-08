from pydantic import BaseModel

class ExtractRequest(BaseModel):
    pdf_path: str


class MapFieldsRequest(BaseModel):
    pdf_path: str
    input_json_path: str

class FillRequest(BaseModel):
    pdf_path: str


class ValidateRequest(BaseModel):
    mapping_file_path: str
    validation_file_path: str
    stats_output_path: str