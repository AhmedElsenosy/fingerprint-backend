from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel
from app.utils.fingerprint import connect_device
from app.utils.multi_device_fingerprint import device_manager, DeviceInfo
from datetime import datetime, date
import subprocess
import asyncio
import pytz
import httpx
from app.models.fingerprint_session import FingerprintSession
from app.models.student import Student
from app.utils.internet_check import check_internet_connectivity
from dotenv import load_dotenv
import os
from typing import List, Dict
import json

# Connection Manager to handle WebSocket connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        # Create a copy of the list to avoid issues if connections change during iteration
        connections_to_remove = []
        for connection in self.active_connections[:]:
            try:
                await connection.send_text(message)
            except Exception as e:
                print(f"⚠️ Error broadcasting to connection: {e}")
                connections_to_remove.append(connection)
        
        # Remove dead connections
        for connection in connections_to_remove:
            if connection in self.active_connections:
                self.active_connections.remove(connection)

manager = ConnectionManager()

# Store pending attendance decisions
pending_decisions: Dict[str, Dict] = {}

load_dotenv()
HOST_REMOTE_URL = os.getenv("HOST_REMOTE_URL")

router = APIRouter(prefix="/fingerprint", tags=["Fingerprint Attendance"])

is_attendance_running = False
attendance_task = None

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


async def send_attendance_to_server(uid: int, timestamp: str):
    """Send attendance to main backend for validation and storage"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{HOST_REMOTE_URL}/attendance/",
                json={
                    "uid": uid,
                    "timestamp": timestamp
                }
            )
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": response.text, "status_code": response.status_code}
    except httpx.HTTPError as e:
        return {"success": False, "error": str(e), "status_code": 500}

async def send_attendance_to_server_approved(uid: int, timestamp: str):
    """Send assistant-approved attendance to main backend (bypasses schedule validation)"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{HOST_REMOTE_URL}/attendance/",
                json={
                    "uid": uid,
                    "timestamp": timestamp,
                    "assistant_approved": True  # This bypasses schedule validation
                }
            )
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": response.text, "status_code": response.status_code}
    except httpx.HTTPError as e:
        return {"success": False, "error": str(e), "status_code": 500}

