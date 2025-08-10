from beanie import Document
from datetime import datetime
from pydantic import Field

class FingerprintSession(Document):
    student_id: int
    name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "fingerprint_sessions"
