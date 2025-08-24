from fastapi import APIRouter, HTTPException, Depends, Request
from app.schemas.student import StudentBase
from app.utils.fingerprint import enroll_fingerprint
from app.utils.multi_device_fingerprint import enroll_fingerprint_multi_device, device_manager, delete_student_from_all_devices
from app.utils.fingerprint import connect_device
from app.dependencies.auth import get_current_assistant
from app.models.student import Student
from app.models.missing_student import MissingStudent
from app.utils.internet_check import check_internet_connectivity
from app.utils.local_id_generator import get_next_student_id_offline, sync_local_counter_with_remote, initialize_student_counter, peek_next_student_id_offline, increment_student_counter
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

@router.get("/", summary="List students (newest first)")
async def list_students(skip: int = 0, limit: int = 100):
    """
    Return students sorted by most recently added first.
    Uses the document id timestamp for ordering (descending).
    """
    try:
        students = await Student.find_all().sort(-Student.id).skip(skip).limit(limit).to_list()
        return {"count": len(students), "data": students}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch students: {e}")

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

    # Step 1: Check internet connectivity
    online = await check_internet_connectivity()

    # Step 2: Get UID and student_id based on connectivity (WITHOUT incrementing counters)
    if online:
        token = request.headers.get("authorization")
        headers = {"Authorization": token} if token else {}

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(f"{HOST_REMOTE_URL}/students/next-ids", headers=headers)

            if response.status_code != 200:
                raise HTTPException(status_code=500, detail="Failed to get UID and student_id from main backend")

            identifiers = response.json()
            uid = identifiers["uid"]
            student_id = identifiers["student_id"]

            # Sync local counter with remote (this sets the counter to match, doesn't increment)
            await sync_local_counter_with_remote(uid - 1)  # Set to one less so next peek gives the right value
        except (httpx.ConnectTimeout, httpx.TimeoutException, httpx.RequestError) as e:
            print(f"⚠️ Connection timeout or error when getting IDs from main backend: {e}")
            print("🔄 Falling back to offline mode...")
            online = False
            # Fall through to offline mode
            ids = await peek_next_student_id_offline()  # Use peek instead of get to avoid incrementing
            uid = ids["uid"]
            student_id = ids["student_id"]
    else:
        # Offline: get local IDs WITHOUT incrementing
        ids = await peek_next_student_id_offline()  # Use peek instead of get to avoid incrementing
        uid = ids["uid"]
        student_id = ids["student_id"]

    # Step 3: Enroll fingerprint using multi-device system with enhanced error handling
    print(f"🔍 Starting fingerprint enrollment for {data.first_name} {data.last_name} (UID: {uid})")
    
    # First attempt at enrollment
    enrollment_result = enroll_fingerprint_multi_device(uid, f"{data.first_name}_{data.last_name}", device_manager)
    
    # If enrollment failed, check if it's due to user already existing
    if not enrollment_result["success"]:
        error_msg = enrollment_result.get("error", "").lower()
        
        # Check if the error is related to user already existing
        if "already exists" in error_msg or "user with uid" in error_msg or "duplicate" in error_msg:
            print(f"⚠️ Detected 'user already exists' error. Attempting to delete student UID={uid} from all devices...")
            
            # Delete the student from all devices
            delete_result = delete_student_from_all_devices(uid, device_manager)
            print(f"🗑️ Deletion result: {delete_result['message']}")
            
            if delete_result["success"] or len(delete_result["deleted_from_devices"]) > 0:
                print(f"🔄 Retrying enrollment after deletion...")
                
                # Retry enrollment after deletion
                enrollment_result = enroll_fingerprint_multi_device(uid, f"{data.first_name}_{data.last_name}", device_manager)
                
                if enrollment_result["success"]:
                    print(f"✅ Enrollment successful after deletion and retry!")
                else:
                    print(f"❌ Enrollment still failed after deletion and retry: {enrollment_result['error']}")
            else:
                print(f"❌ Failed to delete user from devices: {delete_result['message']}")
    
    # If still failed after potential retry, try single device fallback
    if not enrollment_result["success"]:
        # Multi-device enrollment failed, try single device fallback
        print(f"⚠️ Multi-device enrollment failed: {enrollment_result['error']}. Trying single device fallback.")
        template = enroll_fingerprint(uid, f"{data.first_name}_{data.last_name}")
        if not template:
            # BOTH multi-device and single device enrollment failed
            # DO NOT INCREMENT COUNTER - enrollment completely failed
            final_error_msg = f"Fingerprint enrollment failed on all devices. Multi-device error: {enrollment_result['error']}. Please try again or check device connectivity."
            print(f"❌ {final_error_msg}")
            raise HTTPException(
                status_code=500, 
                detail=final_error_msg
            )
        # Single device fallback succeeded
        device_used = None
        print(f"✅ Fingerprint enrolled successfully using single device fallback")
    else:
        template = enrollment_result["template"]
        device_used = enrollment_result["device_used"]
        print(f"✅ Fingerprint enrolled successfully on device {device_used['name']} ({device_used['location']})")

    # Step 4: Handle online vs offline modes
    if online:
        # ONLINE MODE: Send to remote backend
        student_payload = data.dict()
        if isinstance(student_payload.get("birth_date"), date):
            student_payload["birth_date"] = student_payload["birth_date"].isoformat()

        student_payload.update({
            "student_id": student_id,
            "uid": uid,
            "is_subscription": True,
            "fingerprint_template": template
        })

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{HOST_REMOTE_URL}/students/",
                    json=student_payload,
                    headers=headers
                )

            if response.status_code != 200:
                error_text = response.text
                print(f"❌ Main backend error (status {response.status_code}): {error_text}")
                
                # Check if the error is due to blacklist
                if "blacklist" in error_text.lower() or "same name" in error_text.lower():
                    print(f"⚠️ Detected blacklist error. Attempting to delete student UID={uid} from all fingerprint devices...")
                    
                    # Delete the student from all fingerprint devices
                    delete_result = delete_student_from_all_devices(uid, device_manager)
                    print(f"🗑️ Fingerprint deletion result: {delete_result['message']}")
                    
                    # Enhance the error message to include deletion info
                    enhanced_error = f"Student creation failed due to blacklist restriction. Student has been automatically removed from fingerprint devices. Original error: {error_text}"
                    if delete_result["success"]:
                        enhanced_error += f" Successfully deleted from {len(delete_result['deleted_from_devices'])} fingerprint devices."
                    else:
                        enhanced_error += f" Warning: Failed to delete from some fingerprint devices: {delete_result.get('failed_devices', [])}."
                    
                    raise HTTPException(status_code=response.status_code, detail=enhanced_error)
                else:
                    # Other main backend error
                    raise HTTPException(status_code=500, detail=f"Main backend error: {error_text}")
            
            created_student = response.json()
            
            # INCREMENT COUNTER AFTER SUCCESSFUL CREATION (online mode)
            # Since we successfully created the student, we can now safely increment the local counter
            await increment_student_counter()
            
            # Store in local students collection
            try:
                local_student = Student(
                    uid=uid,
                    student_id=str(student_id),
                    first_name=data.first_name,
                    last_name=data.last_name,
                    email=data.email,
                    phone_number=data.phone_number,
                    guardian_number=data.guardian_number,
                    birth_date=data.birth_date,
                    national_id=data.national_id,
                    gender=data.gender,
                    level=data.level,
                    school_name=data.school_name,
                    is_subscription=True,
                    fingerprint_template=template
                )
                await local_student.insert()
                print(f"✅ Student {data.first_name} {data.last_name} stored in local database")
            except Exception as e:
                print(f"⚠️ Warning: Failed to store student in local database: {e}")

            return {
                "message": "Student created successfully via fingerprint and stored locally",
                "data": created_student
            }
            
        except (httpx.ConnectTimeout, httpx.TimeoutException, httpx.RequestError) as e:
            print(f"⚠️ Connection timeout or error when creating student on main backend: {e}")
            print("🔄 Falling back to offline mode...")
            online = False
            # Fall through to offline mode - create student locally and add to sync queue
    
    # OFFLINE MODE or FALLBACK MODE: Save to both students and missing_students collections
    if not online:
        # OFFLINE MODE: Save to both students and missing_students collections
        try:
            # Save to regular students collection
            local_student = Student(
                uid=uid,
                student_id=str(student_id),
                first_name=data.first_name,
                last_name=data.last_name,
                email=data.email,
                phone_number=data.phone_number,
                guardian_number=data.guardian_number,
                birth_date=data.birth_date,
                national_id=data.national_id,
                gender=data.gender,
                level=data.level,
                school_name=data.school_name,
                is_subscription=True,
                fingerprint_template=template
            )
            await local_student.insert()
            print(f"✅ Student {data.first_name} {data.last_name} stored in local students database")

            # Also save to missing_students collection for later sync
            missing_student = MissingStudent(
                uid=uid,
                student_id=str(student_id),
                first_name=data.first_name,
                last_name=data.last_name,
                email=data.email,
                phone_number=data.phone_number,
                guardian_number=data.guardian_number,
                birth_date=data.birth_date,
                national_id=data.national_id,
                gender=data.gender,
                level=data.level,
                school_name=data.school_name,
                is_subscription=True,
                fingerprint_template=template
            )
            await missing_student.insert()
            print(f"✅ Student {data.first_name} {data.last_name} also stored in missing_students for later sync")
            
            # INCREMENT COUNTER AFTER SUCCESSFUL CREATION (offline mode)
            # Since we successfully created the student locally, we can now safely increment the counter
            await increment_student_counter()

        except Exception as e:
            print(f"❌ Failed to store student in databases: {e}")
            raise HTTPException(status_code=500, detail="Failed to store student data locally")

        return {
            "message": "Student created successfully via fingerprint and stored locally (offline mode)",
            "status": "offline",
            "data": {
                "uid": uid,
                "student_id": student_id,
                "first_name": data.first_name,
                "last_name": data.last_name,
                "email": data.email,
                "fingerprint_enrolled": True
            }
        }


