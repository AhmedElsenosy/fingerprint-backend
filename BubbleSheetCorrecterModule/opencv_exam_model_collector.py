#!/usr/bin/env python3

import cv2
import numpy as np
import json
import os
from bubble_edge_detector import detect_aruco_markers

class OpenCVBubbleCollector:
    def __init__(self, image_path):
        self.image_path = image_path
        self.image = cv2.imread(image_path)
        self.display_image = self.image.copy()
        self.clicked_positions = []
        self.letters = ['A', 'B', 'C']
        self.current_bubble = 0
        
        # Detect ArUco markers for reference
        self.markers = detect_aruco_markers(self.image)
        
        print("OpenCV Exam Model Bubble Collector")
        print("==================================")
        print("Instructions:")
        print("- Click on the center of each exam model bubble")
        print("- Click A, then B, then C (in order)")
        print("- Press 's' to save when done")
        print("- Press 'r' to reset if you make a mistake")
        print("- Press 'q' to quit without saving")
        print(f"\nClick on bubble A first...")
        
        # Draw ArUco markers on display image
        self.draw_aruco_markers()
        
        # Add instruction text
        self.update_instruction()
    
    def draw_aruco_markers(self):
        """Draw ArUco markers on the display image for reference."""
        colors = [(0, 0, 255), (0, 255, 0), (255, 0, 0), (0, 255, 255)]  # BGR format
        
        for i, marker in enumerate(self.markers):
            center = tuple(map(int, marker['center']))
            color = colors[i % len(colors)]
            
            # Draw marker center
            cv2.circle(self.display_image, center, 15, color, 3)
            
            # Add marker ID label
            cv2.putText(self.display_image, f"ID:{marker['id']}", 
                       (center[0] + 25, center[1]), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    
    def update_instruction(self):
        """Update instruction text on the image."""
        # Clear previous instruction area
        self.display_image = self.image.copy()
        self.draw_aruco_markers()
        self.draw_clicked_bubbles()
        
        if self.current_bubble < len(self.letters):
            instruction = f"Click on bubble {self.letters[self.current_bubble]}"
        elif len(self.clicked_positions) == 3:
            instruction = "All bubbles recorded! Press 's' to save"
        else:
            instruction = "Press 'r' to reset, 'q' to quit"
        
        # Add background rectangle for text
        cv2.rectangle(self.display_image, (10, 10), (500, 50), (255, 255, 255), -1)
        cv2.rectangle(self.display_image, (10, 10), (500, 50), (0, 0, 0), 2)
        
        # Add instruction text
        cv2.putText(self.display_image, instruction, (20, 35), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    
    def draw_clicked_bubbles(self):
        """Draw previously clicked bubble positions."""
        colors = [(0, 0, 255), (0, 255, 0), (255, 0, 0)]  # Red, Green, Blue in BGR
        
        for i, pos in enumerate(self.clicked_positions):
            center = tuple(pos['center'])
            color = colors[i % len(colors)]
            
            # Draw bubble circle
            cv2.circle(self.display_image, center, 20, color, 4)
            
            # Add letter label with background
            text = pos['letter']
            text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
            text_x = center[0] - text_size[0] // 2
            text_y = center[1] + text_size[1] // 2
            
            # Background rectangle for text
            cv2.rectangle(self.display_image, 
                         (text_x - 5, text_y - text_size[1] - 5), 
                         (text_x + text_size[0] + 5, text_y + 5), 
                         (255, 255, 255), -1)
            
            cv2.putText(self.display_image, text, (text_x, text_y), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    
    def mouse_callback(self, event, x, y, flags, param):
        """Handle mouse clicks."""
        if event == cv2.EVENT_LBUTTONDOWN:
            if self.current_bubble < len(self.letters):
                # Record the click position
                self.clicked_positions.append({
                    'letter': self.letters[self.current_bubble],
                    'center': [x, y]
                })
                
                print(f"Bubble {self.letters[self.current_bubble]} recorded at: ({x}, {y})")
                
                self.current_bubble += 1
                
                if self.current_bubble < len(self.letters):
                    print(f"Now click on bubble {self.letters[self.current_bubble]}...")
                else:
                    print("All bubbles recorded! Press 's' to save, 'r' to reset")
                
                self.update_instruction()
    
    def reset_clicks(self):
        """Reset all clicked positions."""
        self.clicked_positions = []
        self.current_bubble = 0
        print("Reset - Click on bubble A first...")
        self.update_instruction()
    
    def save_to_exam_models_file(self):
        """Save the clicked positions to exam_models.json in the correct format."""
        if len(self.clicked_positions) != 3:
            print(f"Error: Need exactly 3 positions, got {len(self.clicked_positions)}")
            return None
        
        # Get image dimensions
        height, width = self.image.shape[:2]
        
        print("\n" + "="*60)
        print("SAVING EXAM MODEL POSITIONS TO exam_models.json")
        print("="*60)
        
        # Create exam model bubbles data in the correct format
        exam_model_bubbles = []
        
        for pos in self.clicked_positions:
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
            'collection_method': 'opencv_click',
            'timestamp': 'opencv_positioning'
        }
        
        # Load existing exam_models.json or create new one
        exam_models_file = 'exam_models.json'
        if os.path.exists(exam_models_file):
            with open(exam_models_file, 'r') as f:
                exam_models = json.load(f)
        else:
            exam_models = {}
        
        # Update with new exam model data
        exam_model_key = 'exam_model_opencv'
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
    
    def run(self):
        """Run the interactive position collector."""
        window_name = "Exam Model Bubble Collector - OpenCV"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 1200, 900)
        cv2.setMouseCallback(window_name, self.mouse_callback)
        
        while True:
            cv2.imshow(window_name, self.display_image)
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                print("Quit without saving")
                break
            elif key == ord('r'):
                self.reset_clicks()
            elif key == ord('s'):
                if len(self.clicked_positions) == 3:
                    exam_model_key = self.save_to_exam_models_file()
                    if exam_model_key:
                        print(f"\n🎉 Success! Exam model coordinates saved!")
                        cv2.destroyAllWindows()
                        return exam_model_key
                else:
                    print(f"Need 3 positions, only have {len(self.clicked_positions)}")
            elif key == 27:  # ESC key
                print("Quit without saving")
                break
        
        cv2.destroyAllWindows()
        return None

if __name__ == "__main__":
    print("Starting OpenCV-based exam model coordinate collector...")
    print("Using reference image: Arabic@4x-20.jpg")
    
    collector = OpenCVBubbleCollector("Arabic@4x-20.jpg")
    exam_model_key = collector.run()
    
    if exam_model_key:
        print(f"\n🎉 Success! Test the new positions with:")
        print(f"python compare_bubbles.py \"scan_output copy.png\" --exam_model_key {exam_model_key}")
        print(f"python compare_bubbles.py \"Arabic@4x-20.jpg\" --exam_model_key {exam_model_key}")
    else:
        print("No coordinates were saved.") 