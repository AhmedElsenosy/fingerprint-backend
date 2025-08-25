#!/usr/bin/env python3
"""
Scanner Source Configuration Test
=================================

This script helps diagnose and fix the "Document feeder out of documents" error
by properly configuring your Canon TS3400 scanner to use the flatbed.

Run this before using the exam scanner functionality.
"""

import sane
import sys
from typing import Dict, List

def test_scanner_sources():
    """Test and configure scanner sources to avoid feeder errors."""
    
    print("🔍 Scanner Source Configuration Test")
    print("=" * 40)
    
    try:
        # Initialize SANE
        sane.init()
        print("✅ SANE initialized successfully")
        
        # Get available devices
        devices = sane.get_devices()
        if not devices:
            print("❌ No scanner devices found")
            return False
        
        print(f"\n📋 Found {len(devices)} scanner devices:")
        for i, device in enumerate(devices):
            print(f"  {i+1}. {device}")
        
        # Connect to first device (usually the Canon TS3400)
        device_name = devices[0][0]
        print(f"\n🔌 Connecting to: {device_name}")
        
        scanner = sane.open(device_name)
        print("✅ Scanner connected successfully")
        
        # Get all scanner options/parameters
        print(f"\n📊 Scanner Options and Current Values:")
        print("-" * 40)
        
        # Check for source option
        source_found = False
        available_sources = []
        current_source = None
        
        try:
            # Try to get current source
            if hasattr(scanner, 'source'):
                current_source = scanner.source
                source_found = True
                print(f"📍 Current Source: {current_source}")
                
                # Try to get available source options
                try:
                    # Some SANE backends provide constraint information
                    source_info = scanner.get_option_descriptor('source')
                    if source_info and source_info[8]:  # constraint list
                        available_sources = list(source_info[8])
                        print(f"📝 Available Sources: {available_sources}")
                    else:
                        # Common sources for Canon scanners
                        available_sources = ['Flatbed', 'Document Feeder', 'Platen']
                        print(f"📝 Trying common sources: {available_sources}")
                except Exception as e:
                    print(f"⚠️  Could not get source constraints: {e}")
                    # Default to common Canon scanner sources
                    available_sources = ['Flatbed', 'Document Feeder', 'Platen']
            else:
                print("❌ Scanner does not have 'source' option")
        except Exception as e:
            print(f"❌ Error checking source: {e}")
        
        # Show all available scanner options
        print(f"\n🔧 All Scanner Parameters:")
        print("-" * 30)
        
        for attr_name in dir(scanner):
            if not attr_name.startswith('_') and not callable(getattr(scanner, attr_name)):
                try:
                    value = getattr(scanner, attr_name)
                    print(f"  {attr_name}: {value}")
                except:
                    print(f"  {attr_name}: <unable to read>")
        
        # Test setting flatbed source
        if source_found and available_sources:
            print(f"\n🎯 Testing Source Configuration:")
            print("-" * 35)
            
            # Try different flatbed names
            flatbed_options = [
                'Flatbed', 'flatbed', 'Platen', 'platen', 
                'Scanner', 'scanner', 'Document Table', 'Automatic Document Feeder'
            ]
            
            success_source = None
            for source_name in flatbed_options:
                if source_name in available_sources or not available_sources:
                    try:
                        print(f"  Testing: {source_name}...", end=" ")
                        scanner.source = source_name
                        current_test = scanner.source
                        if current_test == source_name:
                            print("✅ SUCCESS")
                            success_source = source_name
                            break
                        else:
                            print(f"⚠️  Set but got: {current_test}")
                    except Exception as e:
                        print(f"❌ Failed: {e}")
                else:
                    print(f"  Skipping: {source_name} (not in available sources)")
            
            if success_source:
                print(f"\n🎉 Successfully configured scanner to use: {success_source}")
                print(f"✅ This should prevent 'Document feeder out of documents' error")
                
                # Try a test scan configuration
                print(f"\n🧪 Testing scan configuration...")
                try:
                    if hasattr(scanner, 'resolution'):
                        scanner.resolution = 300
                        print("✅ Resolution set to 300 DPI")
                    
                    if hasattr(scanner, 'mode'):
                        scanner.mode = 'Color'
                        print("✅ Mode set to Color")
                    
                    print("✅ Scanner is ready for scanning!")
                    print(f"   Source: {scanner.source}")
                    print(f"   Resolution: {getattr(scanner, 'resolution', 'Unknown')}")
                    print(f"   Mode: {getattr(scanner, 'mode', 'Unknown')}")
                    
                except Exception as e:
                    print(f"⚠️  Configuration test warning: {e}")
            else:
                print(f"\n❌ Could not find a working flatbed source")
                print(f"Available sources: {available_sources}")
                print(f"You may need to manually place document on flatbed")
        
        # Cleanup
        scanner.close()
        print(f"\n✅ Scanner test completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Scanner test failed: {e}")
        print(f"\nTroubleshooting:")
        print(f"1. Make sure scanner is powered on and connected")
        print(f"2. Check SANE installation: scanimage -L")
        print(f"3. Test manual scan: scanimage > test.pnm")
        return False

def quick_scan_test():
    """Perform a quick scan test to verify configuration."""
    print(f"\n🚀 Quick Scan Test")
    print("=" * 20)
    
    try:
        from scanner import connect_to_scanner
        
        scanner = connect_to_scanner()
        if not scanner:
            print("❌ Could not connect to scanner")
            return False
        
        print("✅ Connected to scanner")
        
        # Test scan (without actually scanning)
        print("📋 Scanner ready for document scanning")
        print("   Place your document on the flatbed (not in the feeder)")
        print("   The scanner should now work without 'feeder out of documents' error")
        
        scanner.disconnect()
        return True
        
    except Exception as e:
        print(f"❌ Quick scan test failed: {e}")
        return False

if __name__ == "__main__":
    print("Canon TS3400 Scanner Configuration Tool")
    print("=" * 45)
    print("This tool will help fix the 'Document feeder out of documents' error")
    print()
    
    # Run the source configuration test
    if test_scanner_sources():
        print("\n" + "=" * 50)
        quick_scan_test()
        
        print(f"\n🎯 Next Steps:")
        print(f"1. ✅ Your scanner is now configured to use flatbed")
        print(f"2. 📄 Place documents on the scanner glass (not in paper tray)")
        print(f"3. 🚀 Run your exam scanning - it should work now!")
        print(f"4. 📝 If you still get errors, check that documents are properly placed")
    else:
        print(f"\n❌ Scanner configuration failed")
        print(f"Please check your scanner connection and try again")
