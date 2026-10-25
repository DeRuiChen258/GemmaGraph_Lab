from pydantic import BaseModel


class Symbol(BaseModel):
    id: str
    path: str
    name: str
    kind: str
    start_line: int
    end_line: int
    source_hash: str
    text: str


class Relation(BaseModel):
    source: str
    target: str
    kind: str
    confidence: str = "static"


class CodeIndex(BaseModel):
    version: str = "python-ast-v1"
    tree_hash: str
    symbols: list[Symbol]
    relations: list[Relation]
    diagnostics: list[dict]
    file_count: int
    python_count: int
    parsed_count: int
