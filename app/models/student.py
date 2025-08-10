from beanie import Document
from datetime import date
from pydantic import EmailStr, Field
from typing import Optional, Dict, Union, Any
from enum import Enum


class Level(int, Enum):
    level1 = 1
    level2 = 2
    level3 = 3

class Gender(str, Enum):
    male = "male"
    female = "female"


class Student(Document):
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
    attendance: Dict[str, Union[bool, Dict[str, Any]]] = Field(default_factory=dict)  # Format: {"day1": true, "day2_offline": {"status": true, "timestamp": "...", "synced": false}}

    class Settings:
        name = "students"
