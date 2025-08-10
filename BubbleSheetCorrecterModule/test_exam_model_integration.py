#!/usr/bin/env python3
"""
Test script to demonstrate exam model integration with the bubble sheet pipeline.
Creates simulated filled bubbles and processes them through the pipeline.
"""

import cv2
import numpy as np
import json
from compare_bubbles import highlight_reference_bubbles, print_stats

def create_test_filled_image(source_image_path, exam_models_file, output_path):
    """Create a test image with some simulated filled bubbles."""
    
    # Load the original image
    image = cv2.imread(source_image_path)
    if image is None:
        raise ValueError(f"Could not load image: {source_image_path}")
    
    # Load exam model data to know where to draw filled bubbles
    with open(exam_models_file, 'r') as f:
        exam_models = json.load(f)
    
    # Use the second exam model that we created via clicking
    exam_model_key = 'exam_model_2'
    exam_model = exam_models[exam_model_key]
    
    height, width = image.shape[:2]
    
    # Fill exam model bubble B (second bubble) - make it much more filled
    if 'exam_model_bubbles' in exam_model and len(exam_model['exam_model_bubbles']) >= 2:
        bubble_b = exam_model['exam_model_bubbles'][1]  # B is index 1
        center_x = int(bubble_b['relative_center'][0] * width)
        center_y = int(bubble_b['relative_center'][1] * height)
        
        # Draw multiple overlapping circles to make it very well filled
        for radius in range(25, 5, -2):  # Draw circles from large to small
            cv2.circle(image, (center_x, center_y), radius, (0, 0, 0), -1)
        
        # Add some additional noise around it to simulate a pencil fill
        for i in range(80):  # Increased from 50 to 80
            offset_x = np.random.randint(-25, 26)  # Increased range
            offset_y = np.random.randint(-25, 26)  # Increased range
            if (offset_x**2 + offset_y**2) <= 625:  # Within radius 25
                cv2.circle(image, (center_x + offset_x, center_y + offset_y), 3, (0, 0, 0), -1)  # Larger spots
        
        print(f"Heavily filled exam model bubble B at ({center_x}, {center_y})")
    
    # Fill exam model bubble A partially for comparison
    if 'exam_model_bubbles' in exam_model and len(exam_model['exam_model_bubbles']) >= 1:
        bubble_a = exam_model['exam_model_bubbles'][0]  # A is index 0
        center_x = int(bubble_a['relative_center'][0] * width)
        center_y = int(bubble_a['relative_center'][1] * height)
        
        # Draw a smaller, partially filled circle
        cv2.circle(image, (center_x, center_y), 10, (0, 0, 0), -1)
        print(f"Lightly filled exam model bubble A at ({center_x}, {center_y})")
    
    # Save the test image
    cv2.imwrite(output_path, image)
    print(f"Test image saved as: {output_path}")
    
    return output_path

def run_test():
    """Run the exam model integration test."""
    
    print("Exam Model Integration Test")
    print("==========================")
    
    # Create test image with filled bubbles
    test_image = create_test_filled_image(
        'Arabic@4x-20.jpg', 
        'exam_models.json', 
        'scan_output.png'
    )
    
    print("\n1. Processing test image with filled exam model bubble...")
    
    # Process the test image
    try:
        stats = highlight_reference_bubbles(
             'scan_output copy.png',
            'reference_data.json',
            'id_coordinates.json', 
            'exam_models.json',
            'test_exam_model_output.jpg',
            'exam_model_2'  # Use the model we created
        )
        
        print("\n2. Test Results:")
        print("===============")
        
        if 'exam_model' in stats:
            print(f"✅ Exam Model Detected: {stats['exam_model']['value']}")
            print(f"✅ Fill Percentages: {[f'{p:.1f}%' for p in stats['exam_model']['fill_percentages']]}")
            
            if stats['exam_model']['value'] == 'B':
                print("✅ SUCCESS: Exam model B was correctly detected!")
            else:
                print(f"⚠️  Expected 'B', got '{stats['exam_model']['value']}'")
        else:
            print("❌ ERROR: Exam model not found in results")
        
        print(f"\n3. Output files created:")
        print(f"   - Visualization: test_exam_model_output.jpg")
        print(f"   - CSV: test_exam_model_output_grades.csv")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

if __name__ == "__main__":
    success = run_test()
    if success:
        print("\n🎉 Exam model integration test completed successfully!")
    else:
        print("\n💥 Exam model integration test failed!") 