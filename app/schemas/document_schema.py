from typing import Dict, Any
from pydantic import BaseModel


class AdminDocManualCreate(BaseModel):
    title: str
    metadata_json: Dict[str, Any]
