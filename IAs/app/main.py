from fastapi import FastAPI
from app.orchestrator.controller import process_prompt
from app.models.request_models import PromptRequest

app = FastAPI()

@app.post("/process")
async def run_process(request: PromptRequest):
    result = await process_prompt(request)
    return result