async def capture_from_device(device: DeviceInfo):
    """Capture fingerprints from a specific device"""
    configure_network()
    conn = device.connection  # Use the existing connection from device manager
    
    if not conn:
        print(f"❌ No connection available for device {device.name}")
        return
    
    try:
        print(f"📡 Listening for fingerprint on device {device.name} ({device.location})...")
        online = await check_internet_connectivity()
        mode = "ONLINE" if online else "OFFLINE"
        print(f"🌐 Device {device.name} - Mode: {mode}")
        
        for attendance in conn.live_capture():
            if not device_manager.is_capture_running():
                print(f"🛑 Attendance stopped on device {device.name}. Exiting capture loop.")
                break
            
            if attendance is not None:
                if online:
                    now_cairo = datetime.now(pytz.timezone("Africa/Cairo"))
                    print(f"🔍 (ONLINE MODE - {device.name}) Attendance captured: UID={attendance.uid}, Time={now_cairo}")
                    
                    # Store in FingerprintSession (existing log)
                    session = FingerprintSession(
                        student_id=attendance.uid,
                        name="",
                        timestamp=now_cairo
                    )
                    await session.insert()
                    
                    # Get student info for broadcasting
                    student = await Student.find_one(Student.uid == attendance.uid)
                    student_name = f"{student.first_name} {student.last_name}" if student else "Unknown Student"
                    
                    # Broadcast attendance capture event with device info
                    await manager.broadcast(
                        f"Online attendance captured: UID={attendance.uid}, Time={now_cairo}, Name={student_name}, Device={device.name}, Location={device.location}, Status=Processing..."
                    )
                    
                    # First, validate through main backend
                    validation_result = await send_attendance_to_server(attendance.uid, now_cairo.isoformat())
                    
                    if validation_result["success"]:
                        # Main backend approved - now save locally
                        try:
                            if student:
                                # Initialize attendance dict if it doesn't exist
                                if not hasattr(student, "attendance") or not isinstance(student.attendance, dict):
                                    student.attendance = {}
                                
                                # Calculate day key based on existing attendance entries
                                day_index = len(student.attendance) + 1
                                day_key = f"day{day_index}"
                                
                                # Mark attendance as true
                                student.attendance[day_key] = True
                                await student.save()
                                
                                backend_data = validation_result["data"]
                                
                                # Broadcast approval event with device info
                                await manager.broadcast(
                                    f"✅ APPROVED: UID={attendance.uid}, Name={student_name}, Device={device.name}, Location={device.location}, Group={backend_data.get('group', 'Unknown')}, Day={day_key}, Status=Present"
                                )
                                
                                print(f"✅ Device {device.name}: Student {student.first_name} {student.last_name} attendance approved and saved as {day_key}")
                                print(f"📊 Group: {backend_data.get('group', 'Unknown')}, Status: Present")
                            else:
                                await manager.broadcast(
                                    f"⚠️ WARNING: UID={attendance.uid} approved by backend but student not found in local database (Device: {device.name})"
                                )
                                print(f"⚠️ Device {device.name}: Student with UID {attendance.uid} not found in local database")
                        except Exception as e:
                            await manager.broadcast(
                                f"⚠️ ERROR: UID={attendance.uid}, Name={student_name}, Device={device.name} - Failed to save locally: {str(e)}"
                            )
                            print(f"⚠️ Device {device.name}: Failed to update student attendance locally: {e}")
                    else:
                        # Main backend rejected - check if it's a wrong group situation
                        error_msg = validation_result.get("error", "Unknown error")
                        status_code = validation_result.get("status_code", "Unknown")
                        
                        # Check if this is a "wrong group day" error that needs assistant decision
                        if (status_code == 400 and 
                            ("Attendance not allowed on" in str(error_msg) or 
                             "Group schedule" in str(error_msg))):
                            
                            # This is a wrong group situation - ask assistant for decision
                            decision_id = f"{attendance.uid}_{int(now_cairo.timestamp())}"
                            
                            # Store pending decision with device info
                            pending_decisions[decision_id] = {
                                "uid": attendance.uid,
                                "student_name": student_name,
                                "timestamp": now_cairo.isoformat(),
                                "error_msg": error_msg,
                                "student": student,
                                "device_id": device.device_id,
                                "device_name": device.name,
                                "device_location": device.location
                            }
                            
                            # Create decision request message with device info
                            decision_request = {
                                "type": "decision_request",
                                "decision_id": decision_id,
                                "uid": attendance.uid,
                                "student_name": student_name,
                                "timestamp": now_cairo.isoformat(),
                                "reason": error_msg,
                                "device_name": device.name,
                                "device_location": device.location,
                                "message": f"⚠️ DECISION NEEDED: Student {student_name} (UID: {attendance.uid}) is trying to attend at {device.name} ({device.location}) but belongs to different group. Reason: {error_msg}"
                            }
                            
                            # Broadcast decision request
                            await manager.broadcast(json.dumps(decision_request))
                            
                            print(f"⏳ PENDING DECISION: Device {device.name}, UID={attendance.uid}, Student={student_name}, Waiting for assistant approval...")
                            
                        else:
                            # Other type of rejection - auto reject
                            await manager.broadcast(
                                f"❌ REJECTED: UID={attendance.uid}, Name={student_name}, Device={device.name}, Location={device.location}, Reason={error_msg}, Status_Code={status_code}"
                            )
                            
                            print(f"❌ Device {device.name}: Attendance rejected for UID {attendance.uid}: {error_msg} (Status: {status_code})")
                else:
                    # Offline mode: Save attendance locally without validation
                    now_cairo = datetime.now(pytz.timezone("Africa/Cairo"))
                    print(f"📝 (OFFLINE MODE - {device.name}) Attendance captured: UID={attendance.uid}, Time={now_cairo}")
                    
                    # Store in FingerprintSession (for logging)
                    session = FingerprintSession(
                        student_id=attendance.uid,
                        name="",
                        timestamp=now_cairo
                    )
                    await session.insert()
                    
                    # Find student by UID
                    student = await Student.find_one(Student.uid == attendance.uid)
                    if student:
                        if not hasattr(student, "attendance") or not isinstance(student.attendance, dict):
                            student.attendance = {}
                        
                        # Calculate day key based on existing attendance entries
                        day_index = len(student.attendance) + 1
                        day_key = f"day{day_index}_offline"
                        
                        # Mark attendance as offline with timestamp and device info
                        student.attendance[day_key] = {
                            "status": True,
                            "timestamp": now_cairo.isoformat(),
                            "synced": False,
                            "device_id": device.device_id,
                            "device_name": device.name,
                            "device_location": device.location
                        }
                        await student.save()
                        
                        # Broadcast the offline attendance event with device info
                        await manager.broadcast(
                            f"Offline attendance captured: UID={attendance.uid}, Time={now_cairo}, Name={student.first_name} {student.last_name}, Device={device.name}, Location={device.location}"
                        )
                        
                        print(f"✅ (OFFLINE MODE - {device.name}) Student {student.first_name} {student.last_name} attendance saved as {day_key}")
                    else:
                        print(f"⚠️ (OFFLINE MODE - {device.name}) Student with UID {attendance.uid} not found in local database")
            
            await asyncio.sleep(0.2)
    
    except Exception as e:
        print(f"❌ Device {device.name} attendance error: {e}")
        device.status = "error"
        device.error_message = str(e)
    
    finally:
        print(f"⚠️ Device {device.name} fingerprint capture ended")


