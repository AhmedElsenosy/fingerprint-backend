from pydantic import BaseModel, EmailStr, Field
from datetime import date, datetime
from typing import Optional
from enum import Enum



class Level(int, Enum):
    level1 = 1
    level2 = 2
    level3 = 3

class Gender(str, Enum):
    male = "male"
    female = "female"


class StudentBase(BaseModel):
    first_name: str
    last_name: str
    email: Optional[EmailStr] = Field(default=None)
    phone_number: str
    guardian_number: str
    birth_date: Optional[date] = Field(default=None)
    national_id: Optional[str] = Field(default=None)
    gender: Gender
    level: Level
    school_name: Optional[str] = Field(default=None)
    
    class Config:
        # Allow None values for optional fields
        use_enum_values = True
        validate_assignment = True
