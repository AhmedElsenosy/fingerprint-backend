import cv2
import numpy as np
import json
import os
from datetime import datetime
from bubble_edge_detector import detect_aruco_markers, detect_bubble_fallback

class ExamModelCollectorManual:
    def __init__(self, image_path):
        self.image_path = image_path
        self.original_image = None
        self.aruco_corners = None
        self.aruco_ids = None
        
    def load_and_prepare_image(self):
        """Load image and detect ArUco markers for alignment."""
        self.original_image = cv2.imread(self.image_path)
        if self.original_image is None:
            raise ValueError(f"Could not load image: {self.image_path}")
        
        print(f"Loaded image: {self.original_image.shape}")
        
        # Detect ArUco markers
        markers = detect_aruco_markers(self.original_image)
        if markers is None or len(markers) < 3:
            print("Warning: Not enough ArUco markers for perfect alignment, proceeding anyway")
            self.aruco_corners = []
            self.aruco_ids = []
        else:
            print(f"Detected {len(markers)} ArUco markers")
            
            # Store marker information
            self.aruco_corners = []
            self.aruco_ids = []
            for marker in markers:
                self.aruco_corners.append(marker['corners'])
                self.aruco_ids.append(marker['id'])
        
        return True
    
    def detect_contours_near_point(self, image, point, radius=30):
        """Detect bubble contours near a specified point."""
        x, y = point
        
        # Extract ROI around the point
        roi_x1 = max(0, x - radius)
        roi_y1 = max(0, y - radius) 
        roi_x2 = min(image.shape[1], x + radius)
        roi_y2 = min(image.shape[0], y + radius)
        
        roi = image[roi_y1:roi_y2, roi_x1:roi_x2]
        
        if roi.size == 0:
            return None
            
        # Convert to grayscale if needed
        if len(roi.shape) == 3:
            roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        else:
            roi_gray = roi.copy()
        
        try:
            # Use existing bubble detection function
            best_contour, circularity = detect_bubble_fallback(roi_gray, target_area=200)
            
            if best_contour is not None:
                # Adjust contour coordinates back to full image space
                best_contour = best_contour + np.array([roi_x1, roi_y1])
                
                # Get bounding box center
                M = cv2.moments(best_contour)
                if M['m00'] != 0:
                    center_x = int(M['m10'] / M['m00'])
                    center_y = int(M['m01'] / M['m00'])
                    
                    return {
                        'center': (center_x, center_y),
                        'contour': best_contour,
                        'circularity': circularity,
                        'area': cv2.contourArea(best_contour)
                    }
        except Exception as e:
            print(f"Error in bubble detection: {e}")
        
        return None
    
    def process_coordinates(self, coordinates):
        """Process the given coordinates and detect bubbles."""
        detected_bubbles = []
        
        for i, (x, y) in enumerate(coordinates):
            print(f"Processing coordinate {i+1}: ({x}, {y})")
            
            # Detect bubble near this coordinate
            bubble_info = self.detect_contours_near_point(self.original_image, (x, y))
            
            if bubble_info:
                detected_bubbles.append(bubble_info)
                print(f"  Bubble detected at {bubble_info['center']} (circularity: {bubble_info['circularity']:.3f})")
            else:
                # If no bubble detected, use specified position as center
                detected_bubbles.append({
                    'center': (x, y),
                    'contour': None,
                    'circularity': 0.0,
                    'area': 0
                })
                print(f"  No bubble detected, using specified position: ({x}, {y})")
        
        return detected_bubbles
    
    def calculate_relative_positions(self, detected_bubbles):
        """Calculate positions relative to the original image."""
        height, width = self.original_image.shape[:2]
        relative_bubbles = []
        
        for i, bubble in enumerate(detected_bubbles):
            center_x, center_y = bubble['center']
            
            # Convert to relative coordinates (0-1 range)
            rel_x = center_x / width
            rel_y = center_y / height
            
            # Store relative contour if available
            relative_contour = None
            if bubble['contour'] is not None:
                contour_points = bubble['contour'].squeeze()
                relative_contour = [[float(x/width), float(y/height)] for x, y in contour_points]
            
            relative_bubbles.append({
                'model_letter': chr(65 + i),  # A, B, C
                'relative_center': [float(rel_x), float(rel_y)],
                'relative_contour': relative_contour,
                'absolute_center': [int(center_x), int(center_y)],
                'circularity': float(bubble['circularity']),
                'area': float(bubble['area'])
            })
        
        return relative_bubbles
    
    def save_exam_model_data(self, detected_bubbles, output_file='exam_models.json'):
        """Save the exam model data to JSON file."""
        if len(detected_bubbles) != 3:
            print("Error: Need exactly 3 bubbles to save")
            return False
        
        # Calculate relative positions
        relative_bubbles = self.calculate_relative_positions(detected_bubbles)
        
        # Prepare ArUco marker data
        aruco_data = []
        if self.aruco_corners and self.aruco_ids:
            for i, (corners, marker_id) in enumerate(zip(self.aruco_corners, self.aruco_ids)):
                aruco_data.append({
                    'id': int(marker_id),
                    'corners': corners
                })
        
        # Create exam model entry
        exam_model_entry = {
            'aruco_markers': aruco_data,
            'exam_model_bubbles': relative_bubbles,
            'image_size': {
                'width': self.original_image.shape[1],
                'height': self.original_image.shape[0]
            },
            'source_image': self.image_path,
            'timestamp': datetime.now().isoformat(),
            'metadata': {
                'num_bubbles': len(relative_bubbles),
                'collection_method': 'manual_coordinates'
            }
        }
        
        # Load existing data or create new
        exam_models_data = {}
        if os.path.exists(output_file):
            try:
                with open(output_file, 'r') as f:
                    exam_models_data = json.load(f)
            except:
                pass
        
        # Find next available exam model key
        model_num = 1
        while f'exam_model_{model_num}' in exam_models_data:
            model_num += 1
        
        # Save the new model
        model_key = f'exam_model_{model_num}'
        exam_models_data[model_key] = exam_model_entry
        
        # Write to file
        with open(output_file, 'w') as f:
            json.dump(exam_models_data, f, indent=2)
        
        print(f"\nExam model saved as '{model_key}' in {output_file}")
        print(f"Bubbles collected:")
        for bubble in relative_bubbles:
            print(f"  Model {bubble['model_letter']}: {bubble['absolute_center']} -> relative: ({bubble['relative_center'][0]:.3f}, {bubble['relative_center'][1]:.3f})")
        
        return True
    
    def save_visualization(self, detected_bubbles, output_file='exam_model_visualization.jpg'):
        """Save a visualization of the detected bubbles."""
        vis_image = self.original_image.copy()
        
        # Draw ArUco markers if available
        if self.aruco_corners and self.aruco_ids:
            for i, corners in enumerate(self.aruco_corners):
                try:
                    pts = np.array(corners, dtype=np.int32)
                    cv2.polylines(vis_image, [pts], True, (0, 255, 255), 3)
                    # Draw marker ID
                    center = np.mean(pts, axis=0).astype(int)
                    cv2.putText(vis_image, str(self.aruco_ids[i]), tuple(center),
                               cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 255), 3)
                except Exception as e:
                    print(f"Error drawing marker {i}: {e}")
        
        # Draw detected bubbles
        for i, bubble in enumerate(detected_bubbles):
            center = bubble['center']
            
            # Draw center point
            cv2.circle(vis_image, center, 10, (0, 0, 255), -1)
            
            # Draw contour if detected
            if bubble['contour'] is not None:
                cv2.drawContours(vis_image, [bubble['contour']], -1, (255, 0, 0), 3)
            
            # Label the bubble
            label = f"Model {chr(65 + i)}"
            cv2.putText(vis_image, label, (center[0] + 20, center[1] - 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)
            cv2.putText(vis_image, label, (center[0] + 20, center[1] - 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 0), 2)
        
        cv2.imwrite(output_file, vis_image)
        print(f"Visualization saved as {output_file}")

def parse_coordinates(coord_string):
    """Parse coordinate string like '100,200 300,400 500,600' into list of tuples."""
    try:
        coords = []
        for pair in coord_string.split():
            x, y = map(int, pair.split(','))
            coords.append((x, y))
        return coords
    except ValueError:
        raise ValueError("Invalid coordinate format. Use format: 'x1,y1 x2,y2 x3,y3'")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Collect exam model bubble coordinates manually')
    parser.add_argument('image_path', help='Path to the image with exam model bubbles')
    parser.add_argument('coordinates', help='Three coordinates in format: "x1,y1 x2,y2 x3,y3"')
    parser.add_argument('--output', default='exam_models.json', 
                       help='Output JSON file (default: exam_models.json)')
    parser.add_argument('--visualization', default='exam_model_visualization.jpg',
                       help='Output visualization image (default: exam_model_visualization.jpg)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.image_path):
        print(f"Error: Image file '{args.image_path}' not found")
        return 1
    
    try:
        # Parse coordinates
        coordinates = parse_coordinates(args.coordinates)
        if len(coordinates) != 3:
            print("Error: Must provide exactly 3 coordinates")
            return 1
        
        print(f"Processing coordinates: {coordinates}")
        
        # Create collector and process
        collector = ExamModelCollectorManual(args.image_path)
        
        if not collector.load_and_prepare_image():
            return 1
        
        detected_bubbles = collector.process_coordinates(coordinates)
        
        # Save data
        if collector.save_exam_model_data(detected_bubbles, args.output):
            collector.save_visualization(detected_bubbles, args.visualization)
            print("Successfully completed exam model collection!")
            return 0
        else:
            print("Failed to save exam model data")
            return 1
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1

if __name__ == "__main__":
    exit(main()) 