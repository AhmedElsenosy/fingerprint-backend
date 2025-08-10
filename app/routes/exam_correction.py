from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from datetime import datetime
import httpx
import os
import shutil
from pathlib import Path
from typing import Dict

from app.utils.exam_corrector import correct_student_exam
from app.utils.model_detector import detect_exam_model
from app.utils.student_id_detector import detect_student_id
from app.utils.bubble_sheet_processor import process_bubble_sheet
from bson import ObjectId

router = APIRouter(prefix="/exams", tags=["Exam Correction"])

# Configuration for main backend communication
MAIN_BACKEND_URL = os.getenv("MAIN_BACKEND_URL", "http://localhost:8000")
STUDENT_SOLUTION_DIR = "upload/student_solutions"

# Ensure upload directory exists
os.makedirs(STUDENT_SOLUTION_DIR, exist_ok=True)

@router.get("/{exam_id}/debug")
async def debug_exam_solution_path(exam_id: str):
    """Debug endpoint to check exam solution path"""
    try:
        # Get exam details from main backend
        async with httpx.AsyncClient() as client:
            exam_response = await client.get(
                f"{MAIN_BACKEND_URL}/internal/exams/{exam_id}",
                timeout=30.0
            )
            
            if exam_response.status_code != 200:
                return {
                    "error": f"Failed to get exam details: {exam_response.text}",
                    "status_code": exam_response.status_code
                }
            
            exam_data = exam_response.json()
            exam_solution_path = exam_data.get("solution_photo")
            
            # Check different possible paths
            paths_to_check = []
            if exam_solution_path:
                paths_to_check = [
                    exam_solution_path,  # Original path
                    os.path.join("..", "..", "venv", "src", exam_solution_path),  # Relative to fingerprint backend
                    os.path.join("/home/ahmed/Desktop/teacher/venv/src", exam_solution_path),  # Absolute path
                    exam_solution_path.replace("upload/solutions", "/home/ahmed/Desktop/teacher/venv/src/upload/solutions")  # Fixed path
                ]
            
            path_results = []
            for path in paths_to_check:
                path_results.append({
                    "path": path,
                    "exists": os.path.exists(path),
                    "is_file": os.path.isfile(path) if os.path.exists(path) else False
                })
            
            return {
                "exam_id": exam_id,
                "exam_data": exam_data,
                "solution_photo_from_db": exam_solution_path,
                "current_working_dir": os.getcwd(),
                "path_checks": path_results
            }
            
    except Exception as e:
        return {
            "error": f"Debug failed: {str(e)}"
        }

@router.post("/debug/detect-model")
async def debug_model_detection(image_file: UploadFile = File(...)):
    """Debug endpoint to test model detection on uploaded image"""
    try:
        # Save uploaded image temporarily
        temp_filename = f"temp_debug_{image_file.filename}"
        temp_path = os.path.join(STUDENT_SOLUTION_DIR, temp_filename)
        
        with open(temp_path, "wb") as f:
            shutil.copyfileobj(image_file.file, f)
        
        # Detect model
        model_detection = detect_exam_model(temp_path)
        
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        return {
            "model_detection_result": model_detection,
            "detected_model": model_detection.get("model_number"),
            "confidence": model_detection.get("confidence"),
            "message": model_detection.get("message"),
            "debug_info": model_detection.get("debug_info")
        }
        
    except Exception as e:
        return {
            "error": f"Model detection debug failed: {str(e)}"
        }

@router.post("/debug/detect-student-id")
async def debug_student_id_detection(image_file: UploadFile = File(...)):
    """Debug endpoint to test student ID detection on uploaded image"""
    try:
        # Save uploaded image temporarily
        temp_filename = f"temp_debug_id_{image_file.filename}"
        temp_path = os.path.join(STUDENT_SOLUTION_DIR, temp_filename)
        
        with open(temp_path, "wb") as f:
            shutil.copyfileobj(image_file.file, f)
        
        # Detect student ID
        id_detection = detect_student_id(temp_path)
        
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        return {
            "student_id_detection_result": id_detection,
            "detected_student_id": id_detection.get("student_id"),
            "confidence": id_detection.get("confidence"),
            "message": id_detection.get("message"),
            "debug_info": id_detection.get("debug_info")
        }
        
    except Exception as e:
        return {
            "error": f"Student ID detection debug failed: {str(e)}"
        }

