#!/usr/bin/env python3

import cv2
import numpy as np
import json
import os
from BubbleSheetCorrecterModule.bubble_edge_detector import detect_aruco_markers

def calculate_exam_model_relative_to_aruco():
    """
    Calculate exam model bubble positions relative to ArUco markers.
    This creates a reference that can be used for any image with ArUco markers.
    """
    
    # Reference ArUco marker positions (from debug output)
    reference_aruco = {
        0: [187.5, 364.0],    # Top-left
        1: [2192.5, 364.0],  # Top-right  
        2: [187.5, 3003.5],  # Bottom-left
        3: [2192.5, 3003.5]  # Bottom-right
    }
    
    # Exam model bubble positions (coordinates you provided)
    exam_model_positions = {
        'A': [1301, 397],
        'B': [1191, 397], 
        'C': [1085, 397]
    }
    
    print("Calculating exam model positions relative to ArUco markers...")
    print("=" * 60)
    
    # Use top ArUco markers (0 and 1) as reference line
    top_left = np.array(reference_aruco[0])   # [187.5, 364.0]
    top_right = np.array(reference_aruco[1])  # [2192.5, 364.0]
    
    # Calculate the horizontal distance between top markers
    aruco_width = top_right[0] - top_left[0]  # 2192.5 - 187.5 = 2005.0
    aruco_height = top_left[1]  # Y position of top markers = 364.0
    
    print(f"ArUco reference frame:")
    print(f"  Top-left marker (ID 0): {top_left}")
    print(f"  Top-right marker (ID 1): {top_right}")
    print(f"  Width between markers: {aruco_width}")
    print(f"  Top marker Y position: {aruco_height}")
    
    # Calculate relative positions for each exam model bubble
    exam_model_relative = {}
    
    for letter, position in exam_model_positions.items():
        x, y = position
        
        # Calculate relative position from left ArUco marker
        rel_x_from_left = (x - top_left[0]) / aruco_width
        rel_y_from_top = y - aruco_height
        
        # Calculate distance ratios
        exam_model_relative[letter] = {
            'rel_x_ratio': rel_x_from_left,  # As ratio of ArUco width
            'y_offset_from_aruco': rel_y_from_top,  # Pixel offset from ArUco Y
            'absolute_position': position
        }
        
        print(f"\nBubble {letter}:")
        print(f"  Absolute position: {position}")
        print(f"  X ratio from left ArUco: {rel_x_from_left:.4f}")
        print(f"  Y offset from ArUco line: {rel_y_from_top:.1f} pixels")
    
    return exam_model_relative, reference_aruco

def calculate_exam_model_positions_from_aruco(current_aruco_markers):
    """
    Calculate exam model positions in a new image based on its ArUco markers.
    """
    
    # Get the relative positions we calculated
    exam_model_relative, _ = calculate_exam_model_relative_to_aruco()
    
    # Create marker dictionary from current image
    marker_dict = {marker['id']: marker['center'] for marker in current_aruco_markers}
    
    if 0 not in marker_dict or 1 not in marker_dict:
        raise ValueError("Missing required ArUco markers (0 and 1) for exam model positioning")
    
    # Get current top markers
    current_top_left = np.array(marker_dict[0])
    current_top_right = np.array(marker_dict[1])
    current_aruco_width = current_top_right[0] - current_top_left[0]
    current_aruco_y = current_top_left[1]
    
    print(f"\nCalculating exam model positions for current image:")
    print(f"  Current top-left ArUco: {current_top_left}")
    print(f"  Current top-right ArUco: {current_top_right}")
    print(f"  Current ArUco width: {current_aruco_width}")
    print(f"  Current ArUco Y: {current_aruco_y}")
    
    # Calculate exam model positions
    exam_model_positions = []
    
    for letter in ['A', 'B', 'C']:
        rel_data = exam_model_relative[letter]
        
        # Calculate position based on current ArUco markers
        x = current_top_left[0] + (rel_data['rel_x_ratio'] * current_aruco_width)
        y = current_aruco_y + rel_data['y_offset_from_aruco']
        
        exam_model_positions.append({
            'model_letter': letter,
            'center': [int(x), int(y)],
            'relative_data': rel_data
        })
        
        print(f"  Model {letter}: ({int(x)}, {int(y)})")
    
    return exam_model_positions

