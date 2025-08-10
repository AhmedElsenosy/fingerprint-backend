#!/usr/bin/env python3
"""
Exam Data Checker
================

This script helps troubleshoot exam data issues,
specifically missing solution photos.

Usage:
    python check_exam_data.py EXAM_ID

Author: Ahmed
Date: 2025-08-10
"""

import sys
import requests
import json
from pprint import pprint

MAIN_BACKEND_URL = "http://localhost:8000"
FINGERPRINT_URL = "http://localhost:8001"

def check_exam_data(exam_id):
    """Check exam data from main backend."""
    
    print(f"🔍 Checking exam data for: {exam_id}")
    print("=" * 50)
    
    try:
        # Get exam data from main backend
        response = requests.get(f"{MAIN_BACKEND_URL}/internal/exams/{exam_id}", timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Failed to get exam data: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
        
        exam_data = response.json()
        
        # Check solution photo
        solution_photo = exam_data.get("solution_photo")
        print(f"📄 Solution Photo: {solution_photo}")
        
        if not solution_photo:
            print("❌ PROBLEM FOUND: No solution_photo in exam data")
            print("\n🔧 Solutions:")
            print("   1. Upload answer key via web interface")
            print("   2. Use exam creation API to add solution photo")
            print("   3. Check if exam was created properly")
        else:
            print("✅ Solution photo path exists")
            
            # Check if file actually exists
            import os
            possible_paths = [
                solution_photo,
                os.path.join("/home/ahmed/Desktop/teacher/venv/src", solution_photo),
                os.path.join("..", "..", "venv", "src", solution_photo),
            ]
            
            file_found = False
            for path in possible_paths:
                if os.path.exists(path):
                    file_size = os.path.getsize(path)
                    print(f"✅ File found at: {path} ({file_size:,} bytes)")
                    file_found = True
                    break
            
            if not file_found:
                print("❌ PROBLEM FOUND: Solution photo file not found on disk")
                print("📂 Checked paths:")
                for path in possible_paths:
                    print(f"   - {path} ❌")
        
        # Check models
        models = exam_data.get("models", [])
        print(f"\n📝 Models: {len(models)}")
        
        if models:
            for i, model in enumerate(models):
                model_solution = model.get("solution_photo")
                print(f"   Model {i+1}: {model.get('model_name')} - Solution: {bool(model_solution)}")
        
        # Check other important fields
        print(f"\n📊 Exam Details:")
        print(f"   Final Degree: {exam_data.get('final_degree')}")
        print(f"   Title: {exam_data.get('title')}")
        print(f"   Created: {exam_data.get('created_at', 'N/A')}")
        
        # Show full data (truncated)
        print(f"\n📋 Available Fields:")
        for key in exam_data.keys():
            value = exam_data[key]
            if isinstance(value, (str, int, float, bool)):
                print(f"   {key}: {value}")
            elif isinstance(value, list):
                print(f"   {key}: [{len(value)} items]")
            elif isinstance(value, dict):
                print(f"   {key}: {{dict with {len(value)} keys}}")
        
        return True
        
    except requests.RequestException as e:
        print(f"❌ Network error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def check_debug_endpoint(exam_id):
    """Check the debug endpoint."""
    
    print(f"\n🔧 Debug Endpoint Check:")
    print("-" * 30)
    
    try:
        response = requests.get(f"{FINGERPRINT_URL}/exams/{exam_id}/debug", timeout=30)
        
        if response.status_code == 200:
            debug_data = response.json()
            print("✅ Debug endpoint working")
            
            if "path_checks" in debug_data:
                print("\n📂 Path Check Results:")
                for path_info in debug_data["path_checks"]:
                    status = "✅" if path_info["exists"] else "❌"
                    print(f"   {status} {path_info['path']}")
            
        else:
            print(f"❌ Debug endpoint failed: {response.status_code}")
            print(f"   Response: {response.text}")
    
    except Exception as e:
        print(f"❌ Debug check error: {e}")

def main():
    """Main function."""
    
    if len(sys.argv) != 2:
        print("Usage: python check_exam_data.py EXAM_ID")
        print("Example: python check_exam_data.py 507f1f77bcf86cd799439011")
        sys.exit(1)
    
    exam_id = sys.argv[1]
    
    print("🔍 Exam Data Checker")
    print("=" * 30)
    
    # Check exam data
    success = check_exam_data(exam_id)
    
    if success:
        # Also check debug endpoint
        check_debug_endpoint(exam_id)
    
    print(f"\n💡 Next Steps:")
    print("   1. If no solution photo: Upload answer key via web interface")
    print("   2. If file not found: Check file paths and permissions")
    print("   3. Test with: python test_scanner.py")

if __name__ == "__main__":
    main()