@router.delete("/delete_fingerprint/{student_id}")
async def delete_fingerprint(student_id: int):
    configure_network()
    
    # Step 1: Delete from fingerprint device
    try:
        conn = connect_device()
        # Try to delete user
        try:
            result = conn.delete_user(student_id)
        except Exception as e:
            # If the error is "user not found", treat as success
            if "not found" in str(e).lower() or "no such user" in str(e).lower():
                print(f"⚠️ Fingerprint for student_id {student_id} already deleted or not found")
            else:
                raise
        
        # Some SDKs return None/False if user not found, treat as success
        if result is False or result is None:
            print(f"⚠️ Fingerprint for student_id {student_id} already deleted or not found")
            
    except Exception as e:
        print(f"⚠️ Warning: Failed to delete fingerprint from device: {e}")
        # Continue with database deletion even if fingerprint deletion fails
    
    # Step 2: Delete from local database
    try:
        # Find student by uid (since student_id in our database might be stored as string)
        student = await Student.find_one(Student.uid == student_id)
        if student:
            await student.delete()
            print(f"✅ Student with UID {student_id} deleted from local database")
            return {"message": "Student fingerprint and data deleted successfully"}
        else:
            print(f"⚠️ Student with UID {student_id} not found in local database")
            return {"message": "Fingerprint deleted, but student not found in local database"}
    except Exception as e:
        print(f"⚠️ Warning: Failed to delete student from local database: {e}")
        return {"message": "Fingerprint deleted, but failed to delete from local database"}