def save_aruco_based_exam_model(image_path):
    """
    Save exam model coordinates calculated from ArUco markers for any image.
    """
    
    # Load the image
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Could not load image: {image_path}")
    
    # Detect ArUco markers
    aruco_markers = detect_aruco_markers(image)
    if not aruco_markers:
        raise ValueError("No ArUco markers detected in image")
    
    print(f"Processing image: {image_path}")
    print(f"Detected {len(aruco_markers)} ArUco markers")
    
    # Calculate exam model positions
    exam_model_positions = calculate_exam_model_positions_from_aruco(aruco_markers)
    
    # Convert to the format expected by compare_bubbles.py
    height, width = image.shape[:2]
    exam_model_bubbles = []
    
    for pos in exam_model_positions:
        x, y = pos['center']
        
        # Calculate relative coordinates (0-1 range)
        rel_x = x / width
        rel_y = y / height
        
        bubble_data = {
            'model_letter': pos['model_letter'],
            'relative_center': [rel_x, rel_y],
            'relative_contour': None,
            'aruco_based': True
        }
        
        exam_model_bubbles.append(bubble_data)
        
        print(f"  {pos['model_letter']}: abs({x}, {y}) -> rel({rel_x:.6f}, {rel_y:.6f})")
    
    # Create exam model data structure
    exam_model_data = {
        'exam_model_bubbles': exam_model_bubbles,
        'image_size': {
            'width': width,
            'height': height
        },
        'collection_method': 'aruco_based_calculation',
        'timestamp': 'aruco_positioning',
        'aruco_markers': [{'id': m['id'], 'center': m['center']} for m in aruco_markers]
    }
    
    # Save to exam_models.json
    exam_models_file = 'exam_models.json'
    if os.path.exists(exam_models_file):
        with open(exam_models_file, 'r') as f:
            exam_models = json.load(f)
    else:
        exam_models = {}
    
    exam_model_key = 'exam_model_aruco'
    exam_models[exam_model_key] = exam_model_data
    
    with open(exam_models_file, 'w') as f:
        json.dump(exam_models, f, indent=2)
    
    print(f"\nSaved ArUco-based exam model to: {exam_models_file}")
    print(f"Key: {exam_model_key}")
    
    # Create verification image
    create_verification_image(image, exam_model_positions, exam_model_key)
    
    return exam_model_key

