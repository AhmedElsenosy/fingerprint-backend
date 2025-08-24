from fastapi import FastAPI
from app.models.counter import Counter
from app.models.fingerprint_session import FingerprintSession
from app.models.student import Student
from app.database import init_db
from app.models.missing_student import MissingStudent
from app.routes import fingerprint, fingerprint_attendance, exam_correction, bubble
from fastapi.middleware.cors import CORSMiddleware
from app.services.sync_service import sync_missing_students_worker

# Socket.IO imports
import socketio
from fastapi import Request
import uvicorn

# Background task
import asyncio

app = FastAPI()

# Create Socket.IO server
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://xthw34nm-8001.uks1.devtunnels.ms",
        "*"  # Allow all origins for development
    ],
    logger=True,
    engineio_logger=True
)

# Wrap FastAPI app with Socket.IO
socket_app = socketio.ASGIApp(sio, app)

# Initialize Socket.IO manager
from app.utils.socketio_manager import init_socketio

# Socket.IO event handlers
@sio.event
async def connect(sid, environ, auth):
    print(f"✅ Socket.IO client connected: {sid}")
    await sio.emit('connection_status', {'status': 'connected', 'message': 'Connected to fingerprint attendance system'})

@sio.event
async def disconnect(sid):
    print(f"❌ Socket.IO client disconnected: {sid}")

@app.on_event("startup")
async def startup_event():
    await init_db()
    
    # Initialize Socket.IO manager
    init_socketio(sio)
    
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
    allow_origins=["http://localhost:3000"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://xthw34nm-8001.uks1.devtunnels.ms"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Make the Socket.IO app available for uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(socket_app, host="0.0.0.0", port=8001)
else:
    # For uvicorn to import
    app = socket_app
