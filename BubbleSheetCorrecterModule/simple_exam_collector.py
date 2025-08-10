#!/usr/bin/env python3

import cv2
import numpy as np
import json
import os
from bubble_edge_detector import detect_aruco_markers

def create_reference_image_with_grid(image_path):
    """Create a reference image with grid lines and markers to help with coordinate selection."""
    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: Could not load image {image_path}")
        return None
    
    height, width = image.shape[:2]
    display_image = image.copy()
    
    # Detect and draw ArUco markers
    markers = detect_aruco_markers(image)
    colors = [(0, 0, 255), (0, 255, 0), (255, 0, 0), (0, 255, 255)]  # BGR format
    
    for i, marker in enumerate(markers):
        center = tuple(map(int, marker['center']))
        color = colors[i % len(colors)]
        
        # Draw marker center
        cv2.circle(display_image, center, 15, color, 3)
        
        # Add marker ID label
        cv2.putText(display_image, f"ID:{marker['id']}", 
                   (center[0] + 25, center[1]), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    
    # Draw grid lines every 50 pixels
    grid_color = (128, 128, 128)  # Gray
    for x in range(0, width, 50):
        cv2.line(display_image, (x, 0), (x, height), grid_color, 1)
    for y in range(0, height, 50):
        cv2.line(display_image, (0, y), (width, y), grid_color, 1)
    
    # Add coordinate labels every 100 pixels
    for x in range(0, width, 100):
        for y in range(0, height, 100):
            cv2.putText(display_image, f"({x},{y})", (x+5, y+15), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
    
    # Add instruction text
    cv2.rectangle(display_image, (10, 10), (800, 80), (255, 255, 255), -1)
    cv2.rectangle(display_image, (10, 10), (800, 80), (0, 0, 0), 2)
    
    cv2.putText(display_image, "EXAM MODEL BUBBLE COORDINATE HELPER", (20, 35), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    cv2.putText(display_image, "Use this image to identify coordinates for A, B, C bubbles", (20, 60), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
    
    # Save the reference image
    output_path = "exam_model_coordinate_helper.jpg"
    cv2.imwrite(output_path, display_image)
    print(f"Reference image saved as: {output_path}")
    print("Open this image to identify the coordinates of exam model bubbles A, B, and C")
    
    return image, output_path

def collect_coordinates_manually():
    """Collect coordinates manually through user input."""
    print("\n" + "="*60)
    print("MANUAL COORDINATE COLLECTION")
    print("="*60)
    print("Look at the exam_model_coordinate_helper.jpg image")
    print("Find the center coordinates of bubbles A, B, and C")
    print("Enter the coordinates when prompted")
    
    coordinates = []
    letters = ['A', 'B', 'C']
    
    for letter in letters:
        while True:
            try:
                x_input = input(f"\nEnter X coordinate for bubble {letter}: ").strip()
                y_input = input(f"Enter Y coordinate for bubble {letter}: ").strip()
                
                x = int(x_input)
                y = int(y_input)
                
                coordinates.append({
                    'letter': letter,
                    'center': [x, y]
                })
                
                print(f"Bubble {letter} recorded at: ({x}, {y})")
                break
                
            except ValueError:
                print("Please enter valid integer coordinates")
    
    return coordinates

def save_exam_model_coordinates(image_path, coordinates):
    """Save coordinates to exam_models.json file."""
    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: Could not load image {image_path}")
        return None
    
    height, width = image.shape[:2]
    
    print("\n" + "="*60)
    print("SAVING EXAM MODEL POSITIONS TO exam_models.json")
    print("="*60)
    
    # Create exam model bubbles data in the correct format
    exam_model_bubbles = []
    
    for pos in coordinates:
        x, y = pos['center']
        
        # Calculate relative coordinates (0-1 range)
        rel_x = x / width
        rel_y = y / height
        
        # Create bubble data structure matching what compare_bubbles.py expects
        bubble_data = {
            'model_letter': pos['letter'],
            'relative_center': [rel_x, rel_y],
            'relative_contour': None  # Will be created as circle in compare_bubbles.py
        }
        
        exam_model_bubbles.append(bubble_data)
        
        print(f"Bubble {pos['letter']}:")
        print(f"  Absolute position: ({x}, {y})")
        print(f"  Relative position: ({rel_x:.6f}, {rel_y:.6f})")
    
    # Create the complete exam model data structure
    exam_model_data = {
        'exam_model_bubbles': exam_model_bubbles,
        'image_size': {
            'width': width,
            'height': height
        },
        'collection_method': 'manual_input',
        'timestamp': 'manual_positioning'
    }
    
    # Load existing exam_models.json or create new one
    exam_models_file = 'exam_models.json'
    if os.path.exists(exam_models_file):
        with open(exam_models_file, 'r') as f:
            exam_models = json.load(f)
    else:
        exam_models = {}
    
    # Update with new exam model data
    exam_model_key = 'exam_model_manual'
    exam_models[exam_model_key] = exam_model_data
    
    # Save to file
    with open(exam_models_file, 'w') as f:
        json.dump(exam_models, f, indent=2)
    
    print(f"\nExam model data saved to: {exam_models_file}")
    print(f"Exam model key: {exam_model_key}")
    
    print("\nTo test the new positions, run:")
    print(f"python compare_bubbles.py \"scan_output copy.png\" --exam_model_key {exam_model_key}")
    print(f"python compare_bubbles.py \"Arabic@4x-20.jpg\" --exam_model_key {exam_model_key}")
    
    return exam_model_key

def create_verification_image(image_path, coordinates, exam_model_key):
    """Create an image showing where the coordinates were placed."""
    image = cv2.imread(image_path)
    if image is None:
        return
    
    display_image = image.copy()
    colors = [(0, 0, 255), (0, 255, 0), (255, 0, 0)]  # Red, Green, Blue in BGR
    
    for i, pos in enumerate(coordinates):
        center = tuple(pos['center'])
        color = colors[i % len(colors)]
        
        # Draw bubble circle
        cv2.circle(display_image, center, 20, color, 4)
        
        # Add letter label with background
        text = pos['letter']
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
    cv2.putText(display_image, f"Exam Model Coordinates - {exam_model_key}", (20, 35), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    
    # Save verification image
    output_path = f"exam_model_verification_{exam_model_key}.jpg"
    cv2.imwrite(output_path, display_image)
    print(f"Verification image saved as: {output_path}")

def main():
    image_path = "Arabic@4x-20.jpg"
    
    print("Simple Exam Model Coordinate Collector")
    print("=====================================")
    print(f"Using reference image: {image_path}")
    
    # Create reference image with grid
    image, helper_path = create_reference_image_with_grid(image_path)
    if image is None:
        return
    
    print(f"\n1. Open the file: {helper_path}")
    print("2. Look for the exam model bubbles A, B, and C")
    print("3. Note their center coordinates using the grid as reference")
    print("4. Enter the coordinates when prompted below")
    
    # Collect coordinates manually
    coordinates = collect_coordinates_manually()
    
    # Save to file
    exam_model_key = save_exam_model_coordinates(image_path, coordinates)
    
    if exam_model_key:
        # Create verification image
        create_verification_image(image_path, coordinates, exam_model_key)
        
        print(f"\n🎉 Success! Exam model coordinates collected and saved!")
        print(f"\nNext steps:")
        print(f"1. Check the verification image: exam_model_verification_{exam_model_key}.jpg")
        print(f"2. Test with: python compare_bubbles.py \"scan_output copy.png\" --exam_model_key {exam_model_key}")

if __name__ == "__main__":
    main() 