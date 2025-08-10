#!/usr/bin/env python3
"""
Bubble Sheet Printer Script
===========================

This script saves the bubble sheet template as an image file
and optionally sends it to a printer for testing purposes.

Usage:
    python print_bubble_sheet.py [--save-only] [--print]

Options:
    --save-only    Only save the image, don't print
    --print        Save and print the image
    (no args)      Interactive mode - asks what you want to do

Author: Ahmed
Date: 2025-08-10
"""

import os
import sys
import argparse
from datetime import datetime
import base64

def create_bubble_sheet_image():
    """Create and save the bubble sheet template image."""
    
    print("📄 Creating bubble sheet template...")
    
    # The bubble sheet image you provided (converted to base64 would go here)
    # Since I can't directly convert the image you showed, I'll create a script
    # that downloads/saves it from a URL or creates a template
    
    # For now, let's create a placeholder that explains how to use your image
    bubble_sheet_data = """
    BUBBLE SHEET TEMPLATE INSTRUCTIONS:
    ===================================
    
    Since I cannot directly access the image you provided, please follow these steps:
    
    1. Save your bubble sheet image as 'bubble_sheet_template.png' in this directory
    2. Run this script again to print it
    
    OR
    
    1. Place the image URL or file path below and uncomment the appropriate code
    
    The bubble sheet you showed contains:
    - ArUco markers in corners
    - Model selection (A, B, C bubbles at top)
    - Student ID section (numbered bubbles)
    - Answer bubbles (numbered 1-75 with A,B,C,D,E options)
    - Arabic text labels
    """
    
    template_info_file = "bubble_sheet_info.txt"
    with open(template_info_file, 'w', encoding='utf-8') as f:
        f.write(bubble_sheet_data)
    
    print(f"📝 Created info file: {template_info_file}")
    
    # Check if user has provided the image file
    template_files = [
        "bubble_sheet_template.png",
        "bubble_sheet_template.jpg", 
        "bubble_sheet.png",
        "bubble_sheet.jpg"
    ]
    
    found_template = None
    for template_file in template_files:
        if os.path.exists(template_file):
            found_template = template_file
            break
    
    return found_template

def save_bubble_sheet(template_file=None):
    """Save bubble sheet to upload directory."""
    
    if not template_file:
        print("❌ No bubble sheet template found!")
        print("💡 Please save your bubble sheet image as 'bubble_sheet_template.png'")
        return None
    
    # Create upload directory
    upload_dir = "upload/student_solutions"
    os.makedirs(upload_dir, exist_ok=True)
    
    # Create timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"bubble_sheet_template_{timestamp}.png"
    output_path = os.path.join(upload_dir, output_filename)
    
    # Copy the template file
    import shutil
    try:
        shutil.copy2(template_file, output_path)
        file_size = os.path.getsize(output_path)
        print(f"✅ Bubble sheet saved: {output_path} ({file_size:,} bytes)")
        return output_path
    except Exception as e:
        print(f"❌ Failed to save bubble sheet: {e}")
        return None

def download_image_from_url(url):
    """Download image from URL."""
    
    try:
        import urllib.request
        from urllib.parse import urlparse
        
        print(f"📥 Downloading image from: {url}")
        
        # Parse URL to get filename
        parsed = urlparse(url)
        filename = os.path.basename(parsed.path) or "downloaded_bubble_sheet.png"
        
        # Ensure it has an image extension
        if not filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
            filename += '.png'
        
        # Download the file
        urllib.request.urlretrieve(url, filename)
        
        if os.path.exists(filename):
            print(f"✅ Downloaded: {filename}")
            return filename
        else:
            print(f"❌ Download failed")
            return None
            
    except Exception as e:
        print(f"❌ Download error: {e}")
        return None

