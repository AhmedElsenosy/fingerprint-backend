#!/usr/bin/env python3

import cv2
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import json
import os
from bubble_edge_detector import detect_aruco_markers

class BubblePositionCollector:
    def __init__(self, image_path):
        self.image_path = image_path
        self.image = cv2.imread(image_path)
        # Convert BGR to RGB for matplotlib
        self.image_rgb = cv2.cvtColor(self.image, cv2.COLOR_BGR2RGB)
        self.clicked_positions = []
        self.letters = ['A', 'B', 'C']
        self.current_bubble = 0
        
        # Detect ArUco markers for reference
        self.markers = detect_aruco_markers(self.image)
        
        print("Instructions:")
        print("- Click on the center of each exam model bubble")
        print("- Click A, then B, then C (in order)")
        print("- Close the window when done")
        print("\nClick on bubble A first...")
        
        # Set up the plot
        self.fig, self.ax = plt.subplots(1, 1, figsize=(12, 16))
        self.ax.imshow(self.image_rgb)
        self.ax.set_title('Click on Exam Model Bubbles (A, B, C in order)', fontsize=14)
        
        # Draw ArUco markers
        self.draw_aruco_markers()
        
        # Connect click event
        self.fig.canvas.mpl_connect('button_press_event', self.on_click)
        
        # Add instruction text
        self.instruction_text = self.ax.text(50, 50, 'Click on bubble A', 
                                           bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow"),
                                           fontsize=12, fontweight='bold')
    
    def draw_aruco_markers(self):
        """Draw ArUco markers on the plot for reference."""
        colors = ['red', 'green', 'blue', 'orange']
        for i, marker in enumerate(self.markers):
            center = marker['center']
            # Draw marker center
            circle = patches.Circle(center, radius=15, linewidth=3, 
                                  edgecolor=colors[i % len(colors)], facecolor='none')
            self.ax.add_patch(circle)
            
            # Add marker ID label
            self.ax.text(center[0] + 25, center[1], f"ID:{marker['id']}", 
                        fontsize=10, fontweight='bold', 
                        color=colors[i % len(colors)],
                        bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.8))
    
    def on_click(self, event):
        if event.inaxes != self.ax:
            return
        
        if self.current_bubble < len(self.letters):
            x, y = int(event.xdata), int(event.ydata)
            
            # Record the click position
            self.clicked_positions.append({
                'letter': self.letters[self.current_bubble],
                'center': [x, y]
            })
            
            # Draw the clicked position
            colors = ['red', 'lime', 'blue']
            color = colors[self.current_bubble]
            
            # Draw bubble circle
            circle = patches.Circle((x, y), radius=20, linewidth=4, 
                                  edgecolor=color, facecolor='none')
            self.ax.add_patch(circle)
            
            # Add letter label
            self.ax.text(x-10, y+8, self.letters[self.current_bubble], 
                        fontsize=14, fontweight='bold', color=color,
                        bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.9))
            
            print(f"Bubble {self.letters[self.current_bubble]} recorded at: ({x}, {y})")
            
            self.current_bubble += 1
            
            if self.current_bubble < len(self.letters):
                self.instruction_text.set_text(f'Click on bubble {self.letters[self.current_bubble]}')
                print(f"Now click on bubble {self.letters[self.current_bubble]}...")
            else:
                self.instruction_text.set_text('All bubbles recorded! Close window to save.')
                print("All bubbles recorded! Close the window to save.")
            
            # Refresh the plot
            self.fig.canvas.draw()
        
        if self.current_bubble >= len(self.letters):
            # Show results after a short delay
            plt.pause(1)
            self.save_to_exam_models_file()
    
    def save_to_exam_models_file(self):
        """Save the clicked positions to exam_models.json in the correct format."""
        if len(self.clicked_positions) != 3:
            print(f"Error: Need exactly 3 positions, got {len(self.clicked_positions)}")
            return
        
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
            'collection_method': 'matplotlib_click',
            'timestamp': 'updated_positioning'
        }
        
        # Load existing exam_models.json or create new one
        exam_models_file = 'exam_models.json'
        if os.path.exists(exam_models_file):
            with open(exam_models_file, 'r') as f:
                exam_models = json.load(f)
        else:
            exam_models = {}
        
        # Update with new exam model data
        exam_model_key = 'exam_model_updated'
        exam_models[exam_model_key] = exam_model_data
        
        # Save to file
        with open(exam_models_file, 'w') as f:
            json.dump(exam_models, f, indent=2)
        
        print(f"\nExam model data saved to: {exam_models_file}")
        print(f"Exam model key: {exam_model_key}")
        
        print("\nTo test the new positions, run:")
        print(f"python compare_bubbles.py \"your_image.png\" --exam_model_key {exam_model_key}")
        
        # Create a results visualization
        self.show_results()
        
        return exam_model_key
    
    def show_results(self):
        """Show a results visualization."""
        # Create new figure for results
        fig2, ax2 = plt.subplots(1, 1, figsize=(10, 8))
        
        # Show cropped region around the exam model bubbles
        if self.clicked_positions:
            # Find bounding box around clicked positions
            xs = [pos['center'][0] for pos in self.clicked_positions]
            ys = [pos['center'][1] for pos in self.clicked_positions]
            
            min_x, max_x = min(xs) - 100, max(xs) + 100
            min_y, max_y = min(ys) - 50, max(ys) + 50
            
            # Ensure bounds are within image
            min_x = max(0, min_x)
            min_y = max(0, min_y)
            max_x = min(self.image_rgb.shape[1], max_x)
            max_y = min(self.image_rgb.shape[0], max_y)
            
            # Crop and display
            cropped = self.image_rgb[min_y:max_y, min_x:max_x]
            ax2.imshow(cropped)
            
            # Draw bubbles on cropped image
            colors = ['red', 'lime', 'blue']
            for i, pos in enumerate(self.clicked_positions):
                x_crop = pos['center'][0] - min_x
                y_crop = pos['center'][1] - min_y
                
                circle = patches.Circle((x_crop, y_crop), radius=20, linewidth=4, 
                                      edgecolor=colors[i], facecolor='none')
                ax2.add_patch(circle)
                
                ax2.text(x_crop-10, y_crop+8, pos['letter'], 
                        fontsize=16, fontweight='bold', color=colors[i],
                        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.9))
            
            ax2.set_title('Exam Model Bubbles - Saved to exam_models.json', fontsize=14, fontweight='bold')
            ax2.set_xlabel('Ready to test with compare_bubbles.py!', fontsize=12)
        
        plt.tight_layout()
        plt.show()
    
    def run(self):
        """Run the interactive position collector."""
        plt.tight_layout()
        plt.show()
        
        # After window closes, process results
        if len(self.clicked_positions) == 3:
            return self.save_to_exam_models_file()
        else:
            print(f"Warning: Only {len(self.clicked_positions)} positions were recorded.")
            return None

if __name__ == "__main__":
    # Use the reference image instead of scanned image for coordinate collection
    collector = BubblePositionCollector("Arabic@4x-20.jpg")
    exam_model_key = collector.run()
    
    if exam_model_key:
        print(f"\n🎉 Success! Test the new positions with:")
        print(f"python compare_bubbles.py \"scan_output copy.png\" --exam_model_key {exam_model_key}")
        print(f"python compare_bubbles.py \"Arabic@4x-20.jpg\" --exam_model_key {exam_model_key}") 