import httpx
from fastapi import APIRouter, HTTPException
from app.utils.fingerprint import connect_device
from datetime import datetime
import subprocess
import asyncio
import pytz
import os
from dotenv import load_dotenv

load_dotenv()
HOST_REMOTE_URL = os.getenv("HOST_REMOTE_URL")

router = APIRouter(prefix="/fingerprint", tags=["Fingerprint Attendance"])

def configure_network():
    result = subprocess.run(
        ["ip", "addr", "show", "enx00e04c361694"],
        capture_output=True, text=True
    )
    if "192.168.1.100/24" not in result.stdout:
        subprocess.run(
            ["sudo", "ip", "addr", "add", "192.168.1.100/24", "dev", "enx00e04c361694"],
            check=True
        )
    subprocess.run(["sudo", "ip", "link", "set", "enx00e04c361694", "up"], check=True)

@router.post("/attendance")
async def record_live_attendance(duration: int = 30):
    """
    Live attendance capture for multiple students within a time window (default 30 seconds).
    """
    configure_network()
    conn = connect_device()
    if not conn:
        raise HTTPException(status_code=500, detail="❌ Cannot connect to fingerprint device")

    try:
        print("🔒 Disabling device...")
        conn.disable_device()

        print("📥 Fetching initial attendance logs...")
        initial_logs = conn.get_attendance() or []
        initial_log_ids = set((log.user_id, log.timestamp) for log in initial_logs)
        print(f"🗂️ Initial logs: {len(initial_logs)}")

        detected_students = []

        for _ in range(duration):
            new_logs = conn.get_attendance() or []
            for log in new_logs:
                log_key = (log.user_id, log.timestamp)
                if log_key not in initial_log_ids:
                    initial_log_ids.add(log_key)
                    uid = log.user_id
                    egypt_tz = pytz.timezone("Africa/Cairo")
                    timestamp = datetime.now(egypt_tz).isoformat()

                    print(f"✅ UID {uid} identified at {timestamp}")
                    print("🌐 Sending data to main backend...")

                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            f"{HOST_REMOTE_URL}/attendance/",
                            json={"uid": uid, "timestamp": timestamp}
                        )

                    print(f"📨 Main backend response: {response.status_code} {response.text}")
                    if response.status_code == 200:
                        detected_students.append({"uid": uid, "timestamp": timestamp})
                    else:
                        detected_students.append({"uid": uid, "timestamp": timestamp, "error": response.text})

            await asyncio.sleep(1)

        if not detected_students:
            raise HTTPException(status_code=408, detail="⏰ Timeout: No fingerprints detected")

        return {
            "message": f"✅ Attendance captured for {len(detected_students)} student(s)",
            "students": detected_students
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"❌ Attendance error: {e}")

    finally:
        print("🔓 Re-enabling and disconnecting device...")
        conn.enable_device()
        conn.disconnect()