def print_bubble_sheet(image_path):
    """Send bubble sheet to printer."""
    
    if not image_path or not os.path.exists(image_path):
        print("❌ Cannot print: image file not found")
        return False
    
    print(f"🖨️  Printing bubble sheet...")
    
    try:
        # Try different printing methods
        
        # Method 1: Using lpr (Linux/Unix standard)
        import subprocess
        result = subprocess.run(['lpr', image_path], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Sent to printer using lpr")
            return True
        
        # Method 2: Using lp command
        result = subprocess.run(['lp', image_path], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Sent to printer using lp")
            return True
        
        # Method 3: Show available options
        print("🔧 Direct printing failed. Alternative options:")
        print(f"   1. Manual: Open {image_path} and print from image viewer")
        print(f"   2. Command: lpr {image_path}")
        print(f"   3. Command: lp {image_path}")
        
        return False
        
    except Exception as e:
        print(f"❌ Print error: {e}")
        print(f"💡 Manual printing: Open {image_path} in image viewer and print")
        return False

def main():
    """Main function."""
    
    parser = argparse.ArgumentParser(description='Save and print bubble sheet template')
    parser.add_argument('--save-only', action='store_true', help='Only save, do not print')
    parser.add_argument('--print', action='store_true', help='Save and print')
    parser.add_argument('--image', '-i', type=str, help='Path to bubble sheet image file')
    parser.add_argument('--url', '-u', type=str, help='URL to download bubble sheet image')
    parser.add_argument('image_path', nargs='?', help='Path to bubble sheet image (positional argument)')
    
    args = parser.parse_args()
    
    print("📄 Bubble Sheet Template Manager")
    print("=" * 40)
    
    # Step 1: Determine image source
    template_file = None
    
    # Priority order: command line args > positional arg > auto-detect
    if args.image:
        template_file = args.image
        print(f"📁 Using image from --image: {template_file}")
    elif args.image_path:
        template_file = args.image_path
        print(f"📁 Using image from argument: {template_file}")
    elif args.url:
        # Download from URL
        template_file = download_image_from_url(args.url)
        if template_file:
            print(f"📥 Downloaded image from URL: {template_file}")
    else:
        # Auto-detect existing template files
        template_file = create_bubble_sheet_image()
    
    # Validate the image file exists
    if not template_file or not os.path.exists(template_file):
        if args.image or args.image_path:
            print(f"❌ Image file not found: {template_file}")
            return 1
        
        print("\n⚠️  No bubble sheet template found!")
        print("📥 You can provide an image in several ways:")
        print("   • python print_bubble_sheet.py /path/to/image.png")
        print("   • python print_bubble_sheet.py --image /path/to/image.png")
        print("   • python print_bubble_sheet.py --url http://example.com/image.png")
        print("   • Save image as 'bubble_sheet_template.png' in current directory")
        print("\n💡 Example: python print_bubble_sheet.py ~/Downloads/bubble_sheet.png --print")
        return 1
    
    print(f"✅ Found template: {template_file}")
    
    # Step 2: Save the template
    saved_path = save_bubble_sheet(template_file)
    if not saved_path:
        return 1
    
    # Step 3: Determine action
    if args.save_only:
        action = 'save'
    elif args.print:
        action = 'print'
    else:
        # Interactive mode
        print(f"\n📋 What would you like to do?")
        print(f"1. Save only (for scanner testing)")
        print(f"2. Save and print (to create physical copy)")
        print(f"3. Exit")
        
        choice = input("\nEnter choice (1-3): ").strip()
        
        if choice == '1':
            action = 'save'
        elif choice == '2':
            action = 'print'
        else:
            print("👋 Exiting...")
            return 0
    
    # Step 4: Execute action
    if action == 'print':
        print(f"\n🖨️  Printing bubble sheet...")
        success = print_bubble_sheet(saved_path)
        if success:
            print(f"✅ Bubble sheet sent to printer!")
        else:
            print(f"⚠️  Auto-print failed, but file is saved for manual printing")
    
    # Step 5: Final instructions
    print(f"\n📂 File saved at: {saved_path}")
    print(f"🔬 Ready for scanner testing!")
    print(f"💡 You can now:")
    print(f"   • Print this file and use it with your scanner")
    print(f"   • Run: python test_scanner.py")
    print(f"   • Use the printed sheet for bubble sheet processing tests")
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
