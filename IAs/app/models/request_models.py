from pydantic import BaseModel

class PromptRequest(BaseModel):
    prompt: str
    agents: int = 3
    rounds: int = 3