async def start_fingerprint_capture():
    global is_attendance_running

    configure_network()
    conn = connect_device()

    if not conn:
        print("❌ Could not connect to fingerprint device. Attendance not started.")
        is_attendance_running = False
        return

    try:
        print("📡 Listening for fingerprint...")
        online = await check_internet_connectivity()
        mode = "ONLINE" if online else "OFFLINE"
        print(f"🌐 Mode: {mode}")

        for attendance in conn.live_capture():
            if not is_attendance_running:
                print("🛑 Attendance stopped. Exiting capture loop.")
                break

            if attendance is not None:
                if online:
                    now_cairo = datetime.now(pytz.timezone("Africa/Cairo"))
                    print(f"🔍 (ONLINE MODE) Attendance captured: UID={attendance.uid}, Time={now_cairo}")

                    # Store in FingerprintSession (existing log)
                    session = FingerprintSession(
                        student_id=attendance.uid,
                        name="",
                        timestamp=now_cairo
                    )
                    await session.insert()

                    # Get student info for broadcasting
                    student = await Student.find_one(Student.uid == attendance.uid)
                    student_name = f"{student.first_name} {student.last_name}" if student else "Unknown Student"

                    # Broadcast attendance capture event
                    await manager.broadcast(
                        f"Online attendance captured: UID={attendance.uid}, Time={now_cairo}, Name={student_name}, Status=Processing..."
                    )

                    # First, validate through main backend
                    validation_result = await send_attendance_to_server(attendance.uid, now_cairo.isoformat())
                    
                    if validation_result["success"]:
                        # Main backend approved - now save locally
                        try:
                            if student:
                                # Initialize attendance dict if it doesn't exist
                                if not hasattr(student, "attendance") or not isinstance(student.attendance, dict):
                                    student.attendance = {}
                                
                                # Calculate day key based on existing attendance entries
                                day_index = len(student.attendance) + 1
                                day_key = f"day{day_index}"
                                
                                # Mark attendance as true
                                student.attendance[day_key] = True
                                await student.save()
                                
                                backend_data = validation_result["data"]
                                
                                # Broadcast approval event
                                await manager.broadcast(
                                    f"✅ APPROVED: UID={attendance.uid}, Name={student_name}, Group={backend_data.get('group', 'Unknown')}, Day={day_key}, Status=Present"
                                )
                                
                                print(f"✅ Student {student.first_name} {student.last_name} attendance approved and saved as {day_key}")
                                print(f"📊 Group: {backend_data.get('group', 'Unknown')}, Status: Present")
                            else:
                                await manager.broadcast(
                                    f"⚠️ WARNING: UID={attendance.uid} approved by backend but student not found in local database"
                                )
                                print(f"⚠️ Student with UID {attendance.uid} not found in local database")
                        except Exception as e:
                            await manager.broadcast(
                                f"⚠️ ERROR: UID={attendance.uid}, Name={student_name} - Failed to save locally: {str(e)}"
                            )
                            print(f"⚠️ Warning: Failed to update student attendance locally: {e}")
                    else:
                        # Main backend rejected - check if it's a wrong group situation
                        error_msg = validation_result.get("error", "Unknown error")
                        status_code = validation_result.get("status_code", "Unknown")
                        
                        # Check if this is a "wrong group day" error that needs assistant decision
                        if (status_code == 400 and 
                            ("Attendance not allowed on" in str(error_msg) or 
                             "Group schedule" in str(error_msg))):
                            
                            # This is a wrong group situation - ask assistant for decision
                            decision_id = f"{attendance.uid}_{int(now_cairo.timestamp())}"
                            
                            # Store pending decision
                            pending_decisions[decision_id] = {
                                "uid": attendance.uid,
                                "student_name": student_name,
                                "timestamp": now_cairo.isoformat(),
                                "error_msg": error_msg,
                                "student": student
                            }
                            
                            # Create decision request message
                            decision_request = {
                                "type": "decision_request",
                                "decision_id": decision_id,
                                "uid": attendance.uid,
                                "student_name": student_name,
                                "timestamp": now_cairo.isoformat(),
                                "reason": error_msg,
                                "message": f"⚠️ DECISION NEEDED: Student {student_name} (UID: {attendance.uid}) is trying to attend but belongs to different group. Reason: {error_msg}"
                            }
                            
                            # Broadcast decision request
                            await manager.broadcast(json.dumps(decision_request))
                            
                            print(f"⏳ PENDING DECISION: UID={attendance.uid}, Student={student_name}, Waiting for assistant approval...")
                            
                        else:
                            # Other type of rejection - auto reject
                            await manager.broadcast(
                                f"❌ REJECTED: UID={attendance.uid}, Name={student_name}, Reason={error_msg}, Status_Code={status_code}"
                            )
                            
                            print(f"❌ Attendance rejected for UID {attendance.uid}: {error_msg} (Status: {status_code})")
                else:
                    # Offline mode: Save attendance locally without validation
                    now_cairo = datetime.now(pytz.timezone("Africa/Cairo"))
                    print(f"📝 (OFFLINE MODE) Attendance captured: UID={attendance.uid}, Time={now_cairo}")

                    # Store in FingerprintSession (for logging)
                    session = FingerprintSession(
                        student_id=attendance.uid,
                        name="",
                        timestamp=now_cairo
                    )
                    await session.insert()

                    # Find student by UID
                    student = await Student.find_one(Student.uid == attendance.uid)
                    if student:
                        if not hasattr(student, "attendance") or not isinstance(student.attendance, dict):
                            student.attendance = {}

                        # Calculate day key based on existing attendance entries
                        day_index = len(student.attendance) + 1
                        day_key = f"day{day_index}_offline"

                        # Mark attendance as offline with timestamp
                        student.attendance[day_key] = {
                            "status": True,
                            "timestamp": now_cairo.isoformat(),
                            "synced": False
                        }
                        await student.save()

                        # Broadcast the offline attendance event
                        await manager.broadcast(
                            f"Offline attendance captured: UID={attendance.uid}, Time={now_cairo}, Name={student.first_name} {student.last_name}"
                        )

                        print(f"✅ (OFFLINE MODE) Student {student.first_name} {student.last_name} attendance saved as {day_key}")
                    else:
                        print(f"⚠️ (OFFLINE MODE) Student with UID {attendance.uid} not found in local database")

            await asyncio.sleep(0.2)
    except Exception as e:
        print(f"❌ Attendance error: {e}")
    finally:
        conn.disconnect()
        print("⚠️ Fingerprint device disconnected")

