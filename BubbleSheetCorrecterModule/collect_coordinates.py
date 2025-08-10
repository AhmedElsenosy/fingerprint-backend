import cv2
import numpy as np

# Global variables to store coordinates and current state
bubble_coordinates = []
current_question = 1
window_name = "Collect Bubble Coordinates"

def mouse_callback(event, x, y, flags, param):
    global bubble_coordinates, current_question
    
    if event == cv2.EVENT_LBUTTONDOWN:
        # Store the coordinate
        bubble_coordinates.append((x, y))
        
        # Calculate which bubble in the question this is (1-5)
        bubble_in_question = len(bubble_coordinates) % 5
        if bubble_in_question == 0:
            bubble_in_question = 5
        
        # Draw a circle and number at the clicked position
        img_copy = image.copy()
        
        # Draw all previous points
        for idx, (px, py) in enumerate(bubble_coordinates):
            q_num = (idx // 5) + 1
            b_num = (idx % 5) + 1
            cv2.circle(img_copy, (px, py), 5, (0, 255, 0), -1)
            cv2.putText(img_copy, f"Q{q_num}B{b_num}", (px + 10, py),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        cv2.imshow(window_name, img_copy)
        
        # Print information
        print(f"Recorded coordinate for Question {current_question}, Bubble {bubble_in_question}: ({x}, {y})")
        
        # Update question number if we've collected all 5 bubbles for this question
        if bubble_in_question == 5:
            current_question += 1
            print(f"\nMoving to Question {current_question}")
            
            # If we've collected all 100 questions (500 bubbles), save and exit
            if current_question > 100:
                print("\nAll 100 questions completed!")
                save_coordinates()
                cv2.destroyAllWindows()

def save_coordinates():
    """Save the collected coordinates to a file."""
    with open('bubble_coordinates.txt', 'w') as f:
        for idx, (x, y) in enumerate(bubble_coordinates):
            question = (idx // 5) + 1
            bubble = (idx % 5) + 1
            f.write(f"Q{question}B{bubble},{x},{y}\n")
    print(f"\nCoordinates saved to bubble_coordinates.txt")

# Load the image
image = cv2.imread('trial7_with_markers.jpg')
if image is None:
    print("Error: Could not load image")
    exit()

# Create window and set mouse callback
cv2.namedWindow(window_name)
cv2.setMouseCallback(window_name, mouse_callback)

# Display instructions
print("\nInstructions:")
print("1. Click in the center of each bubble")
print("2. For each question, click all 5 bubbles from top to bottom")
print("3. The green dots and labels will show your clicks")
print("4. Press 'q' to quit at any time")
print("\nStarting with Question 1...")

# Show the image
while True:
    # Show the image with any existing marks
    img_copy = image.copy()
    for idx, (px, py) in enumerate(bubble_coordinates):
        q_num = (idx // 5) + 1
        b_num = (idx % 5) + 1
        cv2.circle(img_copy, (px, py), 5, (0, 255, 0), -1)
        cv2.putText(img_copy, f"Q{q_num}B{b_num}", (px + 10, py),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    
    cv2.imshow(window_name, img_copy)
    
    # Check for 'q' key to quit
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        if len(bubble_coordinates) > 0:
            save_coordinates()
        break

cv2.destroyAllWindows() 