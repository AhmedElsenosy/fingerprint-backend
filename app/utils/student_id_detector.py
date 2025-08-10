import cv2
import numpy as np
import json
import os
from typing import Optional, Dict, Any, List

def detect_student_id_template_based(image_path: str) -> Dict[str, Any]:
    """
    Detect student ID using template-based approach with known bubble coordinates.
    
    This function uses the precise bubble coordinates from id_coordinates.json
    to detect student ID more accurately.
    
    Args:
        image_path: Path to the bubble sheet image
        
    Returns:
        Dict containing detection results
    """
    try:
        # Load ID coordinates template
        template_path = os.path.join(os.path.dirname(__file__), "..", "..", "BubbleSheetCorrecterModule", "id_coordinates.json")
        
        if not os.path.exists(template_path):
            # Try alternative paths
            alt_paths = [
                "/home/ahmed/Desktop/teacher/env/src/BubbleSheetCorrecterModule/id_coordinates.json",
                "./BubbleSheetCorrecterModule/id_coordinates.json",
                "../BubbleSheetCorrecterModule/id_coordinates.json"
            ]
            
            template_path = None
            for alt_path in alt_paths:
                if os.path.exists(alt_path):
                    template_path = alt_path
                    break
        
        if not template_path or not os.path.exists(template_path):
            # Fallback to generic detection
            print("⚠️ Template file not found, using generic detection")
            return _detect_student_id_generic(image_path)
        
        with open(template_path, 'r') as f:
            template_data = json.load(f)
        
        id_bubbles = template_data.get("id_bubbles", [])
        template_size = template_data.get("image_size", {"width": 1012, "height": 1310})
        
        if not id_bubbles:
            print("⚠️ No bubble coordinates found in template, using generic detection")
            return _detect_student_id_generic(image_path)
        
        # Read the image
        image = cv2.imread(image_path)
        if image is None:
            return {
                "student_id": None,
                "confidence": 0.0,
                "message": "Could not read the image file",
                "debug_info": {"error": "Image loading failed"}
            }
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape
        
        print(f"📏 Image dimensions: {width} x {height}")
        print(f"📐 Template dimensions: {template_size['width']} x {template_size['height']}")
        
        # Calculate scaling factors
        scale_x = width / template_size["width"]
        scale_y = height / template_size["height"]
        
        print(f"🔍 Scaling factors: X={scale_x:.3f}, Y={scale_y:.3f}")
        
        # Apply threshold to enhance filled circles
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Group bubbles by column
        columns = {}
        for bubble in id_bubbles:
            col = bubble["column"]
            if col not in columns:
                columns[col] = []
            columns[col].append(bubble)
        
        detected_digits = []
        column_details = []
        
        print(f"\n🔢 Processing {len(columns)} columns:")
        
        # Process each column
        for col_idx in sorted(columns.keys()):
            column_bubbles = sorted(columns[col_idx], key=lambda x: x["number"])
            
            print(f"\n  📊 Column {col_idx} ({len(column_bubbles)} bubbles):")
            
            digit_scores = []
            
            for bubble in column_bubbles:
                # Convert relative coordinates to actual pixel coordinates
                x = int(bubble["relative_x"] * width)
                y = int(bubble["relative_y"] * height)
                
                # Define circle radius (adaptive based on image size)
                radius = max(8, int(min(width, height) * 0.01))  # 1% of smaller dimension
                
                # Create a mask for the bubble area
                mask = np.zeros(gray.shape, dtype=np.uint8)
                cv2.circle(mask, (x, y), radius, 255, -1)
                
                # Calculate the mean intensity inside the circle
                mean_intensity = cv2.mean(thresh, mask=mask)[0]
                fill_ratio = mean_intensity / 255.0
                
                digit_scores.append({
                    "digit": bubble["number"],
                    "fill_ratio": fill_ratio,
                    "mean_intensity": mean_intensity,
                    "position": (x, y, radius),
                    "relative_pos": (bubble["relative_x"], bubble["relative_y"])
                })
                
                print(f"    Digit {bubble['number']}: fill_ratio={fill_ratio:.3f}, intensity={mean_intensity:.1f}, pos=({x},{y})")
            
            # Find the most filled bubble in this column
            if digit_scores:
                best_digit = max(digit_scores, key=lambda x: x["fill_ratio"])
                
                print(f"    🎯 Best digit: {best_digit['digit']} with confidence {best_digit['fill_ratio']:.3f}")
                
                # Only accept if confidence is high enough
                if best_digit["fill_ratio"] > 0.2:  # Lower threshold for template-based detection
                    detected_digits.append(str(best_digit["digit"]))
                    column_details.append({
                        "column": col_idx,
                        "detected_digit": best_digit["digit"],
                        "confidence": best_digit["fill_ratio"],
                        "all_scores": digit_scores
                    })
                    print(f"    ✅ Accepted digit: {best_digit['digit']}")
                else:
                    detected_digits.append("?")
                    column_details.append({
                        "column": col_idx,
                        "detected_digit": None,
                        "confidence": best_digit["fill_ratio"],
                        "all_scores": digit_scores
                    })
                    print(f"    ❓ Unclear digit (low confidence: {best_digit['fill_ratio']:.3f})")
        
        print(f"\n🔍 Final detected digits: {detected_digits}")
        
        if not detected_digits:
            return {
                "student_id": None,
                "confidence": 0.0,
                "message": "No valid digits detected using template",
                "debug_info": {
                    "method": "template-based",
                    "columns_processed": len(columns),
                    "column_details": column_details
                }
            }
        
        # Calculate overall confidence
        valid_confidences = [col["confidence"] for col in column_details if col["detected_digit"] is not None]
        overall_confidence = sum(valid_confidences) / len(valid_confidences) if valid_confidences else 0.0
        
        # Create student ID string
        student_id = "".join(detected_digits)
        unclear_count = student_id.count("?")
        
        if unclear_count > 0:
            message = f"Template-based detection found {unclear_count} unclear digit(s): {student_id}"
            overall_confidence *= 0.7  # Reduce confidence for unclear digits
        else:
            message = f"Template-based detection successful: {student_id}"
        
        print(f"🆔 Template-based Student ID: {student_id}")
        
        return {
            "student_id": student_id if unclear_count == 0 else None,
            "confidence": overall_confidence,
            "message": message,
            "debug_info": {
                "method": "template-based",
                "columns_found": len(columns),
                "column_details": column_details,
                "scaling_factors": {"scale_x": scale_x, "scale_y": scale_y},
                "template_path": template_path
            }
        }
        
    except Exception as e:
        print(f"❌ Template-based detection failed: {str(e)}")
        # Return error instead of recursion to avoid infinite loop
        return {
            "student_id": None,
            "confidence": 0.0,
            "message": f"Template-based detection failed: {str(e)}",
            "debug_info": {"error": str(e), "method": "template-based"}
        }