@router.post("/start_attendance")
async def start_attendance():
    """Start attendance capture on all enabled devices"""
    global is_attendance_running, attendance_task

    if device_manager.is_capture_running():
        raise HTTPException(status_code=400, detail="Multi-device attendance already running")
    
    # Try to start multi-device capture first
    result = await device_manager.start_all_capture_tasks(capture_from_device)
    
    if result["success"]:
        # Multi-device mode succeeded
        return {
            "message": result["message"],
            "mode": "multi-device",
            "devices_started": result["devices_started"],
            "total_devices": result["total_devices"]
        }
    else:
        # Multi-device failed, fall back to single device mode
        print(f"⚠️ Multi-device startup failed: {result['message']}. Falling back to single device mode.")
        
        if is_attendance_running:
            raise HTTPException(status_code=400, detail="Single-device attendance already running")

        is_attendance_running = True
        attendance_task = asyncio.create_task(start_fingerprint_capture())
        return {
            "message": "✅ Fingerprint attendance started (single-device fallback)",
            "mode": "single-device",
            "fallback_reason": result["message"]
        }

@router.post("/stop_attendance")
async def stop_attendance():
    """Stop attendance capture on all devices"""
    global is_attendance_running, attendance_task
    
    stopped_devices = False
    stopped_single = False
    
    # Try to stop multi-device capture
    if device_manager.is_capture_running():
        result = await device_manager.stop_all_capture_tasks()
        if result["success"]:
            stopped_devices = True
    
    # Try to stop single-device capture
    if is_attendance_running:
        is_attendance_running = False
        
        # Cancel the attendance task if it's still running
        if attendance_task and not attendance_task.done():
            attendance_task.cancel()
            try:
                await attendance_task
            except asyncio.CancelledError:
                pass
        
        stopped_single = True
    
    if not stopped_devices and not stopped_single:
        raise HTTPException(status_code=400, detail="No attendance system is currently running")
    
    messages = []
    if stopped_devices:
        messages.append("Multi-device attendance stopped")
    if stopped_single:
        messages.append("Single-device attendance stopped")
    
    return {
        "message": "🛑 " + " and ".join(messages),
        "multi_device_stopped": stopped_devices,
        "single_device_stopped": stopped_single
    }


