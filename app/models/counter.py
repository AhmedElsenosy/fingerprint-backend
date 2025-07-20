from beanie import Document
from pydantic import Field

class Counter(Document):
    name: str
    value: int = Field(default=10010)

    class Settings:
        name = "counters"  