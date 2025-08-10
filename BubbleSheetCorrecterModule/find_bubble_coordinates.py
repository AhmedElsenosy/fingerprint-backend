#!/usr/bin/env python3
"""
Helper script to find bubble coordinates by displaying the image
and printing coordinates when you click on it.
"""

import cv2
import numpy as np
from bubble_edge_detector import detect_aruco_markers

class CoordinateFinder:
    def __init__(self, image_path):
        self.image_path = image_path
        self.image = None
        self.display_image = None
        self.coordinates = []
        self.window_name = "Click on Exam Model Bubbles (A, B, C)"
        
    def load_image(self):
        """Load the image and prepare for display."""
        self.image = cv2.imread(self.image_path)
        if self.image is None:
            raise ValueError(f"Could not load image: {self.image_path}")
        
        print(f"Image loaded: {self.image.shape}")
        
        # Resize for display if too large
        max_width = 1200
        if self.image.shape[1] > max_width:
            scale = max_width / self.image.shape[1]
            new_width = int(self.image.shape[1] * scale)
            new_height = int(self.image.shape[0] * scale)
            self.display_image = cv2.resize(self.image, (new_width, new_height))
            self.scale_factor = scale
            print(f"Resized for display: {self.display_image.shape} (scale: {scale:.3f})")
        else:
            self.display_image = self.image.copy()
            self.scale_factor = 1.0
        
        # Detect and draw ArUco markers
        try:
            markers = detect_aruco_markers(self.image)
            if markers:
                print(f"Detected {len(markers)} ArUco markers")
                for marker in markers:
                    corners = np.array(marker['corners'], dtype=np.int32)
                    # Scale corners for display
                    corners = (corners * self.scale_factor).astype(np.int32)
                    cv2.polylines(self.display_image, [corners], True, (0, 255, 255), 2)
                    
                    # Draw marker ID
                    center = np.mean(corners, axis=0).astype(int)
                    cv2.putText(self.display_image, str(marker['id']), tuple(center),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        except Exception as e:
            print(f"Could not detect ArUco markers: {e}")
        
        return True
    
    def mouse_callback(self, event, x, y, flags, param):
        """Handle mouse clicks to record coordinates."""
        if event == cv2.EVENT_LBUTTONDOWN and len(self.coordinates) < 3:
            # Scale coordinates back to original image size
            orig_x = int(x / self.scale_factor)
            orig_y = int(y / self.scale_factor)
            
            self.coordinates.append((orig_x, orig_y))
            
            print(f"Bubble {len(self.coordinates)}: ({orig_x}, {orig_y})")
            
            # Draw on display image
            cv2.circle(self.display_image, (x, y), 8, (0, 0, 255), -1)
            cv2.putText(self.display_image, f"Model {chr(64 + len(self.coordinates))}", 
                       (x + 15, y - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(self.display_image, f"Model {chr(64 + len(self.coordinates))}", 
                       (x + 15, y - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
            
            self.update_display()
            
            if len(self.coordinates) == 3:
                self.print_command()
    
    def update_display(self):
        """Update the display with instructions."""
        display = self.display_image.copy()
        
        # Add instructions
        instructions = [
            f"Coordinates: {len(self.coordinates)}/3",
            "Click on exam model bubbles A, B, C",
            "Press 'r' to reset, 'q' to quit"
        ]
        
        for i, instruction in enumerate(instructions):
            y_pos = 30 + i * 25
            cv2.putText(display, instruction, (10, y_pos),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(display, instruction, (10, y_pos),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
        
        cv2.imshow(self.window_name, display)
    
    def print_command(self):
        """Print the command to run with collected coordinates."""
        if len(self.coordinates) == 3:
            coord_str = " ".join([f"{x},{y}" for x, y in self.coordinates])
            print("\n" + "="*50)
            print("COORDINATES COLLECTED!")
            print("="*50)
            print(f"Run this command to collect the exam model:")
            print(f'python collect_exam_model_manual.py "{self.image_path}" "{coord_str}"')
            print("="*50)
    
    def reset(self):
        """Reset coordinates and reload display."""
        self.coordinates = []
        self.display_image = self.image.copy()
        if self.scale_factor != 1.0:
            new_width = int(self.image.shape[1] * self.scale_factor)
            new_height = int(self.image.shape[0] * self.scale_factor)
            self.display_image = cv2.resize(self.display_image, (new_width, new_height))
        
        # Redraw ArUco markers
        try:
            markers = detect_aruco_markers(self.image)
            if markers:
                for marker in markers:
                    corners = np.array(marker['corners'], dtype=np.int32)
                    corners = (corners * self.scale_factor).astype(np.int32)
                    cv2.polylines(self.display_image, [corners], True, (0, 255, 255), 2)
                    
                    center = np.mean(corners, axis=0).astype(int)
                    cv2.putText(self.display_image, str(marker['id']), tuple(center),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        except:
            pass
        
        print("Reset coordinates. Click 3 new positions.")
        self.update_display()
    
    def run(self):
        """Main loop for coordinate finding."""
        if not self.load_image():
            return False
        
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(self.window_name, self.mouse_callback)
        
        print(f"\nExam Model Coordinate Finder")
        print(f"============================")
        print(f"Image: {self.image_path}")
        print(f"Instructions:")
        print(f"1. Click on the center of 3 exam model bubbles (A, B, C)")
        print(f"2. The command to run will be displayed after 3 clicks")
        print(f"3. Press 'r' to reset, 'q' to quit")
        print(f"4. ArUco markers are shown in yellow")
        
        self.update_display()
        
        while True:
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                print("Quit.")
                break
            elif key == ord('r'):
                self.reset()
        
        cv2.destroyAllWindows()
        return True

def main():
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python find_bubble_coordinates.py <image_path>")
        print("Example: python find_bubble_coordinates.py Arabic@4x-20.jpg")
        return 1
    
    image_path = sys.argv[1]
    
    try:
        finder = CoordinateFinder(image_path)
        finder.run()
        return 0
    except Exception as e:
        print(f"Error: {str(e)}")
        print("\nIf you get a segmentation fault or display error,")
        print("you can manually estimate coordinates and use:")
        print(f'python collect_exam_model_manual.py "{image_path}" "x1,y1 x2,y2 x3,y3"')
        return 1

if __name__ == "__main__":
    exit(main()) 