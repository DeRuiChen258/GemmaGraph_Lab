import json
import re

from pydantic import BaseModel, Field


class FixPlan(BaseModel):
    summary: str = Field(min_length=8, max_length=1200)
    files: list[str] = Field(default_factory=list, max_length=5)
    evidence_ids: list[str] = Field(default_factory=list)
    validation: list[str] = Field(default_factory=list, max_length=8)


class Reflection(BaseModel):
    failure_type: str = Field(max_length=100)
    evidence_gap: str = Field(default="", max_length=600)
    next_step: str = Field(pattern="^(retrieve|replan|regenerate|stop)$")
    summary: str = Field(max_length=1000)


def parse_json_output(text: str):
    value = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", value, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        value = fenced.group(1)
    return json.loads(value)