def detect_student_id_adaptive(image_path: str) -> Dict[str, Any]:
    """
    Adaptive student ID detection that works with different bubble sheet formats.
    
    This function specifically handles the Arabic bubble sheets with student ID
    in the bottom-right area, using pattern recognition instead of exact coordinates.
    
    Args:
        image_path: Path to the bubble sheet image
        
    Returns:
        Dict containing detection results
    """
    try:
        # Read the image
        image = cv2.imread(image_path)
        if image is None:
            return {
                "student_id": None,
                "confidence": 0.0,
                "message": "Could not read the image file",
                "debug_info": {"error": "Image loading failed"}
            }
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape
        
        print(f"📏 Image dimensions: {width} x {height}")
        
        # Focus on bottom-right area where student ID typically appears
        id_x_start = int(width * 0.65)
        id_y_start = int(height * 0.72)
        id_x_end = int(width * 0.98)
        id_y_end = int(height * 0.98)
        
        id_roi = gray[id_y_start:id_y_end, id_x_start:id_x_end]
        roi_height, roi_width = id_roi.shape
        
        print(f"🔍 Student ID ROI: {roi_width} x {roi_height} at ({id_x_start},{id_y_start})")
        
        # Apply threshold to enhance filled circles
        _, thresh = cv2.threshold(id_roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Look for digit patterns by analyzing the structure
        # Most Arabic bubble sheets have 4-5 columns for student ID
        detected_digits = []
        confidence_scores = []
        
        # Try different column counts (4, 5, 6) to find the best fit
        for num_cols in [4, 5, 6]:
            col_width = roi_width // num_cols
            temp_digits = []
            temp_confidences = []
            
            print(f"\n🔢 Trying {num_cols} columns (width: {col_width}px each):")
            
            for col in range(num_cols):
                col_x1 = col * col_width
                col_x2 = min((col + 1) * col_width, roi_width)
                col_roi = thresh[:, col_x1:col_x2]
                
                # Divide column into 10 rows (digits 0-9)
                rows = 10
                row_height = roi_height // rows
                
                digit_scores = []
                for row in range(rows):
                    row_y1 = row * row_height
                    row_y2 = min((row + 1) * row_height, roi_height)
                    cell_roi = col_roi[row_y1:row_y2, :]
                    
                    # Calculate fill ratio for this cell
                    white_pixels = np.sum(cell_roi == 255)
                    total_pixels = cell_roi.size
                    fill_ratio = white_pixels / total_pixels if total_pixels > 0 else 0
                    
                    digit_scores.append({
                        "digit": row,
                        "fill_ratio": fill_ratio,
                        "white_pixels": white_pixels,
                        "total_pixels": total_pixels
                    })
                
                # Find the most filled cell (highest fill ratio)
                if digit_scores:
                    best_digit = max(digit_scores, key=lambda x: x["fill_ratio"])
                    
                    # Only accept if fill ratio is significant
                    if best_digit["fill_ratio"] > 0.15:  # Lower threshold for filled bubbles
                        temp_digits.append(str(best_digit["digit"]))
                        temp_confidences.append(best_digit["fill_ratio"])
                        print(f"  Column {col}: digit {best_digit['digit']} (confidence: {best_digit['fill_ratio']:.3f})")
                    else:
                        temp_digits.append("?")
                        temp_confidences.append(0.0)
                        print(f"  Column {col}: unclear (best confidence: {best_digit['fill_ratio']:.3f})")
                else:
                    temp_digits.append("?")
                    temp_confidences.append(0.0)
                    print(f"  Column {col}: no data")
            
            # Calculate overall confidence for this column count
            valid_confidences = [c for c in temp_confidences if c > 0]
            overall_confidence = sum(valid_confidences) / len(valid_confidences) if valid_confidences else 0.0
            
            print(f"  Overall confidence: {overall_confidence:.3f}")
            print(f"  Detected: {''.join(temp_digits)}")
            
            # Use the best result so far
            if overall_confidence > sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0:
                detected_digits = temp_digits
                confidence_scores = temp_confidences
        
        if not detected_digits:
            return {
                "student_id": None,
                "confidence": 0.0,
                "message": "No student ID digits detected in adaptive analysis",
                "debug_info": {
                    "method": "adaptive",
                    "roi_size": (roi_width, roi_height),
                    "roi_position": (id_x_start, id_y_start, id_x_end, id_y_end)
                }
            }
        
        # Calculate final results
        student_id = "".join(detected_digits)
        valid_confidences = [c for c in confidence_scores if c > 0]
        overall_confidence = sum(valid_confidences) / len(valid_confidences) if valid_confidences else 0.0
        
        # Check for unclear digits
        unclear_count = student_id.count("?")
        
        if unclear_count == 0 and len(student_id) >= 3:
            message = f"Adaptive detection successful: {student_id}"
            final_student_id = student_id
        elif unclear_count > 0:
            message = f"Adaptive detection with {unclear_count} unclear digit(s): {student_id}"
            final_student_id = None  # Don't return unclear results
        else:
            message = f"Adaptive detection failed: student ID too short or invalid"
            final_student_id = None
        
        print(f"🆔 Adaptive detection result: {student_id}")
        
        return {
            "student_id": final_student_id,
            "confidence": overall_confidence,
            "message": message,
            "debug_info": {
                "method": "adaptive",
                "raw_digits": detected_digits,
                "digit_confidences": confidence_scores,
                "unclear_count": unclear_count,
                "roi_size": (roi_width, roi_height),
                "roi_position": (id_x_start, id_y_start, id_x_end, id_y_end)
            }
        }
        
    except Exception as e:
        return {
            "student_id": None,
            "confidence": 0.0,
            "message": f"Error during adaptive student ID detection: {str(e)}",
            "debug_info": {"error": str(e), "method": "adaptive"}
        }


def detect_student_id(image_path: str) -> Dict[str, Any]:
    """
    Detect student ID from the bubble sheet image.
    
    This function tries multiple detection methods in order:
    1. Template-based detection (using exact coordinates)
    2. Adaptive detection (pattern-based for different formats)
    3. Generic detection (fallback HoughCircles)
    
    Args:
        image_path: Path to the bubble sheet image
        
    Returns:
        Dict containing:
        - student_id: The detected student ID string, or None if not detected
        - confidence: Confidence score (0.0 to 1.0)
        - message: Description of detection result
        - debug_info: Additional debugging information
    """
    try:
        print("\n🔍 Starting student ID detection...")
        
        # First try template-based detection
        print("📋 Attempting template-based detection...")
        template_result = detect_student_id_template_based(image_path)
        
        # If template detection succeeds, return it
        if (template_result.get("student_id") is not None and 
            template_result.get("confidence", 0) > 0.2):
            print(f"✅ Template-based detection successful: {template_result.get('student_id')}")
            return template_result
        
        print("⚠️ Template-based detection failed, trying adaptive detection...")
        
        # Try adaptive detection for different bubble sheet formats
        adaptive_result = detect_student_id_adaptive(image_path)
        
        # If adaptive detection succeeds, return it
        if (adaptive_result.get("student_id") is not None and 
            adaptive_result.get("confidence", 0) > 0.15):
            print(f"✅ Adaptive detection successful: {adaptive_result.get('student_id')}")
            return adaptive_result
        
        print("⚠️ Adaptive detection failed, trying generic detection...")
        
        # Fall back to generic detection
        return _detect_student_id_generic(image_path)
        
    except Exception as e:
        return {
            "student_id": None,
            "confidence": 0.0,
            "message": f"Error during student ID detection: {str(e)}",
            "debug_info": {"error": str(e)}
        }


def _detect_student_id_generic(image_path: str) -> Dict[str, Any]:
    """
    Generic student ID detection using HoughCircles.
    
    Args:
        image_path: Path to the bubble sheet image
        
    Returns:
        Dict containing detection results
    """
    try:
        # Read the image
        image = cv2.imread(image_path)
        if image is None:
            return {
                "student_id": None,
                "confidence": 0.0,
                "message": "Could not read the image file",
                "debug_info": {"error": "Image loading failed"}
            }
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Get image dimensions
        height, width = gray.shape
        
        print(f"📏 Image dimensions: {width} x {height}")
        
        # Try multiple specific regions for Arabic bubble sheets
        # These are common locations for student ID sections
        roi_candidates = [
            # Bottom right (most common)
            (int(width * 0.6), int(height * 0.75), width, height),
            # Bottom center-right
            (int(width * 0.45), int(height * 0.8), int(width * 0.9), height),
            # Center-right area
            (int(width * 0.5), int(height * 0.6), width, int(height * 0.95)),
            # Wider bottom area
            (int(width * 0.3), int(height * 0.85), width, height),
        ]
        
        best_result = None
        best_confidence = 0.0
        
        for roi_idx, (roi_left, roi_top, roi_right, roi_bottom) in enumerate(roi_candidates):
            print(f"\n🔍 Trying ROI {roi_idx + 1}: ({roi_left}, {roi_top}) to ({roi_right}, {roi_bottom})")
            print(f"📐 ROI size: {roi_right - roi_left} x {roi_bottom - roi_top}")
            
            # Extract ROI
            roi = gray[roi_top:roi_bottom, roi_left:roi_right]
            
            # Try to detect student ID in this region
            result = _detect_in_roi(roi, roi_left, roi_top, roi_right, roi_bottom)
            
            if result and result.get("confidence", 0) > best_confidence:
                best_confidence = result["confidence"]
                best_result = result
                best_result["roi_used"] = roi_idx + 1
                best_result["roi_coordinates"] = (roi_left, roi_top, roi_right, roi_bottom)
        
        return best_result or {
            "student_id": None,
            "confidence": 0.0,
            "message": "Could not detect student ID in any region",
            "debug_info": {"rois_tried": len(roi_candidates)}
        }
        
    except Exception as e:
        return {
            "student_id": None,
            "confidence": 0.0,
            "message": f"Error during student ID detection: {str(e)}",
            "debug_info": {"error": str(e)}
        }


def _detect_in_roi(roi, roi_left, roi_top, roi_right=None, roi_bottom=None):
    """
    Helper function to detect student ID within a specific ROI.
    
    Args:
        roi: Grayscale ROI image
        roi_left: Left offset of ROI in original image
        roi_top: Top offset of ROI in original image
        roi_right: Right boundary of ROI in original image (optional)
        roi_bottom: Bottom boundary of ROI in original image (optional)
    
    Returns:
        Detection result dict or None
    """
    try:
        
        # Apply threshold to make circles more visible
        _, thresh = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Try multiple circle detection approaches for better results
        circles = None
        detection_attempts = [
            # Standard parameters
            {"dp": 1, "minDist": 15, "param1": 50, "param2": 20, "minRadius": 5, "maxRadius": 25},
            # More sensitive detection
            {"dp": 1, "minDist": 10, "param1": 30, "param2": 15, "minRadius": 3, "maxRadius": 30},
            # Even more sensitive
            {"dp": 1, "minDist": 8, "param1": 20, "param2": 12, "minRadius": 2, "maxRadius": 35},
            # Ultra-aggressive detection
            {"dp": 1, "minDist": 5, "param1": 15, "param2": 8, "minRadius": 1, "maxRadius": 40},
            # Last resort - very lenient
            {"dp": 2, "minDist": 3, "param1": 10, "param2": 5, "minRadius": 1, "maxRadius": 50},
        ]
        
        circles_detected = []
        best_circles = None
        best_count = 0
        
        # Try all detection methods and use the one that finds most circles
        for attempt, params in enumerate(detection_attempts):
            test_circles = cv2.HoughCircles(
                thresh,
                cv2.HOUGH_GRADIENT,
                **params
            )
            
            if test_circles is not None:
                circle_count = len(test_circles[0])
                circles_detected.append((attempt + 1, circle_count))
                print(f"🔍 Attempt {attempt + 1}: Found {circle_count} circles")
                
                # Keep the result with most circles found
                if circle_count > best_count:
                    best_circles = test_circles
                    best_count = circle_count
            else:
                print(f"🔍 Attempt {attempt + 1}: No circles found")
        
        circles = best_circles
        print(f"🎯 Using detection result with {best_count} circles")
        
        if circles is None:
            return {
                "student_id": None,
                "confidence": 0.0,
                "message": "No student ID circles detected in the image",
                "debug_info": {
                    "roi_shape": roi.shape, 
                    "circles_found": 0,
                    "detection_attempts": len(detection_attempts),
                    "roi_coordinates": (roi_left, roi_top, roi_right, roi_bottom)
                }
            }
        
        circles = np.round(circles[0, :]).astype("int")
        print(f"🔍 Found {len(circles)} circles in student ID area")
        
        # Sort circles by x-coordinate to identify columns
        circles_sorted = sorted(circles, key=lambda c: c[0])
        
        # For Arabic bubble sheets, we expect exactly 5 columns of 10 circles each (digits 0-9)
        # Group circles into columns based on x-coordinate proximity
        digit_columns = []
        
        # Debug: print all circle positions
        print(f"📍 All circle positions (x, y, r):")
        for i, (x, y, r) in enumerate(circles_sorted):
            print(f"  Circle {i}: ({x}, {y}, {r})")
        
        # For Arabic student ID, detect columns dynamically (could be 4, 5, or more columns)
        # Use more intelligent column detection
        if len(circles_sorted) >= 4:  # Need at least 4 circles (minimum for student ID)
            # Calculate gaps between consecutive circles
            x_positions = [c[0] for c in circles_sorted]
            x_gaps = []
            
            for i in range(1, len(x_positions)):
                gap = x_positions[i] - x_positions[i-1]
                x_gaps.append((gap, i))  # Store gap and position
            
            # Find the largest gaps which likely represent column separations
            x_gaps_sorted = sorted(x_gaps, key=lambda x: x[0], reverse=True)
            print(f"📊 Top gaps between circles: {x_gaps_sorted[:10]}")
            
            # Use adaptive threshold based on gap distribution
            if x_gaps:
                # Try different percentiles to find column boundaries
                gaps_only = [gap[0] for gap in x_gaps]
                percentile_75 = sorted(gaps_only)[int(len(gaps_only) * 0.75)] if gaps_only else 30
                column_threshold = max(20, percentile_75)
            else:
                column_threshold = 30
            
            print(f"🔍 Using adaptive column threshold: {column_threshold}px")
            
            # Group circles into columns with more flexible logic
            current_column = []
            
            for i, (x, y, r) in enumerate(circles_sorted):
                if not current_column:
                    current_column = [(x, y, r)]
                else:
                    last_x = current_column[-1][0]
                    gap_to_last = abs(x - last_x)
                    
                    if gap_to_last <= column_threshold:
                        current_column.append((x, y, r))
                    else:
                        # End current column and start new one
                        if len(current_column) >= 1:  # Accept even single circles
                            digit_columns.append(current_column)
                        current_column = [(x, y, r)]
            
            # Don't forget the last column
            if len(current_column) >= 1:
                digit_columns.append(current_column)
            
            print(f"📊 Found {len(digit_columns)} columns with adaptive threshold")
            for col_idx, col in enumerate(digit_columns):
                col_x_positions = [c[0] for c in col]
                col_y_positions = [c[1] for c in col]
                print(f"  Column {col_idx}: {len(col)} circles, X range: {min(col_x_positions)}-{max(col_x_positions)}, Y range: {min(col_y_positions)}-{max(col_y_positions)}")
                for circle_idx, (x, y, r) in enumerate(col):
                    print(f"    Circle {circle_idx}: ({x}, {y}, {r})")
        
        # Fallback: try with fixed thresholds if dynamic approach fails
        if len(digit_columns) < 3:
            print(f"🔄 Dynamic grouping found {len(digit_columns)} columns, trying fixed thresholds...")
            
            for threshold in [30, 50, 80, 120]:
                digit_columns = []
                current_column = []
                
                for x, y, r in circles_sorted:
                    if not current_column:
                        current_column = [(x, y, r)]
                    else:
                        last_x = current_column[-1][0]
                        if abs(x - last_x) <= threshold:
                            current_column.append((x, y, r))
                        else:
                            if len(current_column) >= 2:  # Minimum circles per column
                                digit_columns.append(current_column)
                            current_column = [(x, y, r)]
                
                if len(current_column) >= 2:
                    digit_columns.append(current_column)
                
                print(f"🔍 Threshold {threshold}px found {len(digit_columns)} columns")
                
                # If we found a reasonable number of columns, use this
                if len(digit_columns) >= 3:
                    break
        
        if len(digit_columns) == 0:
            return {
                "student_id": None,
                "confidence": 0.0,
                "message": "Could not identify digit columns in student ID area",
                "debug_info": {
                    "circles_found": int(len(circles)), 
                    "columns_found": 0,
                    "circles_coordinates": [[int(x), int(y), int(r)] for x, y, r in circles.tolist()],
                    "roi_coordinates": (int(roi_left), int(roi_top), int(roi_right) if roi_right else None, int(roi_bottom) if roi_bottom else None),
                    "thresholds_tried": [30, 50, 80, 120]
                }
            }
        
        # Process each digit column to find filled circles
        detected_digits = []
        column_details = []
        
        print(f"\n🔢 Processing {len(digit_columns)} columns for digit detection:")
        
        for col_idx, column in enumerate(digit_columns):
            print(f"\n  📊 Column {col_idx} analysis:")
            
            # Sort circles in column by y-coordinate (top to bottom)
            column = sorted(column, key=lambda c: c[1])
            
            # Analyze each circle to find the filled one
            digit_scores = []
            for digit_idx, (x, y, r) in enumerate(column):
                # Create a mask for the circle
                mask = np.zeros(roi.shape, dtype=np.uint8)
                # Adjust coordinates relative to ROI
                cv2.circle(mask, (x, y), max(r - 3, 3), 255, -1)
                
                # Calculate the mean intensity inside the circle
                mean_intensity = cv2.mean(thresh, mask=mask)[0]
                
                # Calculate fill ratio (higher values indicate more filled)
                fill_ratio = mean_intensity / 255.0
                
                digit_scores.append({
                    "digit": int(digit_idx if digit_idx <= 9 else digit_idx % 10),
                    "fill_ratio": float(fill_ratio),
                    "mean_intensity": float(mean_intensity),
                    "position": (int(x), int(y), int(r))
                })
                
                print(f"    Position {digit_idx} (digit {digit_idx if digit_idx <= 9 else digit_idx % 10}): fill_ratio={fill_ratio:.3f}, intensity={mean_intensity:.1f}, pos=({x},{y})")
            
            # Find the most filled circle (highest fill ratio)
            if digit_scores:
                best_digit = max(digit_scores, key=lambda x: x["fill_ratio"])
                
                print(f"    🎯 Best digit: {best_digit['digit']} with confidence {best_digit['fill_ratio']:.3f}")
                
                # Only consider it a valid digit if confidence is high enough
                if best_digit["fill_ratio"] > 0.3:
                    detected_digits.append(str(best_digit["digit"]))
                    column_details.append({
                        "column": col_idx,
                        "detected_digit": best_digit["digit"],
                        "confidence": best_digit["fill_ratio"],
                        "all_scores": digit_scores
                    })
                    print(f"    ✅ Accepted digit: {best_digit['digit']}")
                else:
                    detected_digits.append("?")  # Unclear digit
                    column_details.append({
                        "column": col_idx,
                        "detected_digit": None,
                        "confidence": best_digit["fill_ratio"],
                        "all_scores": digit_scores
                    })
                    print(f"    ❓ Unclear digit (low confidence: {best_digit['fill_ratio']:.3f})")
            else:
                print(f"    ❌ No digit scores generated")
        
        print(f"\n🔍 Final detected digits: {detected_digits}")
        print(f"🆔 Student ID: {''.join(detected_digits)}")
        
        # Construct student ID from detected digits
        if not detected_digits:
            return {
                "student_id": None,
                "confidence": 0.0,
                "message": "No valid digits detected in student ID area",
                "debug_info": {
                    "columns_found": len(digit_columns),
                    "column_details": column_details
                }
            }
        
        # Calculate overall confidence based on individual digit confidences
        valid_confidences = [col["confidence"] for col in column_details if col["detected_digit"] is not None]
        overall_confidence = sum(valid_confidences) / len(valid_confidences) if valid_confidences else 0.0
        
        # Create student ID string
        student_id = "".join(detected_digits)
        
        # Check if we have any unclear digits
        unclear_count = student_id.count("?")
        if unclear_count > 0:
            message = f"Detected student ID with {unclear_count} unclear digit(s): {student_id}"
            overall_confidence *= 0.5  # Reduce confidence for unclear digits
        else:
            message = f"Successfully detected student ID: {student_id}"
        
        return {
            "student_id": student_id if unclear_count == 0 else None,
            "confidence": overall_confidence,
            "message": message,
            "debug_info": {
                "columns_found": len(digit_columns),
                "column_details": column_details,
                "roi_coordinates": (roi_left, roi_top, roi_right, roi_bottom),
                "total_circles": len(circles)
            }
        }
        
    except Exception as e:
        return {
            "student_id": None,
            "confidence": 0.0,
            "message": f"Error during student ID detection: {str(e)}",
            "debug_info": {"error": str(e)}
        }


def detect_student_id_from_image_array(image: np.ndarray) -> Dict[str, Any]:
    """
    Detect student ID from numpy image array (for already loaded images).
    
    Args:
        image: OpenCV image as numpy array
        
    Returns:
        Same format as detect_student_id()
    """
    try:
        if image is None:
            return {
                "student_id": None,
                "confidence": 0.0,
                "message": "Invalid image array provided",
                "debug_info": {"error": "Image array is None"}
            }
        
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Get image dimensions
        height, width = gray.shape
        
        # Define ROI for student ID area
        roi_top = int(height * 0.65)
        roi_bottom = int(height * 0.95)
        roi_left = int(width * 0.55)
        roi_right = int(width * 0.95)
        
        # Extract ROI
        roi = gray[roi_top:roi_bottom, roi_left:roi_right]
        
        # Apply threshold
        _, thresh = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Find circles with optimized parameters for student ID
        circles = cv2.HoughCircles(
            thresh,
            cv2.HOUGH_GRADIENT,
            dp=1,
            minDist=15,
            param1=50,
            param2=20,
            minRadius=5,
            maxRadius=25
        )
        
        if circles is None:
            return {
                "student_id": None,
                "confidence": 0.0,
                "message": "No student ID circles detected",
                "debug_info": {"roi_shape": roi.shape}
            }
        
        circles = np.round(circles[0, :]).astype("int")
        circles = sorted(circles, key=lambda c: c[0])
        
        # Group circles by columns and process digits
        digit_columns = []
        current_column = []
        column_threshold = 30
        
        for x, y, r in circles:
            if not current_column:
                current_column = [(x, y, r)]
            else:
                last_x = current_column[-1][0]
                if abs(x - last_x) <= column_threshold:
                    current_column.append((x, y, r))
                else:
                    if len(current_column) >= 3:
                        digit_columns.append(current_column)
                    current_column = [(x, y, r)]
        
        if len(current_column) >= 3:
            digit_columns.append(current_column)
        
        if not digit_columns:
            return {
                "student_id": None,
                "confidence": 0.0,
                "message": "Could not identify digit columns",
                "debug_info": {"circles_found": len(circles)}
            }
        
        # Process each column to detect digits
        detected_digits = []
        confidences = []
        
        for column in digit_columns:
            column = sorted(column, key=lambda c: c[1])
            
            digit_scores = []
            for digit_idx, (x, y, r) in enumerate(column):
                mask = np.zeros(roi.shape, dtype=np.uint8)
                cv2.circle(mask, (x, y), max(r - 3, 3), 255, -1)
                
                mean_intensity = cv2.mean(thresh, mask=mask)[0]
                fill_ratio = mean_intensity / 255.0
                
                digit_scores.append({
                    "digit": digit_idx if digit_idx <= 9 else digit_idx % 10,
                    "fill_ratio": fill_ratio
                })
            
            if digit_scores:
                best_digit = max(digit_scores, key=lambda x: x["fill_ratio"])
                if best_digit["fill_ratio"] > 0.3:
                    detected_digits.append(str(best_digit["digit"]))
                    confidences.append(best_digit["fill_ratio"])
                else:
                    detected_digits.append("?")
                    confidences.append(best_digit["fill_ratio"])
        
        if not detected_digits:
            return {
                "student_id": None,
                "confidence": 0.0,
                "message": "No valid digits detected",
                "debug_info": {"columns_found": len(digit_columns)}
            }
        
        overall_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        student_id = "".join(detected_digits)
        unclear_count = student_id.count("?")
        
        return {
            "student_id": student_id if unclear_count == 0 else None,
            "confidence": overall_confidence,
            "message": f"Detected student ID: {student_id}" if unclear_count == 0 else f"Student ID with unclear digits: {student_id}",
            "debug_info": {
                "columns_found": len(digit_columns),
                "total_circles": len(circles)
            }
        }
        
    except Exception as e:
        return {
            "student_id": None,
            "confidence": 0.0,
            "message": f"Error during student ID detection: {str(e)}",
            "debug_info": {"error": str(e)}
        }
