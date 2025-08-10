#!/usr/bin/env python3
import cv2
import numpy as np
import json
import os
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.widgets import Button
from bubble_edge_detector import detect_aruco_markers, detect_bubble_fallback

class ExamModelCollectorMatplotlib:
    def __init__(self, image_path):
        self.image_path = image_path
        self.original_image = None
        self.aruco_corners = None
        self.aruco_ids = None
        self.click_positions = []
        self.detected_bubbles = []
        self.fig = None
        self.ax = None
        self.max_clicks = 3
        
    def load_and_prepare_image(self):
        """Load image and detect ArUco markers for alignment."""
        self.original_image = cv2.imread(self.image_path)
        if self.original_image is None:
            raise ValueError(f"Could not load image: {self.image_path}")
        
        # Convert BGR to RGB for matplotlib
        self.original_image = cv2.cvtColor(self.original_image, cv2.COLOR_BGR2RGB)
        
        print(f"Loaded image: {self.original_image.shape}")
        
        # Detect ArUco markers
        # Convert back to BGR for ArUco detection
        bgr_image = cv2.cvtColor(self.original_image, cv2.COLOR_RGB2BGR)
        markers = detect_aruco_markers(bgr_image)
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
        
        return True
    
    def detect_contours_near_point(self, point, radius=30):
        """Detect bubble contours near a clicked point."""
        x, y = int(point[0]), int(point[1])
        
        # Convert back to BGR for processing
        bgr_image = cv2.cvtColor(self.original_image, cv2.COLOR_RGB2BGR)
        
        # Extract ROI around the point
        roi_x1 = max(0, x - radius)
        roi_y1 = max(0, y - radius) 
        roi_x2 = min(bgr_image.shape[1], x + radius)
        roi_y2 = min(bgr_image.shape[0], y + radius)
        
        roi = bgr_image[roi_y1:roi_y2, roi_x1:roi_x2]
        
        if roi.size == 0:
            return None
            
        # Convert to grayscale
        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        
        try:
            # Use existing bubble detection function
            best_contour, circularity = detect_bubble_fallback(roi_gray, target_area=200)
            
            if best_contour is not None:
                # Adjust contour coordinates back to original image space
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
        
        # If no bubble detected, use clicked coordinates
        return {
            'center': (x, y),
            'contour': None,
            'circularity': 0.0,
            'area': 0
        }
    
    def on_click(self, event):
        """Handle mouse clicks to collect bubble positions."""
        if event.inaxes != self.ax or len(self.click_positions) >= self.max_clicks:
            return
        
        if event.button == 1:  # Left click
            x, y = event.xdata, event.ydata
            if x is None or y is None:
                return
                
            # Store click position
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
            if len(self.detected_bubbles) == self.max_clicks:
                print(f"\nCollected {self.max_clicks} bubbles! Click 'Save' button to save or 'Reset' to restart.")
    
    def update_display(self):
        """Update the display with current click positions and detected bubbles."""
        # Clear previous annotations
        self.ax.clear()
        
        # Show the image
        self.ax.imshow(self.original_image)
        
        # Draw ArUco markers
        if self.aruco_corners and self.aruco_ids:
            for i, corners in enumerate(self.aruco_corners):
                corners = np.array(corners)
                # Draw marker outline
                rect = patches.Polygon(corners, linewidth=2, edgecolor='yellow', facecolor='none')
                self.ax.add_patch(rect)
                
                # Draw marker ID
                center = np.mean(corners, axis=0)
                self.ax.text(center[0], center[1], str(self.aruco_ids[i]), 
                           color='yellow', fontsize=12, ha='center', va='center',
                           bbox=dict(boxstyle="round,pad=0.3", facecolor='black', alpha=0.7))
        
        # Draw click positions and detected bubbles
        for i, ((click_x, click_y), bubble) in enumerate(zip(self.click_positions, self.detected_bubbles)):
            # Draw click position (small red circle)
            self.ax.plot(click_x, click_y, 'ro', markersize=5)
            
            # Draw detected bubble center (larger green circle)
            center_x, center_y = bubble['center']
            self.ax.plot(center_x, center_y, 'go', markersize=10, markerfacecolor='none', markeredgewidth=2)
            
            # Draw contour if detected
            if bubble['contour'] is not None:
                contour_points = bubble['contour'].squeeze()
                self.ax.plot(contour_points[:, 0], contour_points[:, 1], 'b-', linewidth=2)
            
            # Label the bubble
            label = f"Model {chr(65 + i)}"
            self.ax.text(center_x + 20, center_y - 20, label, 
                        color='white', fontsize=10, fontweight='bold',
                        bbox=dict(boxstyle="round,pad=0.3", facecolor='black', alpha=0.7))
        
        # Set title with instructions
        title = f"Clicks: {len(self.click_positions)}/{self.max_clicks} - Click on exam model bubbles A, B, C"
        self.ax.set_title(title, fontsize=12, fontweight='bold')
        
        # Remove axis ticks and labels
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        
        # Refresh the plot
        self.fig.canvas.draw()
    
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
        if len(self.detected_bubbles) != self.max_clicks:
            print(f"Error: Need exactly {self.max_clicks} bubbles to save")
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
        # Convert back to BGR for OpenCV operations
        vis_image = cv2.cvtColor(self.original_image, cv2.COLOR_RGB2BGR)
        
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
    
    def on_save(self, event):
        """Handle save button click."""
        if self.save_exam_model_data():
            print("Model saved successfully!")
            plt.close(self.fig)
        else:
            print("Failed to save model.")
    
    def on_reset(self, event):
        """Handle reset button click."""
        self.click_positions = []
        self.detected_bubbles = []
        print("Reset collection. Click 3 new bubble positions.")
        self.update_display()
    
    def run(self):
        """Main loop for collecting exam model bubbles."""
        try:
            if not self.load_and_prepare_image():
                return False
            
            # Create matplotlib figure
            self.fig, self.ax = plt.subplots(figsize=(12, 8))
            
            # Connect click event
            self.fig.canvas.mpl_connect('button_press_event', self.on_click)
            
            # Add buttons
            ax_save = plt.axes([0.85, 0.02, 0.1, 0.04])
            ax_reset = plt.axes([0.74, 0.02, 0.1, 0.04])
            
            btn_save = Button(ax_save, 'Save')
            btn_reset = Button(ax_reset, 'Reset')
            
            btn_save.on_clicked(self.on_save)
            btn_reset.on_clicked(self.on_reset)
            
            print(f"\nExam Model Bubble Collector")
            print(f"===========================")
            print(f"Image: {self.image_path}")
            print(f"Instructions:")
            print(f"1. Click on the center of 3 exam model bubbles (A, B, C)")
            print(f"2. Click 'Save' button after collecting 3 bubbles")
            print(f"3. Click 'Reset' button to restart collection")
            print(f"4. Close window to quit")
            print(f"5. ArUco markers are shown in yellow")
            
            # Initial display
            self.update_display()
            
            # Show the plot
            plt.tight_layout()
            plt.show()
            
            return True
        
        except Exception as e:
            print(f"Error in run(): {e}")
            return False

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Collect exam model bubble coordinates by clicking (matplotlib version)')
    parser.add_argument('image_path', help='Path to the image with exam model bubbles')
    parser.add_argument('--output', default='exam_models.json', 
                       help='Output JSON file (default: exam_models.json)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.image_path):
        print(f"Error: Image file '{args.image_path}' not found")
        return 1
    
    try:
        collector = ExamModelCollectorMatplotlib(args.image_path)
        success = collector.run()
        return 0 if success else 1
    except Exception as e:
        print(f"Error: {str(e)}")
        print("\nIf you continue to have display issues, you can use the manual coordinate version:")
        print(f"python collect_exam_model_manual.py {args.image_path} \"x1,y1 x2,y2 x3,y3\"")
        return 1

if __name__ == "__main__":
    exit(main()) 