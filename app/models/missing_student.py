from beanie import Document
from datetime import date, datetime
from pydantic import EmailStr, Field
from typing import Optional, Dict
from enum import Enum


class Level(int, Enum):
    level1 = 1
    level2 = 2
    level3 = 3

class Gender(str, Enum):
    male = "male"
    female = "female"

class SyncStatus(str, Enum):
    pending = "pending"
    syncing = "syncing"
    synced = "synced"
    failed = "failed"
    invalid = "invalid"


class MissingStudent(Document):
    uid: int
    student_id: str
    first_name: str
    last_name: str
    email: EmailStr
    phone_number: str
    guardian_number: str
    birth_date: date
    national_id: str
    gender: Gender
    level: Level
    school_name: str
    is_subscription: bool = True
    fingerprint_template: Optional[str] = None
    attendance: Dict[str, bool] = Field(default_factory=dict)  # Format: {"2025-01-15": true}
    created_offline_at: datetime = Field(default_factory=datetime.now)  # Track when saved offline
    
    # Sync status tracking
    sync_status: SyncStatus = SyncStatus.pending
    sync_attempts: int = 0
    last_sync_attempt: Optional[datetime] = None
    sync_error: Optional[str] = None
    synced_at: Optional[datetime] = None

    class Settings:
        name = "missing_students"