@router.delete("/delete_from_all_devices/{uid}")
async def delete_from_all_fingerprint_devices(uid: int):
    """
    Delete a student from all fingerprint devices.
    Useful for fixing "user already exists" errors.
    """
    configure_network()
    
    print(f"🗑️ Attempting to delete UID={uid} from all fingerprint devices")
    
    # Use the multi-device deletion function
    delete_result = delete_student_from_all_devices(uid, device_manager)
    
    return {
        "uid": uid,
        "success": delete_result["success"],
        "message": delete_result["message"],
        "deleted_from_devices": delete_result["deleted_from_devices"],
        "failed_devices": delete_result.get("failed_devices", []),
        "note": "This only deletes the fingerprint from devices, not from the database. Use the regular delete endpoint to remove from database as well."
    }


@router.post("/init-counter")
async def init_counter(start_value: int = 10018):
    """
    Initialize the local student counter to a specific value.
    Use this to set the starting point for student IDs.
    """
    success = await initialize_student_counter(start_value)
    if success:
        return {"message": f"Student counter initialized to {start_value}"}
    else:
        raise HTTPException(status_code=500, detail="Failed to initialize counter")


@router.get("/connectivity-status")
async def connectivity_status():
    """
    Check the current internet connectivity status.
    """
    online = await check_internet_connectivity()
    return {
        "online": online,
        "status": "connected" if online else "offline",
        "remote_url": HOST_REMOTE_URL
    }