@router.post("/debug_student_id_detection")
async def debug_student_id_detection_alt(image: UploadFile = File(...)):
    """Alternative debug endpoint to test student ID detection (matches your URL)"""
    try:
        # Save uploaded image temporarily
        temp_filename = f"temp_debug_id_{image.filename}"
        temp_path = os.path.join(STUDENT_SOLUTION_DIR, temp_filename)
        
        with open(temp_path, "wb") as f:
            shutil.copyfileobj(image.file, f)
        
        # Detect student ID
        id_detection = detect_student_id(temp_path)
        
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        return {
            "student_id_detection_result": id_detection,
            "detected_student_id": id_detection.get("student_id"),
            "confidence": id_detection.get("confidence"),
            "message": id_detection.get("message"),
            "debug_info": id_detection.get("debug_info")
        }
        
    except Exception as e:
        return {
            "error": f"Student ID detection debug failed: {str(e)}"
        }

@router.post("/{exam_id}/submit")
async def submit_exam_solution(
    exam_id: str,
    solution_photo: UploadFile = File(...),
    manual_student_id: str = Form(None),  # Optional manual student ID fallback
    force_manual_id: str = Form(None)     # Accept as string and convert
):
    """
    Submit and automatically correct a student's exam solution.
    This endpoint handles the correction processing while communicating
    with the main backend for exam data and result storage.
    """
    try:
        # Step 1: Get exam details from main backend
        async with httpx.AsyncClient() as client:
            exam_response = await client.get(
                f"{MAIN_BACKEND_URL}/internal/exams/{exam_id}",
                timeout=30.0
            )
            
            if exam_response.status_code != 200:
                raise HTTPException(
                    status_code=exam_response.status_code,
                    detail=f"Failed to get exam details: {exam_response.text}"
                )
            
            exam_data = exam_response.json()

        # Step 2: Save uploaded student solution (temporary filename)
        temp_filename = f"temp_{exam_id}_{solution_photo.filename}"
        temp_solution_path = os.path.join(STUDENT_SOLUTION_DIR, temp_filename)
        
        with open(temp_solution_path, "wb") as f:
            shutil.copyfileobj(solution_photo.file, f)
        
        # Step 2b: Detect student ID from bubble sheet (with manual fallback)
        detected_student_id = None
        id_confidence = 0.0
        id_detection = {}
        
        # Convert force_manual_id to boolean (handles string inputs from form data)
        force_manual_bool = force_manual_id and str(force_manual_id).lower() in ['true', '1', 'yes', 'on']
        
        if force_manual_bool and manual_student_id:
            # Force manual ID - skip auto-detection entirely
            detected_student_id = manual_student_id.strip()
            id_confidence = 1.0
            id_detection = {
                "student_id": detected_student_id,
                "confidence": 1.0,
                "message": "Manual student ID used (auto-detection skipped)",
                "debug_info": {"method": "manual_override", "auto_detection_skipped": True}
            }
            print(f"🆔 Using forced manual student ID: {detected_student_id}")
        else:
            # Normal auto-detection using bubble_sheet_processor
            print(f"🔍 Using bubble_sheet_processor for student ID detection...")
            try:
                # Load image for bubble sheet processing
                import cv2
                image = cv2.imread(temp_solution_path)
                if image is None:
                    raise ValueError("Could not load image for processing")
                
                # Process bubble sheet to detect student ID
                bubble_result = process_bubble_sheet(
                    image, 
                    reference_data_file='BubbleSheetCorrecterModule/reference_data.json',
                    id_reference_file='BubbleSheetCorrecterModule/id_coordinates.json'
                )
                
                if bubble_result['success'] and bubble_result['results']:
                    grade_data = bubble_result['results']['grade_data']
                    
                    # Extract student ID from bubble sheet processor results
                    if 'id' in grade_data:
                        id_data = grade_data['id']
                        detected_student_id = id_data['value']
                        id_confidence = 1.0 if id_data['is_complete'] else 0.5
                        id_detection = {
                            "student_id": detected_student_id,
                            "confidence": id_confidence,
                            "message": "Detected using bubble_sheet_processor",
                            "debug_info": {
                                "method": "bubble_sheet_processor", 
                                "is_complete": id_data['is_complete'],
                                "raw_value": id_data['value']
                            }
                        }
                        print(f"🆔 Bubble processor detected ID: {detected_student_id} (complete: {id_data['is_complete']})")
                    else:
                        detected_student_id = None
                        id_confidence = 0.0
                        id_detection = {
                            "student_id": None,
                            "confidence": 0.0,
                            "message": "No ID section found in bubble sheet results",
                            "debug_info": {"method": "bubble_sheet_processor", "no_id_section": True}
                        }
                        print(f"❌ Bubble processor found no ID section")
                else:
                    detected_student_id = None
                    id_confidence = 0.0
                    id_detection = {
                        "student_id": None,
                        "confidence": 0.0,
                        "message": f"Bubble sheet processing failed: {bubble_result.get('message', 'Unknown error')}",
                        "debug_info": {"method": "bubble_sheet_processor", "processing_failed": True}
                    }
                    print(f"❌ Bubble sheet processing failed: {bubble_result.get('message')}")
                    
            except Exception as e:
                print(f"❌ Error in bubble_sheet_processor: {str(e)}")
                detected_student_id = None
                id_confidence = 0.0
                id_detection = {
                    "student_id": None,
                    "confidence": 0.0,
                    "message": f"Bubble processor error: {str(e)}",
                    "debug_info": {"method": "bubble_sheet_processor", "error": str(e)}
                }
            
            # Use manual student ID if auto-detection fails and manual ID is provided
            if not detected_student_id and manual_student_id:
                detected_student_id = manual_student_id.strip()
                id_confidence = 1.0  # High confidence for manual input
                id_detection["message"] = f"Auto-detection failed, using manual student ID. Original: {id_detection.get('message', 'N/A')}"
                print(f"🆔 Auto-detection failed, using manual student ID: {detected_student_id}")
        
        if not detected_student_id:
            # Clean up temp file and return detailed error with debug info
            if os.path.exists(temp_solution_path):
                os.remove(temp_solution_path)
            
            error_detail = f"Could not detect student ID from bubble sheet. {id_detection.get('message', 'Unknown error')}"
            if id_detection.get('debug_info'):
                debug_info = id_detection['debug_info']
                error_detail += f" Debug: Found {debug_info.get('circles_found', 0)} circles, {debug_info.get('columns_found', 0)} columns."
                
            error_detail += " You can retry with manual_student_id parameter in the form data."
            
            raise HTTPException(
                status_code=400,
                detail=error_detail
            )
        
        # Validate student ID format
        if not detected_student_id or len(detected_student_id.strip()) == 0:
            if os.path.exists(temp_solution_path):
                os.remove(temp_solution_path)
            raise HTTPException(
                status_code=400,
                detail="Invalid student ID detected: empty or null value"
            )
        
        # Clean and validate student ID
        detected_student_id = detected_student_id.strip()
        
        # Ensure student ID has reasonable length (at least 1 character, max 20)
        if len(detected_student_id) == 0 or len(detected_student_id) > 20:
            if os.path.exists(temp_solution_path):
                os.remove(temp_solution_path)
            raise HTTPException(
                status_code=400,
                detail=f"Invalid student ID format: '{detected_student_id}' (length: {len(detected_student_id)}). Must be 1-20 characters."
            )
        
        # Check for obviously invalid IDs like single digits, only zeros, or clearly wrong patterns
        if (detected_student_id == "0" or 
            (len(detected_student_id) == 1 and detected_student_id.isdigit()) or
            (len(detected_student_id) == 2 and detected_student_id in ["00", "11", "22", "33", "44", "55", "66", "77", "88", "99"]) or
            len(detected_student_id) < 3):  # Accept 3+ digit student IDs
            
            if os.path.exists(temp_solution_path):
                os.remove(temp_solution_path)
            raise HTTPException(
                status_code=400,
                detail=f"Invalid student ID detected: '{detected_student_id}' appears to be incorrect. Please use manual_student_id parameter or check bubble sheet image quality."
            )
        
        print(f"🆔 Detected Student ID: {detected_student_id} (confidence: {id_confidence:.2f})")
        
        # Step 2c: Convert numeric student ID to MongoDB ObjectId
        # The backend expects an ObjectId, but we detected a numeric student_id
        # We need to look up the student by their student_id field to get their _id (ObjectId)
        print(f"🔍 Looking up student with student_id: {detected_student_id}")
        try:
            # Convert detected_student_id to integer for database lookup
            student_numeric_id = int(detected_student_id)
            
            # Query the main backend to find student by their numeric student_id
            async with httpx.AsyncClient() as client:
                student_lookup_response = await client.get(
                    f"{MAIN_BACKEND_URL}/internal/students/by-student-id/{student_numeric_id}",
                    timeout=30.0
                )
                
                if student_lookup_response.status_code == 200:
                    student_info = student_lookup_response.json()
                    student_object_id = student_info.get("_id")  # This is the MongoDB ObjectId we need
                    print(f"✅ Found student: {student_info.get('first_name')} {student_info.get('last_name')} (ObjectId: {student_object_id})")
                    
                    # Use the ObjectId for backend communication, but keep numeric ID for file naming
                    backend_student_id = student_object_id
                elif student_lookup_response.status_code == 404:
                    # Student not found in database
                    if os.path.exists(temp_solution_path):
                        os.remove(temp_solution_path)
                    raise HTTPException(
                        status_code=404,
                        detail=f"Student with ID {detected_student_id} not found in database. Please verify the student ID is correct and the student is registered."
                    )
                else:
                    # Other error from backend
                    if os.path.exists(temp_solution_path):
                        os.remove(temp_solution_path)
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to lookup student: {student_lookup_response.text}"
                    )
        except ValueError:
            # detected_student_id is not a valid integer
            if os.path.exists(temp_solution_path):
                os.remove(temp_solution_path)
            raise HTTPException(
                status_code=400,
                detail=f"Invalid student ID format: '{detected_student_id}' must be a numeric value"
            )
        except httpx.RequestError as e:
            # Network error communicating with backend
            if os.path.exists(temp_solution_path):
                os.remove(temp_solution_path)
            raise HTTPException(
                status_code=503,
                detail=f"Failed to communicate with main backend for student lookup: {str(e)}"
            )
        
        # Step 2d: Rename file with detected student ID
        final_filename = f"{detected_student_id}_{exam_id}_{solution_photo.filename}"
        student_solution_path = os.path.join(STUDENT_SOLUTION_DIR, final_filename)
        
        # Move temp file to final location
        os.rename(temp_solution_path, student_solution_path)

        # Step 3: Detect exam model from student's bubble sheet using bubble_sheet_processor
        # We already processed the bubble sheet for student ID, so let's reuse or reprocess it for model detection
        print(f"🔍 Using bubble_sheet_processor for exam model detection...")
        detected_model = None
        model_confidence = 0.0
        model_detection = {}
        
        try:
            # Load image again for model detection (or reuse previous processing)
            import cv2
            image = cv2.imread(student_solution_path)
            if image is None:
                raise ValueError("Could not load image for model detection")
            
            # Process bubble sheet to detect exam model
            bubble_result = process_bubble_sheet(
                image, 
                reference_data_file='BubbleSheetCorrecterModule/reference_data.json',
                id_reference_file='BubbleSheetCorrecterModule/id_coordinates.json',
                exam_models_file='BubbleSheetCorrecterModule/exam_models.json',
                exam_model_key='exam_model_aruco'  # Use ArUco-based model detection
            )
            
            if bubble_result['success'] and bubble_result['results']:
                grade_data = bubble_result['results']['grade_data']
                
                # Extract exam model from bubble sheet processor results
                if 'exam_model' in grade_data:
                    model_data = grade_data['exam_model']
                    detected_model = model_data['value']
                    model_confidence = 1.0 if model_data['is_valid'] else 0.5
                    model_detection = {
                        "model_number": detected_model,
                        "confidence": model_confidence,
                        "message": "Detected using bubble_sheet_processor",
                        "debug_info": {
                            "method": "bubble_sheet_processor", 
                            "is_valid": model_data['is_valid'],
                            "raw_value": model_data['value'],
                            "fill_percentages": model_data['fill_percentages']
                        }
                    }
                    print(f"📝 Bubble processor detected model: {detected_model} (valid: {model_data['is_valid']})")
                else:
                    detected_model = None
                    model_confidence = 0.0
                    model_detection = {
                        "model_number": None,
                        "confidence": 0.0,
                        "message": "No exam model section found in bubble sheet results",
                        "debug_info": {"method": "bubble_sheet_processor", "no_model_section": True}
                    }
                    print(f"❌ Bubble processor found no exam model section")
            else:
                detected_model = None
                model_confidence = 0.0
                model_detection = {
                    "model_number": None,
                    "confidence": 0.0,
                    "message": f"Bubble sheet processing failed for model detection: {bubble_result.get('message', 'Unknown error')}",
                    "debug_info": {"method": "bubble_sheet_processor", "processing_failed": True}
                }
                print(f"❌ Bubble sheet processing failed for model detection: {bubble_result.get('message')}")
                
        except Exception as e:
            print(f"❌ Error in bubble_sheet_processor for model detection: {str(e)}")
            detected_model = None
            model_confidence = 0.0
            model_detection = {
                "model_number": None,
                "confidence": 0.0,
                "message": f"Bubble processor error for model detection: {str(e)}",
                "debug_info": {"method": "bubble_sheet_processor", "error": str(e)}
            }
        
        # If model detection fails, check if we can use legacy solution as fallback
        if not detected_model:
            legacy_solution = exam_data.get("solution_photo")
            print(f"🔍 Model detection failed. Legacy solution: {legacy_solution}")
            print(f"🔍 Exam data keys: {list(exam_data.keys())}")
            print(f"🔍 Detection message: {model_detection.get('message')}")
            
            if legacy_solution:
                # Use legacy solution as fallback
                detected_model = "legacy"
                model_confidence = 0.5  # Set moderate confidence for fallback
                print(f"✅ Using legacy solution: {legacy_solution}")
            else:
                # Let's try one more thing - check if there are any models with solutions
                exam_models = exam_data.get("models", [])
                fallback_model = None
                for model in exam_models:
                    if model.get("solution_photo"):
                        fallback_model = model
                        break
                
                if fallback_model:
                    detected_model = fallback_model.get("model_number", 1)
                    model_confidence = 0.3  # Lower confidence for forced fallback
                    print(f"✅ Using first available model as fallback: Model {detected_model}")
                else:
                    print(f"❌ No solutions available - Legacy: {legacy_solution}, Models: {exam_models}")
                    raise HTTPException(
                        status_code=400,
                        detail=f"Could not detect exam model from student's bubble sheet and no solution available. Detection: {model_detection.get('message', 'Unknown error')}. Available: legacy={bool(legacy_solution)}, models={len(exam_models)}"
                    )
        
        # Step 4: Get exam models and find the correct solution
        exam_models = exam_data.get("models", [])
        legacy_solution = exam_data.get("solution_photo")
        selected_model = None
        
        # Debug: Print available models
        print(f"🔍 Available exam models: {len(exam_models)}")
        for i, model in enumerate(exam_models):
            print(f"  Model {i+1}: {model.get('model_number')} - {model.get('model_name')} (solution: {bool(model.get('solution_photo'))})")
        print(f"🔍 Legacy solution available: {bool(legacy_solution)}")
        print(f"🔍 Detected model from bubble sheet: '{detected_model}'")
        
        if detected_model == "legacy" or not exam_models:
            # Use legacy single solution
            if not legacy_solution:
                raise HTTPException(
                    status_code=400,
                    detail="Exam has no solution photos uploaded (neither legacy nor multi-model). Cannot perform correction."
                )
            exam_solution_path = legacy_solution
            selected_model = {"model_name": "Legacy Model", "model_number": "legacy"}
            print(f"✅ Using legacy solution")
        else:
            # Find the correct model solution (try different matching strategies)
            # Strategy 1: Exact match
            for model in exam_models:
                if str(model.get("model_number")).upper() == str(detected_model).upper():
                    selected_model = model
                    print(f"✅ Found exact model match: {model.get('model_number')}")
                    break
            
            # Strategy 2: Try converting letters to numbers (A=1, B=2, C=3, etc.)
            if not selected_model and detected_model.isalpha() and len(detected_model) == 1:
                model_number_from_letter = ord(detected_model.upper()) - ord('A') + 1
                print(f"🔄 Trying to match letter '{detected_model}' as number {model_number_from_letter}")
                for model in exam_models:
                    if model.get("model_number") == model_number_from_letter or str(model.get("model_number")) == str(model_number_from_letter):
                        selected_model = model
                        print(f"✅ Found model by letter-to-number conversion: {model.get('model_number')}")
                        break
            
            # Strategy 3: Try converting numbers to letters (1=A, 2=B, 3=C, etc.)
            if not selected_model and detected_model.isdigit():
                model_letter_from_number = chr(int(detected_model) - 1 + ord('A'))
                print(f"🔄 Trying to match number '{detected_model}' as letter {model_letter_from_number}")
                for model in exam_models:
                    if str(model.get("model_number")).upper() == model_letter_from_number:
                        selected_model = model
                        print(f"✅ Found model by number-to-letter conversion: {model.get('model_number')}")
                        break
            
            # Strategy 4: If no exact match, try first available model with solution
            if not selected_model:
                for model in exam_models:
                    if model.get("solution_photo"):
                        selected_model = model
                        print(f"⚠️ No exact match for '{detected_model}', using first available model: {model.get('model_number')}")
                        break
            
            # If still no model found, try legacy fallback
            if not selected_model:
                if legacy_solution:
                    exam_solution_path = legacy_solution
                    selected_model = {"model_name": "Legacy Fallback", "model_number": "legacy"}
                    print(f"⚠️ Model {detected_model} not configured, using legacy fallback")
                else:
                    # Final error - provide detailed information
                    available_models = [f"{m.get('model_number')}({m.get('model_name')})" for m in exam_models]
                    raise HTTPException(
                        status_code=400,
                        detail=f"Detected model '{detected_model}' but exam doesn't have this model configured. Available models: {available_models}. Legacy solution: {'available' if legacy_solution else 'not available'}. Please check exam configuration or bubble sheet detection."
                    )
            else:
                exam_solution_path = selected_model.get("solution_photo")
                if not exam_solution_path:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Model {selected_model.get('model_number')} ({selected_model.get('model_name')}) has no solution photo uploaded"
                    )
        
        # Step 5: Resolve exam solution path
        possible_paths = [
            exam_solution_path,  # Original path (relative to main backend)
            os.path.join("/home/ahmed/Desktop/teacher/venv/src", exam_solution_path),  # Absolute path
            os.path.join("..", "..", "venv", "src", exam_solution_path),  # Relative from fingerprint to main backend
        ]
        
        resolved_exam_path = None
        for path in possible_paths:
            if os.path.exists(path) and os.path.isfile(path):
                resolved_exam_path = path
                break
        
        if not resolved_exam_path:
            raise HTTPException(
                status_code=400,
                detail=f"Exam answer key file not found at any of these paths: {possible_paths}. Cannot perform automatic correction."
            )

        # Step 6: Perform automatic exam correction
        correction_result = correct_student_exam(
            student_solution_path=student_solution_path,
            exam_solution_path=resolved_exam_path,
            final_degree=exam_data["final_degree"]
        )
        
        # Add model detection info to correction result
        if correction_result.get("success"):
            correction_result["detected_model"] = detected_model
            correction_result["model_confidence"] = model_confidence
            correction_result["model_name"] = selected_model.get("model_name") if selected_model else "Legacy Model"
            # Override total_questions with final_degree from exam collection
            correction_result["total_questions"] = exam_data["final_degree"]

        # Step 7: Prepare results for main backend
        if correction_result["success"]:
            student_degree = correction_result["student_score"]
            degree_percentage = correction_result["percentage"]
            correction_message = f"Automatic correction completed. Score: {student_degree}/{exam_data['final_degree']} ({degree_percentage}%)"
        else:
            student_degree = None
            degree_percentage = None
            correction_message = f"Automatic correction failed: {correction_result['message']}. Manual correction required."

        # Step 8: Send results back to main backend  
        result_data = {
            "student_id": backend_student_id,  # Use the ObjectId from database lookup
            "degree": student_degree,
            "percentage": degree_percentage,
            "delivery_time": datetime.utcnow().isoformat(),
            "solution_photo": student_solution_path,
            "correction_details": correction_result if correction_result["success"] else None
        }

        async with httpx.AsyncClient() as client:
            result_response = await client.post(
                f"{MAIN_BACKEND_URL}/internal/exams/{exam_id}/results",
                json=result_data,
                timeout=30.0
            )
            
            if result_response.status_code != 200:
                raise HTTPException(
                    status_code=result_response.status_code,
                    detail=f"Failed to save results: {result_response.text}"
                )

        # Step 9: Return response
        return {
            "message": correction_message,
            "solution_path": student_solution_path,
            "degree": student_degree,
            "percentage": degree_percentage,
            "correction_details": correction_result if correction_result["success"] else None
        }

    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to communicate with main backend: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error during exam correction: {str(e)}"
        )


