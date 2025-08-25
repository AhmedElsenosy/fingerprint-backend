#!/usr/bin/env python3
"""
Simple Scanner Connection Module
===============================

This module provides a simple interface for connecting to scanner devices only.

Requirements:
- python-sane library: pip install python-sane
- SANE backend installed: sudo apt-get install sane-utils libsane1

Author: Ahmed
Date: 2025-08-10
"""

import sane
import sys
from typing import List, Tuple, Optional

class ScannerConnection:
    """
    Simple class to manage scanner device connection only.
    """
    
    def __init__(self):
        """Initialize the scanner connection."""
        self.scanner = None
        self.scanner_name = None
        self.is_connected = False
        
        # Initialize SANE
        try:
            sane.init()
            print("✅ SANE initialized successfully")
        except Exception as e:
            print(f"❌ Failed to initialize SANE: {e}")
            raise
    
    def list_scanners(self) -> List[Tuple[str, str, str, str]]:
        """
        Get a list of available scanner devices.
        
        Returns:
            List of tuples (device_name, vendor, model, type)
        """
        try:
            devices = sane.get_devices()
            print(f"📋 Found {len(devices)} scanner devices")
            
            for i, device in enumerate(devices):
                print(f"  Device {i+1}: {device}")
            
            return devices
        except Exception as e:
            print(f"❌ Error listing scanners: {e}")
            return []
    
    def connect_scanner(self, device_name: Optional[str] = None) -> bool:
        """
        Connect to a scanner device.
        
        Args:
            device_name: Specific device name to connect to. If None, connects to first available.
            
        Returns:
            True if connection successful, False otherwise
        """
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
                
                self.scanner_name = target_device[0]
            else:
                self.scanner_name = devices[0][0]
            
            # Connect to the scanner
            self.scanner = sane.open(self.scanner_name)
            self.is_connected = True
            
            print(f"✅ Connected to scanner: {self.scanner_name}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to connect to scanner: {e}")
            self.is_connected = False
            return False
    
    def get_scanner_info(self) -> dict:
        """
        Get basic information about the connected scanner.
        
        Returns:
            Dictionary with scanner information
        """
        if not self.is_connected or not self.scanner:
            print("❌ No scanner connected")
            return {}
        
        try:
            info = {
                'name': self.scanner_name,
                'connected': self.is_connected,
            }
            
            # Try to get some basic scanner parameters
            try:
                info['resolution'] = getattr(self.scanner, 'resolution', 'Unknown')
            except:
                pass
                
            try:
                info['mode'] = getattr(self.scanner, 'mode', 'Unknown')
            except:
                pass
                
            return info
            
        except Exception as e:
            print(f"❌ Error getting scanner info: {e}")
            return {
                'name': self.scanner_name,
                'connected': self.is_connected
            }
    
    def scan_document(self, output_path: str, resolution: int = 300, mode: str = 'Color') -> bool:
        """
        Scan a document and save to file.
        
        Args:
            output_path: Path to save the scanned image
            resolution: Scan resolution in DPI
            mode: Scan mode ('Color', 'Gray', 'Lineart')
            
        Returns:
            True if scan successful, False otherwise
        """
        if not self.is_connected or not self.scanner:
            print("❌ No scanner connected")
            return False
        
        try:
            # Set scan parameters
            print(f"🔧 Setting scan parameters: {resolution} DPI, {mode} mode")
            
            # IMPORTANT: Force flatbed source instead of document feeder
            # This fixes "Document feeder out of documents" error
            if hasattr(self.scanner, 'source'):
                try:
                    # Try common flatbed source names
                    flatbed_names = ['Flatbed', 'flatbed', 'Platen', 'platen', 'Scanner', 'scanner']
                    current_source = getattr(self.scanner, 'source', None)
                    print(f"🔍 Current scan source: {current_source}")
                    
                    # Get available sources
                    if hasattr(self.scanner, 'get_parameters'):
                        try:
                            params = self.scanner.get_parameters()
                            print(f"📋 Available scanner parameters: {params}")
                        except:
                            pass
                    
                    # Try to set flatbed source
                    for flatbed_name in flatbed_names:
                        try:
                            self.scanner.source = flatbed_name
                            print(f"✅ Scan source set to: {flatbed_name}")
                            break
                        except Exception as e:
                            print(f"⚠️ Could not set source to {flatbed_name}: {e}")
                            continue
                    
                except Exception as e:
                    print(f"⚠️ Could not configure scan source: {e}")
                    print("📝 Continuing with default source...")
            
            # Set resolution if supported
            if hasattr(self.scanner, 'resolution'):
                self.scanner.resolution = resolution
                print(f"✅ Resolution set to {resolution} DPI")
            
            # Set scan mode if supported
            if hasattr(self.scanner, 'mode'):
                self.scanner.mode = mode
                print(f"✅ Scan mode set to {mode}")
            
            print("📷 Starting scan...")
            
            # Additional flatbed enforcement before scan
            try:
                # Force flatbed one more time before scanning
                if hasattr(self.scanner, 'source'):
                    self.scanner.source = 'Flatbed'
                    print(f"🔒 Final source confirmation: {self.scanner.source}")
                    
                # Set scan area to full flatbed (this can help force flatbed mode)
                if hasattr(self.scanner, 'tl_x'):
                    self.scanner.tl_x = 0.0
                if hasattr(self.scanner, 'tl_y'):
                    self.scanner.tl_y = 0.0
                if hasattr(self.scanner, 'br_x') and hasattr(self.scanner, 'br_y'):
                    # Use reasonable A4 size or scanner max
                    try:
                        # Get scanner max dimensions
                        max_x = getattr(self.scanner, 'br_x', 215.0)
                        max_y = getattr(self.scanner, 'br_y', 297.0)
                        self.scanner.br_x = max_x
                        self.scanner.br_y = max_y
                        print(f"📐 Scan area set: (0,0) to ({max_x},{max_y})mm")
                    except:
                        pass
                        
            except Exception as e:
                print(f"⚠️ Pre-scan configuration warning: {e}")
            
            # Try multiple scan approaches to avoid document feeder issues
            scan_success = False
            last_error = None
            
            # Approach 1: Normal scan with flatbed enforcement
            try:
                print("🎯 Attempting scan approach 1: Normal with flatbed enforcement...")
                self.scanner.start()
                scan_success = True
            except Exception as e1:
                last_error = str(e1)
                print(f"❌ Scan approach 1 failed: {e1}")
                
                # Approach 2: Reset scanner and try again with different settings
                try:
                    print("🎯 Attempting scan approach 2: Reset and retry...")
                    # Close and reopen scanner connection
                    temp_name = self.scanner_name
                    self.scanner.close()
                    self.scanner = sane.open(temp_name)
                    
                    # Reapply settings
                    if hasattr(self.scanner, 'source'):
                        self.scanner.source = 'Flatbed'
                    if hasattr(self.scanner, 'resolution'):
                        self.scanner.resolution = resolution
                    if hasattr(self.scanner, 'mode'):
                        self.scanner.mode = mode
                    
                    # Try scan again
                    self.scanner.start()
                    scan_success = True
                    print("✅ Scan approach 2 succeeded!")
                except Exception as e2:
                    last_error = str(e2)
                    print(f"❌ Scan approach 2 failed: {e2}")
                    
                    # Approach 3: Try with minimal settings
                    try:
                        print("🎯 Attempting scan approach 3: Minimal settings...")
                        # Close and reopen again
                        temp_name = self.scanner_name
                        self.scanner.close()
                        self.scanner = sane.open(temp_name)
                        
                        # Set only essential settings
                        if hasattr(self.scanner, 'source'):
                            self.scanner.source = 'Flatbed'
                            
                        self.scanner.start()
                        scan_success = True
                        print("✅ Scan approach 3 succeeded!")
                    except Exception as e3:
                        last_error = str(e3)
                        print(f"❌ Scan approach 3 failed: {e3}")
            
            if not scan_success:
                raise Exception(f"All scan approaches failed. Last error: {last_error}")
            
            # Get the scanned image
            image = self.scanner.snap()
            
            # Save the image
            if hasattr(image, 'save'):
                # PIL Image object
                image.save(output_path)
            else:
                # NumPy array - convert to PIL Image
                from PIL import Image as PILImage
                import numpy as np
                
                if isinstance(image, np.ndarray):
                    pil_image = PILImage.fromarray(image)
                    pil_image.save(output_path)
                else:
                    # Try to save directly
                    with open(output_path, 'wb') as f:
                        f.write(image)
            
            print(f"✅ Document scanned and saved to: {output_path}")
            return True
            
        except Exception as e:
            print(f"❌ Error during scanning: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from the scanner and cleanup."""
        try:
            if self.scanner:
                self.scanner.close()
                print("✅ Scanner disconnected")
            
            self.scanner = None
            self.scanner_name = None
            self.is_connected = False
            
        except Exception as e:
            print(f"❌ Error disconnecting scanner: {e}")
    
    def __del__(self):
        """Cleanup when object is destroyed."""
        self.disconnect()


# Convenience function
def connect_to_scanner(device_name: Optional[str] = None) -> Optional[ScannerConnection]:
    """
    Simple function to connect to a scanner device.
    
    Args:
        device_name: Specific scanner to connect to (optional)
        
    Returns:
        ScannerConnection object if successful, None otherwise
    """
    conn = ScannerConnection()
    
    if conn.connect_scanner(device_name):
        return conn
    else:
        conn.disconnect()
        return None


def list_available_scanners() -> List[Tuple[str, str, str, str]]:
    """
    Get list of available scanners.
    
    Returns:
        List of available scanner devices
    """
    conn = ScannerConnection()
    devices = conn.list_scanners()
    del conn
    return devices


# Example usage
if __name__ == "__main__":
    print("Scanner Connection Test")
    print("=" * 30)
    
    try:
        # List available scanners
        print("\nListing available scanners...")
        devices = list_available_scanners()
        
        if not devices:
            print("\n❌ No scanners found. Make sure:")
            print("1. Scanner is connected and powered on")
            print("2. SANE is installed: sudo apt-get install sane-utils libsane1")
            print("3. python-sane is installed: pip install python-sane")
            print("4. Scanner drivers are installed")
            sys.exit(1)
        
        # Connect to first available scanner
        print("\nConnecting to scanner...")
        connection = connect_to_scanner()
        
        if connection:
            print("\n✅ Successfully connected to scanner!")
            
            # Show scanner info
            scanner_info = connection.get_scanner_info()
            print("\nScanner information:")
            for key, value in scanner_info.items():
                print(f"  {key}: {value}")
                
            # Disconnect
            connection.disconnect()
        
        else:
            print("\n❌ Failed to connect to scanner")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nTroubleshooting:")
        print("1. Install required packages:")
        print("   sudo apt-get install sane-utils libsane1")
        print("   pip install python-sane")
        print("2. Check if scanner is detected:")
        print("   scanimage -L")
        print("3. Test scanner manually:")
        print("   scanimage > test.pnm")
