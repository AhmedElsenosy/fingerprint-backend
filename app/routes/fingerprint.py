from fastapi import APIRouter, HTTPException, Depends, Request
from app.schemas.student import StudentBase
from app.utils.fingerprint import enroll_fingerprint
from app.utils.fingerprint import connect_device
from app.dependencies.auth import get_current_assistant
import subprocess
import httpx
import os
from datetime import date
from dotenv import load_dotenv

load_dotenv()
HOST_REMOTE_URL = os.getenv("HOST_REMOTE_URL")

router = APIRouter(
    prefix="/students",
    tags=["Students"],
)

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


@router.post("/register")
async def register_student_with_fingerprint(
    data: StudentBase,
    request: Request,
    current_assistant: dict = Depends(get_current_assistant)
):
    configure_network()

    # Step 1: Get UID and student_id from main backend
    token = request.headers.get("authorization")
    headers = {"Authorization": token} if token else {}

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{HOST_REMOTE_URL}/students/next-ids", headers=headers)

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to get UID and student_id from main backend")

    identifiers = response.json()
    uid = identifiers["uid"]
    student_id = identifiers["student_id"]

    # Step 2: Enroll fingerprint
    template = enroll_fingerprint(uid, f"{data.first_name}_{data.last_name}")
    if not template:
        raise HTTPException(status_code=500, detail="Failed to enroll fingerprint")

    # Step 3: Prepare full payload to main backend
    student_payload = data.dict()
    if isinstance(student_payload.get("birth_date"), date):
        student_payload["birth_date"] = student_payload["birth_date"].isoformat()

    student_payload.update({
        "student_id": student_id,
        "uid": uid,
        "is_subscription": True,
        "fingerprint_template": template
    })

    # Step 4: Send student data to main backend
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{HOST_REMOTE_URL}/students/",
            json=student_payload,
            headers=headers
        )

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Main backend error: {response.text}")

    created_student = response.json()
    # Optionally, use created_student["uid"] and ["student_id"] for further logic

    return {
        "message": "Student created successfully via fingerprint",
        "data": created_student
    }


@router.delete("/delete_fingerprint/{student_id}")
async def delete_fingerprint(student_id: int):
    configure_network()
    try:
        conn = connect_device()
        # Try to delete user
        try:
            result = conn.delete_user(student_id)
        except Exception as e:
            # If the error is "user not found", treat as success
            if "not found" in str(e).lower() or "no such user" in str(e).lower():
                return {"message": "Fingerprint already deleted or not found"}
            raise

        # Some SDKs return None/False if user not found, treat as success
        if result is False or result is None:
            return {"message": "Fingerprint already deleted or not found"}

        return {"message": "Fingerprint deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
