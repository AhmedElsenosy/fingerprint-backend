#!/usr/bin/env python3

import cv2
import json
import os

def save_exam_model_coordinates_direct():
    """Save specific coordinates directly to exam_models.json file."""
    image_path = "Arabic@4x-20.jpg"
    
    # Load the image to get dimensions
    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: Could not load image {image_path}")
        return None
    
    height, width = image.shape[:2]
    print(f"Image dimensions: {width} x {height}")
    
    # Use the coordinates from our previous successful collection
    # These were collected from the reference image where the bubbles worked correctly
    coordinates = [
        {'letter': 'A', 'center': [1301, 442]},
        {'letter': 'B', 'center': [1191, 442]}, 
        {'letter': 'C', 'center': [1085, 442]}
    ]
    
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
        'collection_method': 'direct_coordinates',
        'timestamp': 'direct_positioning'
    }
    
    # Load existing exam_models.json or create new one
    exam_models_file = 'exam_models.json'
    if os.path.exists(exam_models_file):
        with open(exam_models_file, 'r') as f:
            exam_models = json.load(f)
    else:
        exam_models = {}
    
    # Update with new exam model data
    exam_model_key = 'exam_model_direct'
    exam_models[exam_model_key] = exam_model_data
    
    # Save to file
    with open(exam_models_file, 'w') as f:
        json.dump(exam_models, f, indent=2)
    
    print(f"\nExam model data saved to: {exam_models_file}")
    print(f"Exam model key: {exam_model_key}")
    
    print("\nTo test the new positions, run:")
    print(f"python compare_bubbles.py \"scan_output copy.png\" --exam_model_key {exam_model_key}")
    print(f"python compare_bubbles.py \"Arabic@4x-20.jpg\" --exam_model_key {exam_model_key}")
    
    # Create verification image
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
    
    return exam_model_key

if __name__ == "__main__":
    print("Quick Exam Model Coordinate Saver")
    print("=================================")
    print("Using the previously successful coordinates from reference image...")
    
    exam_model_key = save_exam_model_coordinates_direct()
    
    if exam_model_key:
        print(f"\n🎉 Success! Exam model coordinates saved!")
        print(f"\nTest the coordinates:")
        print(f"python compare_bubbles.py \"scan_output copy.png\" --exam_model_key {exam_model_key}") 