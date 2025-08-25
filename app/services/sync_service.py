import asyncio
from app.models.missing_student import MissingStudent, SyncStatus
from app.models.student import Student
from app.utils.internet_check import check_internet_connectivity
import httpx
from datetime import datetime, date
import os
from dotenv import load_dotenv

load_dotenv()
HOST_REMOTE_URL = os.getenv("HOST_REMOTE_URL")


async def send_attendance_to_server(uid: int, timestamp: str):
    """Send attendance to main backend for validation and storage"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{HOST_REMOTE_URL}/attendance/",
                json={
                    "uid": uid,
                    "timestamp": timestamp
                },
                timeout=30.0
            )
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                error_msg = f"Main backend error (HTTP {response.status_code}): {response.text}"
                print(f"⚠️ {error_msg}")
                return {"success": False, "error": error_msg, "status_code": response.status_code}
    except httpx.HTTPError as e:
        error_msg = f"HTTP error: {str(e)}"
        print(f"⚠️ {error_msg}")
        return {"success": False, "error": error_msg, "status_code": 500}
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"⚠️ {error_msg}")
        return {"success": False, "error": error_msg, "status_code": 500}


async def sync_offline_attendance():
    print("🔄 Checking for offline attendance to sync...")

    # Fetch students with offline attendance
    students_with_offline = await Student.find(
        {"attendance": {"$exists": True, "$ne": {}}}
    ).to_list()

    offline_count = 0
    for student in students_with_offline:
        # Extract days with offline attendance
        offline_days = {k: v for k, v in student.attendance.items() if k.endswith("_offline")}
        
        if offline_days:
            offline_count += len(offline_days)

        for day_key, attendance_data in offline_days.items():
            if not attendance_data.get("synced", False):
                try:
                    # Send each offline attendance to main backend
                    response = await send_attendance_to_server(student.uid, attendance_data["timestamp"])

                    if response["success"]:
                        # Approved - update day key to remove _offline
                        new_day_key = day_key.replace("_offline", "")
                        student.attendance[new_day_key] = True
                        del student.attendance[day_key]  # Remove old entry
                        print(f"✅ Synced offline attendance for UID {student.uid} ({student.first_name} {student.last_name}) as {new_day_key}")
                    else:
                        # Rejected - remove the offline attendance
                        del student.attendance[day_key]
                        print(f"❌ Rejected offline attendance for UID {student.uid} ({student.first_name} {student.last_name}): {response.get('error', 'Unknown error')}")

                    # Save changes
                    await student.save()

                except Exception as e:
                    print(f"❌ Error syncing offline attendance for UID {student.uid}: {e}")
    
    if offline_count == 0:
        print("✅ No offline attendance to sync.")


async def sync_missing_students_worker():
    """
    Background task that attempts to sync missing students to the remote backend.
    Runs every minute and handles all failure scenarios gracefully.
    """
    while True:
        print("🔄 Running sync task for missing students...")

        # Check if internet is available
        online = await check_internet_connectivity()
        if not online:
            print("🚫 No internet connection. Sync task will retry in 60 seconds.")
            await asyncio.sleep(60)
            continue

        try:
            # Fetch unsynced students (pending or failed with less than 3 attempts)
            unsynced_students = await MissingStudent.find(
                {
                    "$or": [
                        {"sync_status": SyncStatus.pending},
                        {"sync_status": SyncStatus.failed, "sync_attempts": {"$lt": 3}}
                    ]
                }
            ).to_list()
            
            print(f"Found {len(unsynced_students)} students to sync.")

            for student in unsynced_students:
                # Attempt to sync each student
                try:
                    student.sync_status = SyncStatus.syncing
                    student.last_sync_attempt = datetime.now()
                    await student.save()

                    # Prepare student data for remote backend
                    student_data = student.dict(exclude={
                        "sync_status", "sync_attempts", "last_sync_attempt", 
                        "sync_error", "synced_at", "created_offline_at", "id"
                    })
                    
                    # Convert date to string format
                    if isinstance(student_data.get("birth_date"), date):
                        student_data["birth_date"] = student_data["birth_date"].isoformat()
                    
                    # Check if student already exists on remote backend first
                    async with httpx.AsyncClient(timeout=30) as client:
                        # Check if student exists
                        check_response = await client.get(
                            f"{HOST_REMOTE_URL}/students/{student.uid}"
                        )
                        
                        if check_response.status_code == 200:
                            # Student already exists, mark as synced and delete from missing_students
                            student.sync_status = SyncStatus.synced
                            student.synced_at = datetime.now()
                            await student.save()  # Save the updated status first
                            
                            # Delete from missing_students with retry mechanism
                            try:
                                await student.delete()
                                print(f"✅ Student {student.first_name} {student.last_name} already exists on remote backend and removed from missing_students.")
                            except Exception as delete_error:
                                print(f"⚠️ Warning: Failed to delete student {student.first_name} {student.last_name} from missing_students: {delete_error}")
                                # Try force delete by finding student by UID
                                try:
                                    missing_student = await MissingStudent.find_one(MissingStudent.uid == student.uid)
                                    if missing_student:
                                        await missing_student.delete()
                                        print(f"✅ Force deleted student {student.first_name} {student.last_name} from missing_students.")
                                except Exception as force_error:
                                    print(f"❌ Forcasynce delete failed for {student.first_name} {student.last_name}: {force_error}")
                            continue
                        
                        # Student doesn't exist, create it
                        # Note: Sync service runs in background without request context
                        # Using empty headers for now - consider implementing service token
                        headers = {}
                        response = await client.post(
                            f"{HOST_REMOTE_URL}/students/",
                            json=student_data,
                            headers=headers,
                            timeout=30
                        )

                    if response.status_code in [200, 201]:  # Accept both 200 (OK) and 201 (Created) as success
                        # Student successfully synced, now remove from missing_students
                        student.sync_status = SyncStatus.synced
                        student.synced_at = datetime.now()
                        await student.save()  # Save the updated status first
                        
                        # Delete from missing_students with retry mechanism
                        try:
                            await student.delete()  # Remove from missing_students collection after successful sync
                            print(f"✅ Synced student {student.first_name} {student.last_name} to remote backend and removed from missing_students.")
                        except Exception as delete_error:
                            print(f"⚠️ Warning: Failed to delete student {student.first_name} {student.last_name} from missing_students: {delete_error}")
                            # Try force delete by finding student by UID
                            try:
                                missing_student = await MissingStudent.find_one(MissingStudent.uid == student.uid)
                                if missing_student:
                                    await missing_student.delete()
                                    print(f"✅ Force deleted student {student.first_name} {student.last_name} from missing_students.")
                            except Exception as force_error:
                                print(f"❌ Force delete failed for {student.first_name} {student.last_name}: {force_error}")
                    else:
                        student.sync_status = SyncStatus.failed
                        student.sync_error = f"Failed with status {response.status_code}: {response.text}"
                        print(f"⚠️ Failed to sync student {student.first_name} {student.last_name}. Error: {student.sync_error}")

                except Exception as e:
                    student.sync_status = SyncStatus.failed
                    student.sync_error = str(e)
                    print(f"❌ Exception while syncing student {student.first_name} {student.last_name}. Error: {student.sync_error}")

                finally:
                    student.sync_attempts += 1
                    await student.save()

            # Also cleanup any students that are marked as synced but still in missing_students
            await cleanup_synced_students_from_missing()
            
            # Sync offline attendance
            await sync_offline_attendance()
            
            await asyncio.sleep(60)

        except Exception as e:
            print(f"❌ Critical error in sync task: {e}")
            await asyncio.sleep(60)


async def cleanup_synced_students_from_missing():
    """
    Clean up any students that are marked as synced but still exist in missing_students collection.
    This is a safety mechanism to ensure no synced students remain in the collection.
    """
    try:
        synced_students = await MissingStudent.find(
            {"sync_status": SyncStatus.synced}
        ).to_list()
        
        if len(synced_students) > 0:
            print(f"🧹 Found {len(synced_students)} synced students still in missing_students collection. Cleaning up...")
            
            for student in synced_students:
                try:
                    await student.delete()
                    print(f"✅ Cleaned up synced student {student.first_name} {student.last_name} from missing_students")
                except Exception as e:
                    print(f"❌ Failed to cleanup synced student {student.first_name} {student.last_name}: {e}")
                    
    except Exception as e:
        print(f"⚠️ Error during synced students cleanup: {e}")
