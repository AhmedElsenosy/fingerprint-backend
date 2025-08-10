import cv2
import numpy as np
import json
import os
from datetime import datetime
from bubble_edge_detector import detect_aruco_markers, detect_bubble_fallback

class ExamModelCollector:
    def __init__(self, image_path):
        self.image_path = image_path
        self.original_image = None
        self.aligned_image = None
        self.aruco_corners = None
        self.aruco_ids = None
        self.transform_matrix = None
        self.click_positions = []
        self.detected_bubbles = []
        self.window_name = "Exam Model Collector"
        
    def load_and_prepare_image(self):
        """Load image and detect ArUco markers for alignment."""
        self.original_image = cv2.imread(self.image_path)
        if self.original_image is None:
            raise ValueError(f"Could not load image: {self.image_path}")
        
        print(f"Loaded image: {self.original_image.shape}")
        
        # Detect ArUco markers
        markers = detect_aruco_markers(self.original_image)
        if markers is None or len(markers) < 3:  # Reduced requirement
            print("Warning: Not enough ArUco markers for perfect alignment, proceeding anyway")
            # Use original image without alignment
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
        
        # Use original image as aligned (simplified approach)
        self.aligned_image = self.original_image.copy()
        
        # Resize if image is too large for display
        max_display_width = 1200
        if self.aligned_image.shape[1] > max_display_width:
            scale = max_display_width / self.aligned_image.shape[1]
            new_width = int(self.aligned_image.shape[1] * scale)
            new_height = int(self.aligned_image.shape[0] * scale)
            self.aligned_image = cv2.resize(self.aligned_image, (new_width, new_height))
            print(f"Resized image for display: {self.aligned_image.shape}")
        
        return True
    
    def detect_contours_near_point(self, image, point, radius=30):
        """Detect bubble contours near a clicked point."""
        x, y = point
        
        # Extract ROI around the click
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
    
    def mouse_callback(self, event, x, y, flags, param):
        """Handle mouse clicks to collect bubble positions."""
        if event == cv2.EVENT_LBUTTONDOWN and len(self.click_positions) < 3:
            # Store click position
            self.click_positions.append((x, y))
            
            # Detect bubble near this click
            bubble_info = self.detect_contours_near_point(self.aligned_image, (x, y))
            
            if bubble_info:
                self.detected_bubbles.append(bubble_info)
                print(f"Bubble {len(self.detected_bubbles)} detected at {bubble_info['center']} (circularity: {bubble_info['circularity']:.3f})")
            else:
                # If no bubble detected, use click position as center
                self.detected_bubbles.append({
                    'center': (x, y),
                    'contour': None,
                    'circularity': 0.0,
                    'area': 0
                })
                print(f"No bubble detected at click {len(self.detected_bubbles)}, using click position: ({x}, {y})")
            
            # Update display
            try:
                self.update_display()
            except Exception as e:
                print(f"Display update error: {e}")
            
            # Check if we have 3 bubbles
            if len(self.detected_bubbles) == 3:
                print("\nCollected 3 bubbles! Press 's' to save or 'r' to restart.")
    
    def update_display(self):
        """Update the display with current click positions and detected bubbles."""
        display_image = self.aligned_image.copy()
        
        # Draw ArUco markers if available
        if self.aruco_corners and self.aruco_ids:
            for i, corners in enumerate(self.aruco_corners):
                try:
                    pts = np.array(corners, dtype=np.int32)
                    cv2.polylines(display_image, [pts], True, (0, 255, 255), 2)
                    # Draw marker ID
                    center = np.mean(pts, axis=0).astype(int)
                    cv2.putText(display_image, str(self.aruco_ids[i]), tuple(center),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                except Exception as e:
                    print(f"Error drawing marker {i}: {e}")
        
        # Draw click positions and detected bubbles
        for i, (click_pos, bubble) in enumerate(zip(self.click_positions, self.detected_bubbles)):
            try:
                # Draw click position
                cv2.circle(display_image, click_pos, 5, (0, 0, 255), -1)
                
                # Draw detected bubble center
                bubble_center = bubble['center']
                cv2.circle(display_image, bubble_center, 8, (0, 255, 0), 2)
                
                # Draw contour if detected
                if bubble['contour'] is not None:
                    cv2.drawContours(display_image, [bubble['contour']], -1, (255, 0, 0), 2)
                
                # Label the bubble
                label = f"Model {chr(65 + i)}"
                cv2.putText(display_image, label, (bubble_center[0] + 15, bubble_center[1] - 15),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                cv2.putText(display_image, label, (bubble_center[0] + 15, bubble_center[1] - 15),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
            except Exception as e:
                print(f"Error drawing bubble {i}: {e}")
        
        # Add instructions
        instructions = [
            f"Clicks: {len(self.click_positions)}/3",
            "Left click on bubble centers",
            "Press 's' to save, 'r' to restart, 'q' to quit"
        ]
        
        for i, instruction in enumerate(instructions):
            try:
                y_pos = 30 + i * 25
                cv2.putText(display_image, instruction, (10, y_pos),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                cv2.putText(display_image, instruction, (10, y_pos),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
            except Exception as e:
                print(f"Error drawing instruction {i}: {e}")
        
        try:
            cv2.imshow(self.window_name, display_image)
        except Exception as e:
            print(f"Error showing image: {e}")
            raise e
    
    def calculate_relative_positions(self):
        """Calculate positions relative to the aligned/warped image."""
        height, width = self.original_image.shape[:2]  # Use original image dimensions
        relative_bubbles = []
        
        # Calculate scale factor if image was resized for display
        scale_x = self.original_image.shape[1] / self.aligned_image.shape[1]
        scale_y = self.original_image.shape[0] / self.aligned_image.shape[0]
        
        for i, bubble in enumerate(self.detected_bubbles):
            center_x, center_y = bubble['center']
            
            # Scale back to original image coordinates
            orig_center_x = int(center_x * scale_x)
            orig_center_y = int(center_y * scale_y)
            
            # Convert to relative coordinates (0-1 range)
            rel_x = orig_center_x / width
            rel_y = orig_center_y / height
            
            # Store relative contour if available
            relative_contour = None
            if bubble['contour'] is not None:
                contour_points = bubble['contour'].squeeze()
                # Scale contour back to original image coordinates
                scaled_contour = []
                for x, y in contour_points:
                    orig_x = x * scale_x
                    orig_y = y * scale_y
                    scaled_contour.append([float(orig_x/width), float(orig_y/height)])
                relative_contour = scaled_contour
            
            relative_bubbles.append({
                'model_letter': chr(65 + i),  # A, B, C
                'relative_center': [float(rel_x), float(rel_y)],
                'relative_contour': relative_contour,
                'absolute_center': [orig_center_x, orig_center_y],
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
        
        return True
    
    def reset_collection(self):
        """Reset the collection to start over."""
        self.click_positions = []
        self.detected_bubbles = []
        print("Reset collection. Click 3 new bubble positions.")
        try:
            self.update_display()
        except Exception as e:
            print(f"Display update error during reset: {e}")
    
    def run(self):
        """Main loop for collecting exam model bubbles."""
        try:
            if not self.load_and_prepare_image():
                return False
            
            # Test if OpenCV display works
            try:
                cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
                cv2.resizeWindow(self.window_name, 800, 600)
                cv2.setMouseCallback(self.window_name, self.mouse_callback)
            except Exception as e:
                print(f"Error setting up display: {e}")
                return False
            
            print(f"\nExam Model Bubble Collector")
            print(f"===========================")
            print(f"Image: {self.image_path}")
            print(f"Instructions:")
            print(f"1. Click on the center of 3 exam model bubbles (A, B, C)")
            print(f"2. Press 's' to save after collecting 3 bubbles")
            print(f"3. Press 'r' to restart collection")
            print(f"4. Press 'q' to quit")
            
            self.update_display()
            
            while True:
                try:
                    key = cv2.waitKey(1) & 0xFF
                    
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
                except KeyboardInterrupt:
                    print("\nInterrupted by user.")
                    break
                except Exception as e:
                    print(f"Error in main loop: {e}")
                    break
        
        except Exception as e:
            print(f"Error in run(): {e}")
            return False
        finally:
            try:
                cv2.destroyAllWindows()
            except:
                pass
        
        return True

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Collect exam model bubble coordinates')
    parser.add_argument('image_path', help='Path to the image with exam model bubbles')
    parser.add_argument('--output', default='exam_models.json', 
                       help='Output JSON file (default: exam_models.json)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.image_path):
        print(f"Error: Image file '{args.image_path}' not found")
        return 1
    
    try:
        collector = ExamModelCollector(args.image_path)
        success = collector.run()
        return 0 if success else 1
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1

if __name__ == "__main__":
    exit(main()) 