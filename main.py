from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.models.counter import Counter
# from app.models.counter import Counter
from app.routes import fingerprint, fingerprint_attendance  

app = FastAPI()

@app.on_event("startup")
async def connect_to_db():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["teacher_app"]

    await init_beanie(
        database=db,
        document_models=[
            Counter
        ]
    )

# Include your routes
app.include_router(fingerprint.router)
app.include_router(fingerprint_attendance.router)