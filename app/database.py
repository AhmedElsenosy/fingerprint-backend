from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
import os
from dotenv import load_dotenv

from app.models.fingerprint_session import FingerprintSession
from app.models.student import Student
from app.models.counter import Counter
from app.models.missing_student import MissingStudent

load_dotenv()

MONGODB_URL = os.getenv("MONGO_URI", "mongodb://localhost:27017")

async def init_db():
    client = AsyncIOMotorClient(MONGODB_URL)
    await init_beanie(database=client[os.getenv("DATABASE_NAME", "teacher_app_offline")], document_models=[FingerprintSession, Student, Counter, MissingStudent])
