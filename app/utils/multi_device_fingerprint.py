import json
import os
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
import base64
from zk import ZK
from dataclasses import dataclass
from enum import Enum


class DeviceStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    CONNECTING = "connecting"


@dataclass
class DeviceInfo:
    device_id: str
    ip: str
    port: int
    name: str
    location: str
    enabled: bool
    status: DeviceStatus = DeviceStatus.OFFLINE
    connection: Optional[Any] = None
    last_heartbeat: Optional[datetime] = None
    error_message: Optional[str] = None


class MultiDeviceManager:
    def __init__(self, config_file: str = "devices_config.json"):
        self.config_file = config_file
        self.devices: Dict[str, DeviceInfo] = {}
        self.capture_tasks: Dict[str, asyncio.Task] = {}
        self.is_running = False
        self._load_device_config()
    
    def _load_device_config(self):
        """Load device configuration from JSON file"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), "..", "..", self.config_file)
            with open(config_path, 'r') as f:
                devices_config = json.load(f)
            
            self.devices = {}
            for device_config in devices_config:
                device_info = DeviceInfo(
                    device_id=device_config["device_id"],
                    ip=device_config["ip"],
                    port=device_config["port"],
                    name=device_config["name"],
                    location=device_config["location"],
                    enabled=device_config.get("enabled", True)
                )
                self.devices[device_info.device_id] = device_info
            
            print(f"✅ Loaded {len(self.devices)} devices from config")
            
        except FileNotFoundError:
            print(f"⚠️ Config file {self.config_file} not found. Using default device.")
            # Fallback to single device for backward compatibility
            self.devices = {
                "default": DeviceInfo(
                    device_id="default",
                    ip="192.168.1.201",
                    port=4370,
                    name="Default Device",
                    location="Main Location",
                    enabled=True
                )
            }
        except Exception as e:
            print(f"❌ Error loading device config: {e}")
            self.devices = {}
    
    def get_enabled_devices(self) -> List[DeviceInfo]:
        """Get list of enabled devices"""
        return [device for device in self.devices.values() if device.enabled]
    
    def get_device(self, device_id: str) -> Optional[DeviceInfo]:
        """Get specific device by ID"""
        return self.devices.get(device_id)
    
    def get_all_devices(self) -> Dict[str, DeviceInfo]:
        """Get all devices"""
        return self.devices
    
    def connect_device(self, device: DeviceInfo) -> Optional[Any]:
        """Connect to a specific fingerprint device"""
        try:
            print(f"🔌 Connecting to device {device.name} ({device.ip}:{device.port})")
            device.status = DeviceStatus.CONNECTING
            
            zk = ZK(device.ip, port=device.port, timeout=5)
            conn = zk.connect()
            
            if conn:
                device.connection = conn
                device.status = DeviceStatus.ONLINE
                device.last_heartbeat = datetime.now()
                device.error_message = None
                print(f"✅ Connected to device {device.name}")
                return conn
            else:
                device.status = DeviceStatus.ERROR
                device.error_message = "Connection failed"
                print(f"❌ Failed to connect to device {device.name}")
                return None
                
        except Exception as e:
            device.status = DeviceStatus.ERROR
            device.error_message = str(e)
            print(f"❌ Connection error for device {device.name}: {e}")
            return None
    
    def disconnect_device(self, device: DeviceInfo):
        """Disconnect from a specific device"""
        try:
            if device.connection:
                device.connection.disconnect()
                device.connection = None
            device.status = DeviceStatus.OFFLINE
            print(f"🔌 Disconnected from device {device.name}")
        except Exception as e:
            print(f"⚠️ Error disconnecting from device {device.name}: {e}")
    
    def connect_all_devices(self) -> Dict[str, bool]:
        """Connect to all enabled devices"""
        results = {}
        enabled_devices = self.get_enabled_devices()
        
        print(f"🔌 Connecting to {len(enabled_devices)} devices...")
        
        for device in enabled_devices:
            conn = self.connect_device(device)
            results[device.device_id] = conn is not None
        
        connected_count = sum(results.values())
        print(f"✅ Connected to {connected_count}/{len(enabled_devices)} devices")
        
        return results
    
    def disconnect_all_devices(self):
        """Disconnect from all devices"""
        for device in self.devices.values():
            if device.connection:
                self.disconnect_device(device)
    
    def get_device_status(self) -> Dict[str, Dict]:
        """Get status of all devices"""
        status = {}
        for device_id, device in self.devices.items():
            status[device_id] = {
                "name": device.name,
                "location": device.location,
                "ip": device.ip,
                "port": device.port,
                "enabled": device.enabled,
                "status": device.status,
                "last_heartbeat": device.last_heartbeat.isoformat() if device.last_heartbeat else None,
                "error_message": device.error_message,
                "connected": device.connection is not None
            }
        return status
    
    async def start_all_capture_tasks(self, capture_function):
        """Start capture tasks for all enabled and connected devices"""
        if self.is_running:
            print("⚠️ Capture tasks already running")
            return {"success": False, "message": "Already running"}
        
        enabled_devices = self.get_enabled_devices()
        if not enabled_devices:
            return {"success": False, "message": "No enabled devices found"}
        
        # Connect to all devices first
        connection_results = self.connect_all_devices()
        connected_devices = [
            device for device in enabled_devices 
            if connection_results.get(device.device_id, False)
        ]
        
        if not connected_devices:
            return {"success": False, "message": "No devices connected successfully"}
        
        # Start capture tasks for connected devices
        self.capture_tasks = {}
        self.is_running = True
        
        for device in connected_devices:
            print(f"🚀 Starting capture task for device {device.name}")
            task = asyncio.create_task(capture_function(device))
            self.capture_tasks[device.device_id] = task
        
        print(f"✅ Started capture on {len(connected_devices)} devices")
        
        return {
            "success": True,
            "message": f"Started attendance on {len(connected_devices)} devices",
            "devices_started": [device.name for device in connected_devices],
            "total_devices": len(connected_devices)
        }
    
    async def stop_all_capture_tasks(self):
        """Stop all capture tasks and disconnect devices"""
        if not self.is_running:
            return {"success": False, "message": "Not currently running"}
        
        self.is_running = False
        
        # Cancel all capture tasks
        cancelled_count = 0
        for device_id, task in self.capture_tasks.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                cancelled_count += 1
                print(f"🛑 Stopped capture task for device {device_id}")
        
        # Disconnect all devices
        self.disconnect_all_devices()
        self.capture_tasks = {}
        
        print(f"✅ Stopped {cancelled_count} capture tasks and disconnected all devices")
        
        return {
            "success": True,
            "message": f"Stopped attendance on {cancelled_count} devices",
            "tasks_stopped": cancelled_count
        }
    
    def is_capture_running(self) -> bool:
        """Check if any capture tasks are running"""
        return self.is_running and len(self.capture_tasks) > 0


# Multi-device enrollment functions
def enroll_fingerprint_multi_device(uid: int, name: str, device_manager: MultiDeviceManager) -> Dict[str, Any]:
    """
    Enroll fingerprint on the first available device
    Returns enrollment result with device info
    """
    enabled_devices = device_manager.get_enabled_devices()
    
    if not enabled_devices:
        return {
            "success": False,
            "error": "No enabled devices available",
            "template": None,
            "device_used": None
        }
    
    # Try each device until one succeeds
    for device in enabled_devices:
        conn = device_manager.connect_device(device)
        if not conn:
            continue
            
        try:
            print(f"🔍 Enrolling fingerprint for UID={uid}, Name={name} on device {device.name}")
            conn.disable_device()

            # Delete user if exists
            users = conn.get_users()
            user_exists = any(u.uid == uid for u in users)
            if user_exists:
                print(f"⚠️ User with UID={uid} already exists on {device.name}. Deleting first.")
                conn.delete_user(uid=uid)

            # Set user on the device
            conn.set_user(
                uid=uid,
                name=name,
                privilege=0,
                password='',
                group_id='',
                user_id=str(uid)
            )

            # Enroll user
            try:
                conn.enroll_user(uid, 0, 0)
            except Exception as enroll_err:
                print(f"⚠️ enroll_user with 3 args failed: {enroll_err}. Trying with 2 args...")
                try:
                    conn.enroll_user(uid, 0)
                except Exception as fallback_err:
                    print(f"❌ Both enrollment attempts failed: {fallback_err}")
                    continue

            # Get fingerprint template
            template = conn.get_user_template(uid, 0)
            if not template:
                print(f"❌ No fingerprint template retrieved from {device.name}")
                continue

            # Extract raw fingerprint data
            if hasattr(template, "template"):
                raw = template.template
            elif hasattr(template, "serialize"):
                raw = template.serialize()
            elif isinstance(template, str):
                raw = template.encode()
            else:
                print(f"❌ Unsupported fingerprint template format on {device.name}")
                continue

            # Encode to base64
            encoded_template = base64.b64encode(raw).decode()
            print(f"✅ Fingerprint enrolled successfully on device {device.name}")
            
            return {
                "success": True,
                "template": encoded_template,
                "device_used": {
                    "device_id": device.device_id,
                    "name": device.name,
                    "location": device.location,
                    "ip": device.ip
                },
                "error": None
            }

        except Exception as e:
            print(f"❌ Enrollment error on device {device.name}: {e}")
            continue
        
        finally:
            try:
                conn.enable_device()
                device_manager.disconnect_device(device)
            except:
                pass
    
    return {
        "success": False,
        "error": "Failed to enroll on any available device",
        "template": None,
        "device_used": None
    }


# Create global device manager instance
device_manager = MultiDeviceManager()
