from fastapi import FastAPI
from app.models.counter import Counter
from app.models.fingerprint_session import FingerprintSession
from app.models.student import Student
from app.models.missing_student import MissingStudent
from app.database import init_db
from app.routes import fingerprint, fingerprint_attendance, exam_correction, bubble
from fastapi.middleware.cors import CORSMiddleware
from app.services.sync_service import sync_missing_students_worker

# Background task
import asyncio

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    await init_db()
    
    # Start background sync task
    asyncio.create_task(sync_missing_students_worker())
    print("✅ Background sync task started!")

# Include your routes
app.include_router(fingerprint.router)
app.include_router(fingerprint_attendance.router)
app.include_router(exam_correction.router)
app.include_router(bubble.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)