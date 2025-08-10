#!/usr/bin/env python3

import cv2
import numpy as np
from bubble_edge_detector import detect_aruco_markers

def calculate_exam_model_positions_from_aruco(aruco_markers):
    """Calculate exam model bubble positions based purely on ArUco marker geometry."""
    
    # Find the required ArUco markers (assuming standard layout)
    marker_dict = {marker['id']: marker for marker in aruco_markers}
    
    # We need at least markers 0 (top-left) and 1 (top-right) for the top section
    if 0 not in marker_dict or 1 not in marker_dict:
        print("Warning: Missing required ArUco markers (0 and 1) for exam model calculation")
        return None
    
    # Get top markers (0 = top-left, 1 = top-right)
    top_left_marker = marker_dict[0]
    top_right_marker = marker_dict[1]
    
    # Calculate marker centers
    tl_center = top_left_marker['center']
    tr_center = top_right_marker['center']
    
    # Calculate the width between markers
    width_between_markers = tr_center[0] - tl_center[0]
    
    # Test different vertical positions
    marker_height = tl_center[1]
    
    positions_to_test = []
    
    # Test multiple Y positions
    for y_factor in [0.2, 0.3, 0.4, 0.5, 0.6, 0.7]:
        exam_model_y = int(marker_height * y_factor)
        exam_model_y = max(exam_model_y, 15)
        exam_model_y = min(exam_model_y, marker_height - 30)
        
        # Test multiple horizontal positions
        for left_margin in [0.2, 0.25, 0.3, 0.35]:
            for span in [0.3, 0.35, 0.4, 0.45]:
                start_x = tl_center[0] + width_between_markers * left_margin
                usable_width = width_between_markers * span
                
                bubble_positions = []
                for i in range(3):  # A, B, C
                    if i == 0:
                        x = start_x
                    elif i == 1:
                        x = start_x + usable_width * 0.5
                    else:
                        x = start_x + usable_width
                    
                    bubble_positions.append({
                        'model_letter': chr(65 + i),
                        'center': [int(x), exam_model_y],
                        'params': f"Y:{y_factor:.1f} LM:{left_margin:.2f} S:{span:.2f}"
                    })
                
                positions_to_test.append({
                    'y_factor': y_factor,
                    'left_margin': left_margin,
                    'span': span,
                    'bubbles': bubble_positions
                })
    
    return positions_to_test

def debug_exam_model_positions(image_path):
    """Debug exam model positions by overlaying multiple position options."""
    
    # Load and align the image
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError("Could not load image")
    
    # Detect ArUco markers
    markers = detect_aruco_markers(image)
    if not markers:
        print("No ArUco markers detected")
        return
    
    # Get all position combinations to test
    position_sets = calculate_exam_model_positions_from_aruco(markers)
    
    if not position_sets:
        print("Could not calculate positions")
        return
    
    # Create debug visualization
    debug_image = image.copy()
    
    # Draw ArUco markers
    for marker in markers:
        center = tuple(map(int, marker['center']))
        cv2.circle(debug_image, center, 10, (0, 255, 255), -1)  # Yellow circles
        cv2.putText(debug_image, f"ID:{marker['id']}", 
                   (center[0] + 15, center[1]), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    
    # Colors for different position sets
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255)]
    
    # Test first few position sets
    for idx, pos_set in enumerate(position_sets[:6]):
        color = colors[idx % len(colors)]
        
        for bubble in pos_set['bubbles']:
            center = tuple(bubble['center'])
            
            # Draw bubble circle
            cv2.circle(debug_image, center, 15, color, 2)
            
            # Draw letter
            cv2.putText(debug_image, bubble['model_letter'], 
                       (center[0] - 5, center[1] + 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            
            # Draw parameter info for first bubble of each set
            if bubble['model_letter'] == 'A':
                cv2.putText(debug_image, bubble['params'], 
                           (center[0] - 50, center[1] - 20), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1)
    
    # Save debug image
    output_path = 'debug_exam_model_positions.jpg'
    cv2.imwrite(output_path, debug_image)
    print(f"Debug visualization saved to: {output_path}")
    
    # Print position details
    print("\nPosition sets tested:")
    for idx, pos_set in enumerate(position_sets[:6]):
        print(f"Set {idx + 1}: Y-factor={pos_set['y_factor']:.1f}, "
              f"Left-margin={pos_set['left_margin']:.2f}, Span={pos_set['span']:.2f}")
        for bubble in pos_set['bubbles']:
            print(f"  {bubble['model_letter']}: {bubble['center']}")

if __name__ == "__main__":
    debug_exam_model_positions("scan_output copy.png") 