@router.post("/{exam_id}/students/{student_id}/correct")
async def manually_correct_exam(
    exam_id: str,
    student_id: str
):
    """
    Manually trigger exam correction for a student who has already submitted.
    This is useful when automatic correction failed or needs to be re-run.
    """
    try:
        # Step 1: Get exam details from main backend
        async with httpx.AsyncClient() as client:
            exam_response = await client.get(
                f"{MAIN_BACKEND_URL}/internal/exams/{exam_id}",
                timeout=30.0
            )
            
            if exam_response.status_code != 200:
                raise HTTPException(
                    status_code=exam_response.status_code,
                    detail=f"Failed to get exam details: {exam_response.text}"
                )
            
            exam_data = exam_response.json()

        # Step 2: Get student submission details from main backend
        async with httpx.AsyncClient() as client:
            student_response = await client.get(
                f"{MAIN_BACKEND_URL}/internal/exams/{exam_id}/students/{student_id}",
                timeout=30.0
            )
            
            if student_response.status_code != 200:
                raise HTTPException(
                    status_code=student_response.status_code,
                    detail=f"Student submission not found: {student_response.text}"
                )
            
            student_data = student_response.json()

        # Step 3: Check if student solution file exists
        student_solution_path = student_data.get("solution_photo")
        if not student_solution_path or not os.path.exists(student_solution_path):
            raise HTTPException(
                status_code=400,
                detail="Student solution file not found"
            )

        # Step 4: Check if exam solution exists
        exam_solution_path = exam_data.get("solution_photo")
        if not exam_solution_path or not os.path.exists(exam_solution_path):
            raise HTTPException(
                status_code=400,
                detail="Exam answer key not found. Cannot perform correction."
            )

        # Step 5: Perform exam correction
        correction_result = correct_student_exam(
            student_solution_path=student_solution_path,
            exam_solution_path=exam_solution_path,
            final_degree=exam_data["final_degree"]
        )

        # Step 6: Send updated results to main backend
        if correction_result["success"]:
            result_data = {
                "student_id": student_id,
                "degree": correction_result["student_score"],
                "percentage": correction_result["percentage"],
                "correction_details": correction_result
            }

            async with httpx.AsyncClient() as client:
                update_response = await client.put(
                    f"{MAIN_BACKEND_URL}/internal/exams/{exam_id}/students/{student_id}/results",
                    json=result_data,
                    timeout=30.0
                )
                
                if update_response.status_code != 200:
                    raise HTTPException(
                        status_code=update_response.status_code,
                        detail=f"Failed to update results: {update_response.text}"
                    )

            return {
                "success": True,
                "message": f"Manual correction completed successfully. Score: {correction_result['student_score']}/{exam_data['final_degree']} ({correction_result['percentage']}%)",
                "degree": correction_result["student_score"],
                "percentage": correction_result["percentage"],
                "correction_details": correction_result
            }
        else:
            return {
                "success": False,
                "message": f"Manual correction failed: {correction_result['message']}",
                "correction_details": correction_result
            }

    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to communicate with main backend: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error during manual correction: {str(e)}"
        )
