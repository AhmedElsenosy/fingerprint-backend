#!/usr/bin/env python3
"""
Test Scanner Script
==================

This script tests the scanner functionality by scanning any paper
and saving it to the upload folder for testing purposes.

Usage:
    python test_scanner.py

Requirements:
- Scanner connected and powered on
- python-sane installed: pip install python-sane
- SANE installed: sudo apt-get install sane-utils libsane1

Author: Ahmed
Date: 2025-08-10
"""

import os
import sys
from datetime import datetime
from scanner import ScannerConnection

def test_scanner():
    """Test scanner by scanning a document and saving to upload folder."""
    
    print("🔬 Scanner Test Script")
    print("=" * 40)
    
    # Create upload directory if it doesn't exist
    upload_dir = "upload/student_solutions"
    os.makedirs(upload_dir, exist_ok=True)
    print(f"📁 Upload directory: {upload_dir}")
    
    scanner = None
    
    try:
        # Step 1: Connect to scanner
        print("\n📡 Step 1: Connecting to scanner...")
        scanner = ScannerConnection()
        
        if not scanner.connect_scanner():
            print("❌ Failed to connect to scanner!")
            print("\n🔧 Troubleshooting:")
            print("1. Make sure scanner is connected via USB")
            print("2. Make sure scanner is powered on")
            print("3. Install SANE: sudo apt-get install sane-utils libsane1")
            print("4. Install python-sane: pip install python-sane")
            print("5. Check scanner detection: scanimage -L")
            return False
        
        # Step 2: Show scanner info
        print("\n📋 Step 2: Scanner Information:")
        scanner_info = scanner.get_scanner_info()
        for key, value in scanner_info.items():
            print(f"  {key}: {value}")
        
        # Step 3: Prepare for scanning
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        test_filename = f"test_scan_{timestamp}.png"
        output_path = os.path.join(upload_dir, test_filename)
        
        print(f"\n📄 Step 3: Ready to scan")
        print(f"📝 Output file: {output_path}")
        print("\n⚠️  PLACE ANY PAPER ON THE SCANNER NOW!")
        print("    (Can be blank paper, document, photo, anything...)")
        
        input("\n⏸️  Press ENTER when paper is ready on scanner...")
        
        # Step 4: Test different scan settings
        scan_tests = [
            {"resolution": 150, "mode": "Color", "name": "Quick Color Test"},
            {"resolution": 300, "mode": "Color", "name": "Standard Color Test"},
            {"resolution": 300, "mode": "Gray", "name": "Grayscale Test"},
        ]
        
        successful_scans = []
        
        for i, test in enumerate(scan_tests, 1):
            print(f"\n🔍 Step 4.{i}: {test['name']}")
            print(f"    Resolution: {test['resolution']} DPI")
            print(f"    Mode: {test['mode']}")
            
            # Create filename for this test
            test_file = f"test_scan_{test['mode'].lower()}_{test['resolution']}dpi_{timestamp}.png"
            test_path = os.path.join(upload_dir, test_file)
            
            success = scanner.scan_document(
                output_path=test_path,
                resolution=test['resolution'],
                mode=test['mode']
            )
            
            if success:
                if os.path.exists(test_path):
                    file_size = os.path.getsize(test_path)
                    print(f"    ✅ SUCCESS: Saved {test_file} ({file_size:,} bytes)")
                    successful_scans.append(test_path)
                else:
                    print(f"    ❌ FAILED: File was not created")
            else:
                print(f"    ❌ FAILED: Scan operation failed")
            
            # Small delay between scans
            import time
            time.sleep(1)
        
        # Step 5: Results Summary
        print(f"\n📊 Step 5: Test Results Summary")
        print(f"✅ Successful scans: {len(successful_scans)}/{len(scan_tests)}")
        
        if successful_scans:
            print(f"\n📂 Scanned files saved in: {upload_dir}")
            for scan_file in successful_scans:
                file_size = os.path.getsize(scan_file)
                filename = os.path.basename(scan_file)
                print(f"  📄 {filename} ({file_size:,} bytes)")
            
            print(f"\n🎉 Scanner test PASSED! Your scanner is working correctly.")
            print(f"💡 You can now use these test files to test your bubble sheet processing.")
            
            # Bonus: Try to display file info
            try:
                from PIL import Image
                print(f"\n🖼️  Image Analysis:")
                for scan_file in successful_scans[:2]:  # Analyze first 2 images
                    try:
                        with Image.open(scan_file) as img:
                            filename = os.path.basename(scan_file)
                            print(f"  📐 {filename}: {img.size[0]}x{img.size[1]} pixels, {img.mode} mode")
                    except Exception as e:
                        print(f"  ⚠️  Could not analyze {os.path.basename(scan_file)}: {e}")
            except ImportError:
                print(f"\n💡 Install PIL for image analysis: pip install Pillow")
            
            return True
        else:
            print(f"❌ Scanner test FAILED! No scans were successful.")
            return False
    
    except KeyboardInterrupt:
        print(f"\n⏹️  Test interrupted by user")
        return False
    
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return False
    
    finally:
        # Step 6: Cleanup
        if scanner:
            try:
                scanner.disconnect()
                print(f"\n🔌 Scanner disconnected")
            except:
                pass

def main():
    """Main function to run the scanner test."""
    
    print("🚀 Starting Scanner Test...")
    
    # Check if we're in the right directory
    if not os.path.exists("scanner.py"):
        print("❌ Error: scanner.py not found in current directory")
        print("💡 Make sure you're running this from /home/ahmed/Desktop/teacher/env/src/")
        return 1
    
    # Run the test
    success = test_scanner()
    
    if success:
        print(f"\n🎊 TEST COMPLETED SUCCESSFULLY!")
        print(f"🔧 Your scanner is ready to use with the exam system.")
        return 0
    else:
        print(f"\n💥 TEST FAILED!")
        print(f"🔧 Please check scanner connection and try again.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