@router.get("/attendance-status")
async def get_attendance_status():
    """Get current attendance system status (both single and multi-device)"""
    multi_device_running = device_manager.is_capture_running()
    single_device_running = is_attendance_running
    
    return {
        "single_device": {
            "is_running": single_device_running,
            "task_status": "running" if attendance_task and not attendance_task.done() else "stopped"
        },
        "multi_device": {
            "is_running": multi_device_running,
            "active_tasks": len(device_manager.capture_tasks),
            "total_devices": len(device_manager.get_enabled_devices())
        },
        "overall_status": "running" if (multi_device_running or single_device_running) else "stopped",
        "remote_backend": HOST_REMOTE_URL
    }


@router.get("/devices")
async def get_all_devices():
    """Get information about all configured devices"""
    devices_status = device_manager.get_device_status()
    return {
        "total_devices": len(devices_status),
        "enabled_devices": len(device_manager.get_enabled_devices()),
        "devices": devices_status
    }


@router.get("/devices/{device_id}")
async def get_device_info(device_id: str):
    """Get information about a specific device"""
    device = device_manager.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
    
    device_status = device_manager.get_device_status()
    return device_status.get(device_id, {})


@router.post("/devices/{device_id}/test-connection")
async def test_device_connection(device_id: str):
    """Test connection to a specific device"""
    device = device_manager.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
    
    # Test connection
    conn = device_manager.connect_device(device)
    if conn:
        device_manager.disconnect_device(device)
        return {
            "success": True,
            "message": f"Successfully connected to device {device.name}",
            "device_info": {
                "name": device.name,
                "location": device.location,
                "ip": device.ip,
                "port": device.port
            }
        }
    else:
        return {
            "success": False,
            "message": f"Failed to connect to device {device.name}",
            "error": device.error_message,
            "device_info": {
                "name": device.name,
                "location": device.location,
                "ip": device.ip,
                "port": device.port
            }
        }


@router.get("/student-attendance/{uid}")
async def get_student_attendance(uid: int):
    """Get attendance record for a specific student"""
    student = await Student.find_one(Student.uid == uid)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    return {
        "uid": uid,
        "student": f"{student.first_name} {student.last_name}",
        "attendance": student.attendance if hasattr(student, 'attendance') else {},
        "total_days": len(student.attendance) if hasattr(student, 'attendance') else 0
    }


