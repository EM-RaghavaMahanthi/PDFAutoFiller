from pydantic import BaseModel

class ExtractRequest(BaseModel):
    config_path: str

class MapFieldsRequest(BaseModel):
    config_path: str

class FillRequest(BaseModel):
    config_path: str

class ValidateRequest(BaseModel):
    config_path: str