def create_verification_image(image, exam_model_positions, exam_model_key):
    """Create a verification image showing the calculated positions."""
    
    display_image = image.copy()
    colors = [(0, 0, 255), (0, 255, 0), (255, 0, 0)]  # Red, Green, Blue in BGR
    
    # Draw ArUco markers
    aruco_markers = detect_aruco_markers(image)
    for marker in aruco_markers:
        center = tuple(map(int, marker['center']))
        cv2.circle(display_image, center, 15, (255, 255, 0), 3)  # Yellow circles
        cv2.putText(display_image, f"ID:{marker['id']}", 
                   (center[0] + 20, center[1]), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
    
    # Draw exam model bubbles
    for i, pos in enumerate(exam_model_positions):
        center = tuple(pos['center'])
        color = colors[i % len(colors)]
        
        # Draw bubble circle
        cv2.circle(display_image, center, 20, color, 4)
        
        # Add letter label
        text = pos['model_letter']
        text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
        text_x = center[0] - text_size[0] // 2
        text_y = center[1] + text_size[1] // 2
        
        # Background rectangle for text
        cv2.rectangle(display_image, 
                     (text_x - 5, text_y - text_size[1] - 5), 
                     (text_x + text_size[0] + 5, text_y + 5), 
                     (255, 255, 255), -1)
        
        cv2.putText(display_image, text, (text_x, text_y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    
    # Add title
    cv2.rectangle(display_image, (10, 10), (600, 50), (255, 255, 255), -1)
    cv2.rectangle(display_image, (10, 10), (600, 50), (0, 0, 0), 2)
    cv2.putText(display_image, f"ArUco-Based Exam Model - {exam_model_key}", (20, 35), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    
    # Save verification image
    output_path = f"exam_model_aruco_verification.jpg"
    cv2.imwrite(output_path, display_image)
    print(f"Verification image saved as: {output_path}")

def detect_bubble_contour_at_position(image, center_x, center_y, search_radius=25):
    """
    Detect the actual bubble contour around a given position.
    Returns the contour points for accurate fill percentage calculation.
    """
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # Create a region of interest around the center point
    roi_size = search_radius * 2
    x1 = max(0, center_x - search_radius)
    y1 = max(0, center_y - search_radius)
    x2 = min(image.shape[1], center_x + search_radius)
    y2 = min(image.shape[0], center_y + search_radius)
    
    roi = gray[y1:y2, x1:x2]
    
    if roi.size == 0:
        # Fallback to circular contour if ROI is invalid
        return create_circular_contour(center_x, center_y, 15)
    
    # Apply preprocessing to enhance bubble edges
    # Gaussian blur to smooth noise
    blurred = cv2.GaussianBlur(roi, (5, 5), 0)
    
    # Apply adaptive threshold to find bubble edges
    binary = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY_INV, 11, 2)
    
    # Find contours in the ROI
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        # Fallback to circular contour if no contours found
        return create_circular_contour(center_x, center_y, 15)
    
    # Find the contour closest to the center point (relative to ROI)
    roi_center_x = center_x - x1
    roi_center_y = center_y - y1
    
    best_contour = None
    min_distance = float('inf')
    
    for contour in contours:
        # Calculate contour area - we want circular bubbles, not tiny noise
        area = cv2.contourArea(contour)
        if area < 50 or area > 2000:  # Filter out too small or too large contours
            continue
        
        # Check if contour is roughly circular
        perimeter = cv2.arcLength(contour, True)
        if perimeter == 0:
            continue
        circularity = 4 * np.pi * area / (perimeter * perimeter)
        if circularity < 0.3:  # Filter out non-circular shapes
            continue
        
        # Calculate distance from contour center to target point
        M = cv2.moments(contour)
        if M['m00'] != 0:
            cx = int(M['m10'] / M['m00'])
            cy = int(M['m01'] / M['m00'])
            distance = np.sqrt((cx - roi_center_x)**2 + (cy - roi_center_y)**2)
            
            if distance < min_distance:
                min_distance = distance
                best_contour = contour
    
    if best_contour is not None and min_distance < search_radius:
        # Convert ROI coordinates back to full image coordinates
        full_contour = best_contour + np.array([x1, y1])
        return full_contour
    else:
        # Fallback to circular contour
        return create_circular_contour(center_x, center_y, 15)

def create_circular_contour(center_x, center_y, radius):
    """Create a circular contour as fallback."""
    contour_points = []
    for angle in range(0, 360, 10):
        x = center_x + int(radius * np.cos(np.radians(angle)))
        y = center_y + int(radius * np.sin(np.radians(angle)))
        contour_points.append([x, y])
    return np.array(contour_points, dtype=np.int32)

if __name__ == "__main__":
    print("ArUco-Based Exam Model Positioning")
    print("==================================")
    
    # First, show the calculation for reference
    print("\n1. Calculating relative positions from reference image...")
    exam_model_relative, reference_aruco = calculate_exam_model_relative_to_aruco()
    
    # Test with reference image
    print("\n2. Testing with reference image...")
    try:
        exam_model_key = save_aruco_based_exam_model("Arabic@4x-20.jpg")
        
        print(f"\n🎉 Success! ArUco-based exam model coordinates generated!")
        print(f"\nTest the coordinates:")
        print(f"python compare_bubbles.py \"Arabic@4x-20.jpg\" --exam_model_key {exam_model_key}")
        print(f"python compare_bubbles.py \"scan_output copy.png\" --exam_model_key {exam_model_key}")
        
    except Exception as e:
        print(f"Error: {e}") 