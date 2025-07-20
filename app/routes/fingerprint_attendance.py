import httpx
from fastapi import APIRouter, HTTPException
from app.utils.fingerprint import connect_device
from datetime import datetime
import subprocess
import asyncio
import pytz


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
async def record_attendance():
    configure_network()
    conn = connect_device()
    if not conn:
        raise HTTPException(status_code=500, detail="❌ Cannot connect to fingerprint device")

    try:
        print("🔒 Disabling device...")
        conn.disable_device()

        print("📥 Fetching attendance logs...")
        initial_logs = conn.get_attendance() or []
        initial_count = len(initial_logs)
        print(f"🗂️ Initial logs: {initial_count}")

        # Wait for new log up to 30 seconds
        for attempt in range(30):
            new_logs = conn.get_attendance() or []
            print(f"⏱️ Attempt {attempt+1}: {len(new_logs)} logs")

            if len(new_logs) > initial_count:
                last_log = new_logs[-1]
                uid = last_log.user_id
                egypt_tz = pytz.timezone("Africa/Cairo")
                timestamp = datetime.now(egypt_tz).isoformat()

                print(f"✅ UID {uid} identified at {timestamp}")
                print("🌐 Sending data to main backend...")

                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "http://localhost:8000/attendance/",
                        json={"uid": uid, "timestamp": timestamp}
                    )

                print(f"📨 Main backend response: {response.status_code} {response.text}")
                if response.status_code != 200:
                    raise HTTPException(status_code=500, detail=f"Main backend error: {response.text}")

                return {"message": "✅ Attendance sent", "uid": uid}

            await asyncio.sleep(1)

        raise HTTPException(status_code=408, detail="⏰ Timeout: No fingerprint detected")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"❌ Attendance error: {e}")

    finally:
        print("🔓 Re-enabling and disconnecting device...")
        conn.enable_device()
        conn.disconnect()
