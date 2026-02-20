from pydantic import BaseModel
from typing import Any, List, Dict

class ProcessResponse(BaseModel):
    rounds: List[Any]
    final_report: str
    scores: Dict[str, float]
