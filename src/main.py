from fastapi import FastAPI
from src.api import extract_route
from src.api import map_route
from src.api import fill_route

app = FastAPI()



@app.get("/")
def home():
    return {"message": "PDF Automation API"}

app.include_router(extract_route.router)


app.include_router(map_route.router)


app.include_router(fill_route.router)
