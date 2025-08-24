#!/usr/bin/env python3
"""
Simple test script to connect with a fingerprint device
This script attempts to connect to a fingerprint device at IP 192.168.1.201
"""

import socket
import time
import sys

# Configuration
DEVICE_IP = "192.168.1.201"  # Assuming 201 means .201 in local network
DEVICE_PORT = 4370  # Default port for ZKTeco devices
TIMEOUT = 5  # Connection timeout in seconds

def test_tcp_connection(ip, port):
    """Test basic TCP connection to the device"""
    print(f"Testing TCP connection to {ip}:{port}...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(TIMEOUT)
        result = sock.connect_ex((ip, port))
        sock.close()
        
        if result == 0:
            print(f"✓ TCP connection successful to {ip}:{port}")
            return True
        else:
            print(f"✗ TCP connection failed to {ip}:{port}")
            return False
    except Exception as e:
        print(f"✗ Connection error: {e}")
        return False

def ping_device(ip):
    """Test ping connectivity to the device"""
    print(f"Pinging {ip}...")
    
    try:
        import subprocess
        result = subprocess.run(['ping', '-c', '3', ip], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print(f"✓ Ping successful to {ip}")
            return True
        else:
            print(f"✗ Ping failed to {ip}")
            return False
    except Exception as e:
        print(f"✗ Ping error: {e}")
        return False

def test_zkteco_connection(ip, port=4370):
    """Test ZKTeco device specific connection"""
    print(f"Testing ZKTeco device connection to {ip}:{port}...")
    
    try:
        # Simple ZKTeco protocol test - send connect command
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(TIMEOUT)
        sock.connect((ip, port))
        
        # ZKTeco connect command (simplified)
        connect_cmd = b'\x50\x50\x82\x7d\x13\x00\x00\x00\x14\x05\x00\x00\x00\x00\x00\x00'
        sock.send(connect_cmd)
        
        # Wait for response
        response = sock.recv(1024)
        sock.close()
        
        if response:
            print(f"✓ ZKTeco device responded: {len(response)} bytes received")
            return True
        else:
            print(f"✗ No response from ZKTeco device")
            return False
            
    except Exception as e:
        print(f"✗ ZKTeco connection error: {e}")
        return False

def main():
    """Main test function"""
    print("=" * 50)
    print("FINGERPRINT DEVICE CONNECTION TEST")
    print("=" * 50)
    print(f"Target Device: {DEVICE_IP}")
    print(f"Port: {DEVICE_PORT}")
    print(f"Timeout: {TIMEOUT} seconds")
    print("-" * 50)
    
    # Test 1: Ping connectivity
    ping_success = ping_device(DEVICE_IP)
    print()
    
    # Test 2: TCP connection
    tcp_success = test_tcp_connection(DEVICE_IP, DEVICE_PORT)
    print()
    
    # Test 3: ZKTeco specific connection (if TCP works)
    zk_success = False
    if tcp_success:
        zk_success = test_zkteco_connection(DEVICE_IP, DEVICE_PORT)
        print()
    
    # Summary
    print("=" * 50)
    print("TEST SUMMARY:")
    print(f"Ping Test:      {'PASS' if ping_success else 'FAIL'}")
    print(f"TCP Test:       {'PASS' if tcp_success else 'FAIL'}")
    print(f"ZKTeco Test:    {'PASS' if zk_success else 'FAIL'}")
    print("=" * 50)
    
    if ping_success and tcp_success:
        print("✓ Device is reachable and responding!")
        if zk_success:
            print("✓ ZKTeco protocol communication successful!")
        else:
            print("⚠ Device responds but may not be ZKTeco or different protocol")
    else:
        print("✗ Device connection failed!")
        print("\nTroubleshooting tips:")
        print("1. Check if device IP is correct (currently set to 192.168.1.201)")
        print("2. Ensure device is powered on and connected to network")
        print("3. Check network connectivity and firewall settings")
        print("4. Verify the correct port (default 4370 for ZKTeco)")

if __name__ == "__main__":
    main()
