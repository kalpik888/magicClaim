from pydantic import BaseModel, Field
from typing import List

class DamagedParts(BaseModel):
    """Consolidated report of damaged parts from all images."""
    parts: List[str] = Field(
        description="A unique, consolidated list of all damaged car parts identified across all provided images."
    )