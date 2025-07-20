from pydantic import BaseModel, EmailStr
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
    email: EmailStr
    phone_number: str
    guardian_number: str
    birth_date: date
    national_id: str
    gender: Gender
    level: Level
    school_name: str
