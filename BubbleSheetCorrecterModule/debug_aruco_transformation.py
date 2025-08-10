#!/usr/bin/env python3
"""
Debug script to analyze ArUco marker detection and transformation issues.
"""

import cv2
import numpy as np
import json
from bubble_edge_detector import detect_aruco_markers, compare_with_reference

def analyze_aruco_markers(image_path, reference_data_file='reference_data.json'):
    """Analyze ArUco marker detection and transformation."""
    
    print(f"Analyzing ArUco markers for: {image_path}")
    print("=" * 50)
    
    # Load reference data
    with open(reference_data_file, 'r') as f:
        reference_data = json.load(f)
    
    # Load current image
    current_image = cv2.imread(image_path)
    if current_image is None:
        print(f"ERROR: Could not load image: {image_path}")
        return
    
    print(f"Current image size: {current_image.shape[1]}x{current_image.shape[0]}")
    print(f"Reference image size: {reference_data['image_size']['width']}x{reference_data['image_size']['height']}")
    
    # Detect ArUco markers in current image
    current_markers = detect_aruco_markers(current_image)
    if current_markers is None:
        print("ERROR: No ArUco markers detected in current image")
        return
    
    print(f"\nArUco markers detected in current image: {len(current_markers)}")
    for marker in current_markers:
        print(f"  ID {marker['id']}: center {marker['center']}")
    
    print(f"\nArUco markers in reference data: {len(reference_data['aruco_markers'])}")
    for marker in reference_data['aruco_markers']:
        print(f"  ID {marker['id']}: center {marker['center']}")
    
    # Find matching markers
    ref_marker_points = []
    cur_marker_points = []
    
    for ref_marker in reference_data['aruco_markers']:
        for cur_marker in current_markers:
            if ref_marker['id'] == cur_marker['id']:
                ref_marker_points.append(ref_marker['center'])
                cur_marker_points.append(cur_marker['center'])
                print(f"\nMatched marker ID {ref_marker['id']}:")
                print(f"  Reference: {ref_marker['center']}")
                print(f"  Current:   {cur_marker['center']}")
                
                # Calculate displacement
                dx = cur_marker['center'][0] - ref_marker['center'][0]
                dy = cur_marker['center'][1] - ref_marker['center'][1]
                print(f"  Displacement: ({dx:.1f}, {dy:.1f})")
    
    if len(ref_marker_points) < 3:
        print(f"\nERROR: Not enough matching markers found ({len(ref_marker_points)}). Need at least 3.")
        return
    
    # Calculate transformation matrix
    ref_points = np.float32(ref_marker_points[:3])
    cur_points = np.float32(cur_marker_points[:3])
    
    transform_matrix = cv2.getAffineTransform(cur_points, ref_points)
    
    print(f"\nTransformation matrix:")
    print(transform_matrix)
    
    # Analyze transformation properties
    print("\nTransformation analysis:")
    
    # Extract rotation and scale
    a = transform_matrix[0, 0]
    b = transform_matrix[0, 1]
    c = transform_matrix[1, 0]
    d = transform_matrix[1, 1]
    
    # Scale factors
    scale_x = np.sqrt(a*a + b*b)
    scale_y = np.sqrt(c*c + d*d)
    
    # Rotation angle
    rotation_angle = np.arctan2(b, a) * 180 / np.pi
    
    # Translation
    tx = transform_matrix[0, 2]
    ty = transform_matrix[1, 2]
    
    print(f"  Scale X: {scale_x:.3f}")
    print(f"  Scale Y: {scale_y:.3f}")
    print(f"  Rotation: {rotation_angle:.2f} degrees")
    print(f"  Translation: ({tx:.1f}, {ty:.1f})")
    
    # Test transformation on a point
    test_point = [100, 100]  # Test point
    test_homogeneous = np.array([[test_point[0], test_point[1], 1]], dtype=np.float32)
    transformed_point = transform_matrix.dot(test_homogeneous.T).T[0]
    
    print(f"\nTest point transformation:")
    print(f"  Original: {test_point}")
    print(f"  Transformed: [{transformed_point[0]:.1f}, {transformed_point[1]:.1f}]")
    
    # Create visualization of markers
    create_marker_visualization(current_image, current_markers, reference_data['aruco_markers'], image_path)
    
    return transform_matrix, current_markers, reference_data['aruco_markers']

def create_marker_visualization(image, current_markers, reference_markers, image_path):
    """Create a visualization showing ArUco marker positions."""
    
    vis_image = image.copy()
    
    # Draw current markers in blue
    for marker in current_markers:
        center = tuple(map(int, marker['center']))
        cv2.circle(vis_image, center, 20, (255, 0, 0), 3)  # Blue circle
        cv2.putText(vis_image, f"C{marker['id']}", 
                   (center[0] + 25, center[1]), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
    
    # Draw reference marker positions in red (if they fit in the image)
    height, width = image.shape[:2]
    for marker in reference_markers:
        center = tuple(map(int, marker['center']))
        if 0 <= center[0] < width and 0 <= center[1] < height:
            cv2.circle(vis_image, center, 15, (0, 0, 255), 2)  # Red circle
            cv2.putText(vis_image, f"R{marker['id']}", 
                       (center[0] - 20, center[1] - 25), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    
    # Add legend
    cv2.putText(vis_image, "Blue: Current markers", (20, 40), 
               cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
    cv2.putText(vis_image, "Red: Reference positions", (20, 80), 
               cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    
    output_file = f"aruco_debug_{image_path.replace('.', '_').replace('/', '_')}.jpg"
    cv2.imwrite(output_file, vis_image)
    print(f"\nMarker visualization saved as: {output_file}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Debug ArUco marker detection and transformation')
    parser.add_argument('image_path', help='Path to the image to analyze')
    parser.add_argument('--reference', default='reference_data.json',
                       help='Path to reference data file')
    
    args = parser.parse_args()
    
    try:
        result = analyze_aruco_markers(args.image_path, args.reference)
        if result:
            print("\n✅ Analysis completed successfully")
        else:
            print("\n❌ Analysis failed")
    except Exception as e:
        print(f"\nERROR: {str(e)}")

if __name__ == "__main__":
    main() 