@router.get("/pending-decisions")
async def get_pending_decisions():
    """Get all pending attendance decisions waiting for assistant approval"""
    return {
        "pending_count": len(pending_decisions),
        "decisions": [
            {
                "decision_id": decision_id,
                "uid": data["uid"],
                "student_name": data["student_name"],
                "timestamp": data["timestamp"],
                "reason": data["error_msg"]
            }
            for decision_id, data in pending_decisions.items()
        ]
    }


@router.post("/assistant-decision/{decision_id}")
async def make_assistant_decision(decision_id: str, decision: str = Query(..., description="Decision: 'approve' or 'reject'")):
    """REST endpoint for assistant to approve/reject attendance
    
    Args:
        decision_id: The ID of the pending decision
        decision: 'approve' or 'reject' (query parameter)
    """
    if decision.lower() not in ["approve", "reject"]:
        raise HTTPException(status_code=400, detail="Decision must be 'approve' or 'reject'")
    
    result = await process_assistant_decision(decision_id, decision)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


async def process_assistant_decision(decision_id: str, decision: str):
    """Process assistant's approve/reject decision"""
    if decision_id not in pending_decisions:
        return {"success": False, "error": "Decision ID not found or already processed"}
    
    pending_data = pending_decisions[decision_id]
    student = pending_data["student"]
    
    if decision.lower() == "approve":
        # Assistant approved - save attendance locally
        try:
            if student:
                if not hasattr(student, "attendance") or not isinstance(student.attendance, dict):
                    student.attendance = {}
                
                day_index = len(student.attendance) + 1
                day_key = f"day{day_index}"
                
                student.attendance[day_key] = True
                await student.save()
                
                # Send attendance to main backend with assistant_approved=True
                try:
                    response = await send_attendance_to_server_approved(pending_data['uid'], pending_data['timestamp'])
                    if not response['success']:
                        raise Exception(response['error'])

                except Exception as e:
                    await manager.broadcast(
                        f"⚠️ ERROR: Failed to send to main backend for UID={pending_data['uid']}: {str(e)}"
                    )
                    return {"success": False, "error": str(e)}
                
                # Broadcast approval
                await manager.broadcast(
                    f"✅ ASSISTANT APPROVED: UID={pending_data['uid']}, Name={pending_data['student_name']}, Day={day_key}, Status=Present (Manual Override)"
                )
                
                print(f"✅ ASSISTANT APPROVED: UID={pending_data['uid']}, Student={pending_data['student_name']}, Day={day_key}")
                
                # Remove from pending
                del pending_decisions[decision_id]
                return {"success": True, "message": "Attendance approved and saved"}
            
        except Exception as e:
            await manager.broadcast(
                f"⚠️ ERROR: Failed to save approved attendance for UID={pending_data['uid']}: {str(e)}"
            )
            return {"success": False, "error": str(e)}
    
    elif decision.lower() == "reject":
        # Assistant rejected - don't save
        await manager.broadcast(
            f"❌ ASSISTANT REJECTED: UID={pending_data['uid']}, Name={pending_data['student_name']}, Status=Absent (Manual Decision)"
        )
        
        print(f"❌ ASSISTANT REJECTED: UID={pending_data['uid']}, Student={pending_data['student_name']}")
        
        # Remove from pending
        del pending_decisions[decision_id]
        return {"success": True, "message": "Attendance rejected"}
    
    return {"success": False, "error": "Invalid decision. Use 'approve' or 'reject'"}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time attendance updates and assistant decisions"""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            
            try:
                # Try to parse as JSON for decision responses
                message = json.loads(data)
                
                if message.get("type") == "decision_response":
                    decision_id = message.get("decision_id")
                    decision = message.get("decision")  # "approve" or "reject"
                    
                    if decision_id and decision:
                        result = await process_assistant_decision(decision_id, decision)
                        await websocket.send_text(json.dumps(result))
                    else:
                        await websocket.send_text(json.dumps({"error": "Missing decision_id or decision"}))
                else:
                    await websocket.send_text(f"Message received: {data}")
                    
            except json.JSONDecodeError:
                # Not JSON, treat as regular message
                await websocket.send_text(f"Message received: {data}")
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