@router.get("/fingerprint-device-status")
async def fingerprint_device_status():
    """
    Check fingerprint device connectivity and status.
    Useful for troubleshooting enrollment timeouts.
    """
    from app.utils.fingerprint import connect_device
    
    # Test single device connection
    single_device_status = {
        "connected": False,
        "error": None,
        "device_info": None
    }
    
    try:
        conn = connect_device()
        if conn:
            try:
                # Test basic device operations
                users = conn.get_users()
                user_count = len(users) if users else 0
                
                single_device_status = {
                    "connected": True,
                    "error": None,
                    "device_info": {
                        "ip": "192.168.1.201",
                        "port": 4370,
                        "user_count": user_count,
                        "firmware_version": getattr(conn, 'firmware_version', 'Unknown'),
                        "device_name": getattr(conn, 'device_name', 'Unknown')
                    }
                }
                conn.disconnect()
            except Exception as e:
                single_device_status["error"] = f"Connected but device operations failed: {str(e)}"
                try:
                    conn.disconnect()
                except:
                    pass
        else:
            single_device_status["error"] = "Failed to connect to device"
    except Exception as e:
        single_device_status["error"] = f"Connection error: {str(e)}"
    
    # Test multi-device manager status
    multi_device_status = device_manager.get_device_status()
    
    return {
        "single_device": single_device_status,
        "multi_device": multi_device_status,
        "recommendations": {
            "timeout_issues": [
                "Ensure finger is properly placed on scanner during enrollment",
                "Check if device is busy with another operation",
                "Verify network connectivity to fingerprint device",
                "Try enrolling again after a few seconds"
            ],
            "connection_issues": [
                "Check device IP address and port",
                "Ensure device is powered on and network accessible",
                "Verify firewall settings allow connection to device port",
                "Check network cable connections"
            ]
        }
    }


@router.get("/missing-students")
async def get_missing_students():
    """
    Get all students that were created offline and need to be synced.
    """
    from app.models.missing_student import SyncStatus
    
    missing_students = await MissingStudent.find_all().to_list()
    
    # Count by status
    status_counts = {
        "pending": 0,
        "syncing": 0,
        "synced": 0,
        "failed": 0,
        "invalid": 0
    }
    
    for student in missing_students:
        status_counts[student.sync_status] += 1
    
    return {
        "total_count": len(missing_students),
        "status_counts": status_counts,
        "students": missing_students
    }


@router.post("/sync-missing-students")
async def manual_sync_missing_students():
    """
    Manually trigger sync of missing students.
    """
    from app.models.missing_student import SyncStatus
    
    # Check internet connectivity
    online = await check_internet_connectivity()
    if not online:
        raise HTTPException(status_code=503, detail="No internet connection available")
    
    # Get count of pending students
    pending_count = await MissingStudent.find(
        {"sync_status": SyncStatus.pending}
    ).count()
    
    if pending_count == 0:
        return {"message": "No pending students to sync"}
    
    return {
        "message": f"Found {pending_count} pending students. Background sync will process them automatically.",
        "pending_count": pending_count,
        "note": "Background sync runs every minute when internet is available"
    }


@router.post("/cleanup-synced-students")
async def cleanup_synced_students():
    """
    Clean up students that are marked as synced but still exist in missing_students collection.
    This is useful when the deletion process failed after successful sync.
    """
    from app.models.missing_student import SyncStatus
    
    try:
        # Find all students marked as synced
        synced_students = await MissingStudent.find(
            {"sync_status": SyncStatus.synced}
        ).to_list()
        
        if len(synced_students) == 0:
            return {"message": "No synced students found in missing_students collection"}
        
        deleted_count = 0
        failed_deletions = []
        
        for student in synced_students:
            try:
                await student.delete()
                deleted_count += 1
                print(f"✅ Cleaned up synced student {student.first_name} {student.last_name} from missing_students")
            except Exception as e:
                failed_deletions.append({
                    "uid": student.uid,
                    "name": f"{student.first_name} {student.last_name}",
                    "error": str(e)
                })
                print(f"❌ Failed to clean up student {student.first_name} {student.last_name}: {e}")
        
        result = {
            "message": f"Cleanup completed. Deleted {deleted_count} synced students from missing_students collection.",
            "deleted_count": deleted_count,
            "total_found": len(synced_students)
        }
        
        if failed_deletions:
            result["failed_deletions"] = failed_deletions
            result["failed_count"] = len(failed_deletions)
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cleanup synced students: {str(e)}")
