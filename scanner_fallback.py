#!/usr/bin/env python3
"""
Scanner Fallback Module
========================

Alternative scanner implementation using direct scanimage command
to avoid eSCL protocol issues with Canon TS3400.

This bypasses python-sane and uses the scanimage CLI directly.
"""

import subprocess
import os
import sys
from typing import Optional, List, Tuple

class ScannerCommandLine:
    """Scanner using direct scanimage command."""
    
    def __init__(self):
        self.device_name = None
        self.is_connected = False
    
    def list_scanners(self) -> List[Tuple[str, str, str, str]]:
        """List available scanners using scanimage -L"""
        try:
            print("📡 Scanning for devices using scanimage...")
            result = subprocess.run(['scanimage', '-L'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                print(f"❌ scanimage command failed: {result.stderr}")
                return []
            
            devices = []
            lines = result.stdout.strip().split('\n')
            
            print(f"📋 Found {len(lines)} scanner devices:")
            for i, line in enumerate(lines):
                if 'device `' in line:
                    # Parse: device `escl:https://192.168.114.1:443' is a Canon TS3400 series platen scanner
                    device_start = line.find('`') + 1
                    device_end = line.find("'", device_start)
                    device_name = line[device_start:device_end] if device_end > device_start else line[device_start:-1]
                    
                    # Extract vendor/model info
                    info_part = line.split(' is a ')[-1] if ' is a ' in line else 'Unknown'
                    parts = info_part.split()
                    vendor = parts[0] if parts else 'Unknown'
                    model = ' '.join(parts[1:]) if len(parts) > 1 else 'Unknown'
                    
                    device_tuple = (device_name, vendor, model, 'scanner')
                    devices.append(device_tuple)
                    print(f"  Device {i+1}: {device_tuple}")
            
            return devices
            
        except subprocess.TimeoutExpired:
            print("❌ Scanner detection timed out")
            return []
        except FileNotFoundError:
            print("❌ scanimage command not found. Install: sudo apt-get install sane-utils")
            return []
        except Exception as e:
            print(f"❌ Error listing scanners: {e}")
            return []
    
    def connect_scanner(self, device_name: Optional[str] = None) -> bool:
        """Connect to scanner (just store device name)"""
        try:
            devices = self.list_scanners()
            
            if not devices:
                print("❌ No scanner devices found")
                return False
            
            # Use specified device or first available
            if device_name:
                target_device = None
                for device in devices:
                    if device_name in device[0]:
                        target_device = device
                        break
                
                if not target_device:
                    print(f"❌ Scanner device '{device_name}' not found")
                    return False
                
                self.device_name = target_device[0]
            else:
                self.device_name = devices[0][0]
            
            self.is_connected = True
            print(f"✅ Connected to scanner: {self.device_name}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to connect to scanner: {e}")
            self.is_connected = False
            return False
    
    def scan_document(self, output_path: str, resolution: int = 300, mode: str = 'Color') -> bool:
        """Scan document using scanimage command"""
        if not self.is_connected or not self.device_name:
            print("❌ No scanner connected")
            return False
        
        try:
            print(f"📄 Scanning document with scanimage...")
            print(f"🔧 Parameters: {resolution} DPI, {mode} mode")
            
            # Build scanimage command
            cmd = [
                'scanimage',
                '--device-name', self.device_name,
                '--resolution', str(resolution),
                '--format', 'png',
                '--output-file', output_path
            ]
            
            # Set mode
            mode_lower = mode.lower()
            if mode_lower == 'color':
                cmd.extend(['--mode', 'Color'])
            elif mode_lower == 'gray':
                cmd.extend(['--mode', 'Gray'])
            else:
                cmd.extend(['--mode', 'Color'])  # Default to color
            
            # Force flatbed source
            cmd.extend(['--source', 'Flatbed'])
            
            print(f"🚀 Running: {' '.join(cmd)}")
            
            # Execute scan command
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                if os.path.exists(output_path):
                    file_size = os.path.getsize(output_path)
                    print(f"✅ Document scanned successfully: {output_path} ({file_size} bytes)")
                    return True
                else:
                    print(f"❌ Scan completed but file not found: {output_path}")
                    return False
            else:
                print(f"❌ Scan failed: {result.stderr}")
                print(f"📝 Command output: {result.stdout}")
                return False
                
        except subprocess.TimeoutExpired:
            print("❌ Scan timed out (60 seconds)")
            return False
        except Exception as e:
            print(f"❌ Error during scanning: {e}")
            return False
    
    def get_scanner_info(self) -> dict:
        """Get basic scanner info"""
        return {
            'name': self.device_name,
            'connected': self.is_connected,
            'method': 'scanimage_cli'
        }
    
    def disconnect(self):
        """Disconnect (cleanup)"""
        self.device_name = None
        self.is_connected = False
        print("✅ Scanner disconnected")

# Drop-in replacement functions
def connect_to_scanner_cli(device_name: Optional[str] = None) -> Optional[ScannerCommandLine]:
    """Connect to scanner using CLI method"""
    scanner = ScannerCommandLine()
    if scanner.connect_scanner(device_name):
        return scanner
    else:
        return None

if __name__ == "__main__":
    print("Scanner Command Line Test")
    print("=" * 30)
    
    # Test CLI scanner
    scanner = connect_to_scanner_cli()
    if scanner:
        print("✅ CLI Scanner connected")
        info = scanner.get_scanner_info()
        print(f"Scanner info: {info}")
        
        # Test scan (uncomment to actually scan)
        # success = scanner.scan_document('test_cli_scan.png', 300, 'Color')
        # print(f"Scan result: {success}")
        
        scanner.disconnect()
    else:
        print("❌ CLI Scanner failed")
