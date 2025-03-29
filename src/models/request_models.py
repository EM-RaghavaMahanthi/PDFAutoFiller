from pydantic import BaseModel

class ExtractRequest(BaseModel):
    pdf_path: str


class MapFieldsRequest(BaseModel):
    pdf_path: str
    input_json_path: str

class FillRequest(BaseModel):
    pdf_path: str


