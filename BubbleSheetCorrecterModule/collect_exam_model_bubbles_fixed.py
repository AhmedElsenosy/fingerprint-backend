#!/usr/bin/env python3
import cv2
import numpy as np
import json
import os
from datetime import datetime
from bubble_edge_detector import detect_aruco_markers, detect_bubble_fallback

class ExamModelCollectorGUI:
    def __init__(self, image_path):
        self.image_path = image_path
        self.original_image = None
        self.display_image = None
        self.aruco_corners = None
        self.aruco_ids = None
        self.click_positions = []
        self.detected_bubbles = []
        self.window_name = "Click on 3 Exam Model Bubbles"
        self.scale_factor = 1.0
        
    def load_and_prepare_image(self):
        """Load image and detect ArUco markers for alignment."""
        self.original_image = cv2.imread(self.image_path)
        if self.original_image is None:
            raise ValueError(f"Could not load image: {self.image_path}")
        
        print(f"Loaded image: {self.original_image.shape}")
        
        # Detect ArUco markers
        markers = detect_aruco_markers(self.original_image)
        if markers is None or len(markers) < 3:
            print("Warning: Not enough ArUco markers detected, proceeding anyway")
            self.aruco_corners = []
            self.aruco_ids = []
        else:
            print(f"Detected {len(markers)} ArUco markers")
            self.aruco_corners = []
            self.aruco_ids = []
            for marker in markers:
                self.aruco_corners.append(marker['corners'])
                self.aruco_ids.append(marker['id'])
        
        # Prepare display image with proper scaling
        self.prepare_display_image()
        return True
    
    def prepare_display_image(self):
        """Prepare the display image with appropriate scaling."""
        # Scale down if image is too large for display
        max_display_size = 1000
        height, width = self.original_image.shape[:2]
        
        if width > max_display_size or height > max_display_size:
            if width > height:
                self.scale_factor = max_display_size / width
            else:
                self.scale_factor = max_display_size / height
            
            new_width = int(width * self.scale_factor)
            new_height = int(height * self.scale_factor)
            self.display_image = cv2.resize(self.original_image, (new_width, new_height))
            print(f"Scaled image for display: {self.display_image.shape} (scale: {self.scale_factor:.3f})")
        else:
            self.display_image = self.original_image.copy()
            self.scale_factor = 1.0
        
        # Draw ArUco markers on display image
        self.draw_aruco_markers()
    
    def draw_aruco_markers(self):
        """Draw ArUco markers on the display image."""
        if self.aruco_corners and self.aruco_ids:
            for i, corners in enumerate(self.aruco_corners):
                # Scale corners for display
                scaled_corners = np.array(corners) * self.scale_factor
                pts = scaled_corners.astype(np.int32)
                cv2.polylines(self.display_image, [pts], True, (0, 255, 255), 2)
                
                # Draw marker ID
                center = np.mean(pts, axis=0).astype(int)
                cv2.putText(self.display_image, str(self.aruco_ids[i]), tuple(center),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
    
    def detect_contours_near_point(self, point, radius=30):
        """Detect bubble contours near a clicked point."""
        # Convert display coordinates to original image coordinates
        orig_x = int(point[0] / self.scale_factor)
        orig_y = int(point[1] / self.scale_factor)
        
        # Extract ROI around the point in original image
        roi_x1 = max(0, orig_x - radius)
        roi_y1 = max(0, orig_y - radius) 
        roi_x2 = min(self.original_image.shape[1], orig_x + radius)
        roi_y2 = min(self.original_image.shape[0], orig_y + radius)
        
        roi = self.original_image[roi_y1:roi_y2, roi_x1:roi_x2]
        
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
                # Adjust contour coordinates back to original image space
                best_contour = best_contour + np.array([roi_x1, roi_y1])
                
                # Get bounding box center in original image coordinates
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
        
        # If no bubble detected, use original coordinates
        return {
            'center': (orig_x, orig_y),
            'contour': None,
            'circularity': 0.0,
            'area': 0
        }
    
    def mouse_callback(self, event, x, y, flags, param):
        """Handle mouse clicks to collect bubble positions."""
        if event == cv2.EVENT_LBUTTONDOWN and len(self.click_positions) < 3:
            # Store click position (in display coordinates)
            self.click_positions.append((x, y))
            
            # Detect bubble near this click
            bubble_info = self.detect_contours_near_point((x, y))
            
            if bubble_info:
                self.detected_bubbles.append(bubble_info)
                if bubble_info['contour'] is not None:
                    print(f"Bubble {len(self.detected_bubbles)} detected at {bubble_info['center']} (circularity: {bubble_info['circularity']:.3f})")
                else:
                    print(f"Bubble {len(self.detected_bubbles)} position recorded at {bubble_info['center']} (no contour detected)")
            
            # Update display
            self.update_display()
            
            # Check if we have 3 bubbles
            if len(self.detected_bubbles) == 3:
                print("\nCollected 3 bubbles! Press 's' to save or 'r' to restart.")
    
    def update_display(self):
        """Update the display with current click positions and detected bubbles."""
        # Start with fresh display image
        current_display = self.display_image.copy()
        
        # Draw click positions and detected bubbles
        for i, ((click_x, click_y), bubble) in enumerate(zip(self.click_positions, self.detected_bubbles)):
            # Draw click position (small red circle)
            cv2.circle(current_display, (click_x, click_y), 3, (0, 0, 255), -1)
            
            # Draw detected bubble center in display coordinates
            display_center_x = int(bubble['center'][0] * self.scale_factor)
            display_center_y = int(bubble['center'][1] * self.scale_factor)
            
            # Draw bubble center (larger green circle)
            cv2.circle(current_display, (display_center_x, display_center_y), 8, (0, 255, 0), 2)
            
            # Draw contour if detected
            if bubble['contour'] is not None:
                # Scale contour for display
                scaled_contour = (bubble['contour'] * self.scale_factor).astype(np.int32)
                cv2.drawContours(current_display, [scaled_contour], -1, (255, 0, 0), 2)
            
            # Label the bubble
            label = f"Model {chr(65 + i)}"
            cv2.putText(current_display, label, (display_center_x + 15, display_center_y - 15),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(current_display, label, (display_center_x + 15, display_center_y - 15),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 1)
        
        # Add instructions
        instructions = [
            f"Clicks: {len(self.click_positions)}/3",
            "Left click on exam model bubbles A, B, C",
            "Press 's' to save, 'r' to restart, 'q' to quit"
        ]
        
        for i, instruction in enumerate(instructions):
            y_pos = 30 + i * 25
            cv2.putText(current_display, instruction, (10, y_pos),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(current_display, instruction, (10, y_pos),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
        
        # Show the updated display
        cv2.imshow(self.window_name, current_display)
    
    def calculate_relative_positions(self):
        """Calculate positions relative to the original image."""
        height, width = self.original_image.shape[:2]
        relative_bubbles = []
        
        for i, bubble in enumerate(self.detected_bubbles):
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
    
    def save_exam_model_data(self, output_file='exam_models.json'):
        """Save the exam model data to JSON file."""
        if len(self.detected_bubbles) != 3:
            print("Error: Need exactly 3 bubbles to save")
            return False
        
        # Calculate relative positions
        relative_bubbles = self.calculate_relative_positions()
        
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
                'collection_method': 'manual_click'
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
        
        # Also save visualization
        self.save_visualization()
        
        return True
    
    def save_visualization(self, output_file='exam_model_visualization.jpg'):
        """Save a visualization of the detected bubbles."""
        vis_image = self.original_image.copy()
        
        # Draw ArUco markers
        if self.aruco_corners and self.aruco_ids:
            for i, corners in enumerate(self.aruco_corners):
                pts = np.array(corners, dtype=np.int32)
                cv2.polylines(vis_image, [pts], True, (0, 255, 255), 3)
                center = np.mean(pts, axis=0).astype(int)
                cv2.putText(vis_image, str(self.aruco_ids[i]), tuple(center),
                           cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 255), 3)
        
        # Draw detected bubbles
        for i, bubble in enumerate(self.detected_bubbles):
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
    
    def reset_collection(self):
        """Reset the collection to start over."""
        self.click_positions = []
        self.detected_bubbles = []
        print("Reset collection. Click 3 new bubble positions.")
        self.update_display()
    
    def run(self):
        """Main loop for collecting exam model bubbles."""
        try:
            if not self.load_and_prepare_image():
                return False
            
            # Create window with proper flags
            cv2.namedWindow(self.window_name, cv2.WINDOW_AUTOSIZE)
            cv2.setMouseCallback(self.window_name, self.mouse_callback)
            
            print(f"\nExam Model Bubble Collector")
            print(f"===========================")
            print(f"Image: {self.image_path}")
            print(f"Instructions:")
            print(f"1. Click on the center of 3 exam model bubbles (A, B, C)")
            print(f"2. Press 's' to save after collecting 3 bubbles")
            print(f"3. Press 'r' to restart collection")
            print(f"4. Press 'q' to quit")
            print(f"5. ArUco markers are shown in yellow")
            
            # Initial display
            self.update_display()
            
            # Main event loop
            while True:
                key = cv2.waitKey(30) & 0xFF
                
                if key == ord('q'):
                    print("Quit without saving.")
                    break
                elif key == ord('s'):
                    if len(self.detected_bubbles) == 3:
                        if self.save_exam_model_data():
                            print("Model saved successfully!")
                            break
                        else:
                            print("Failed to save model.")
                    else:
                        print(f"Need 3 bubbles, currently have {len(self.detected_bubbles)}")
                elif key == ord('r'):
                    self.reset_collection()
                elif key == 27:  # ESC key
                    print("Quit without saving.")
                    break
        
        except Exception as e:
            print(f"Error in run(): {e}")
            return False
        finally:
            cv2.destroyAllWindows()
        
        return True

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Collect exam model bubble coordinates by clicking')
    parser.add_argument('image_path', help='Path to the image with exam model bubbles')
    parser.add_argument('--output', default='exam_models.json', 
                       help='Output JSON file (default: exam_models.json)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.image_path):
        print(f"Error: Image file '{args.image_path}' not found")
        return 1
    
    try:
        collector = ExamModelCollectorGUI(args.image_path)
        success = collector.run()
        return 0 if success else 1
    except Exception as e:
        print(f"Error: {str(e)}")
        print("\nIf you continue to have display issues, you can use the manual coordinate version:")
        print(f"python collect_exam_model_manual.py {args.image_path} \"x1,y1 x2,y2 x3,y3\"")
        return 1

if __name__ == "__main__":
    exit(main()) 