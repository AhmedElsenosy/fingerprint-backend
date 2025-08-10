import cv2
import numpy as np

def detect_markers_and_bubbles(image):
    """Detect ArUco markers and bubbles in the image."""
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
        
    # Load the predefined dictionary
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    parameters = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)
    
    # Detect markers
    corners, ids, rejected = detector.detectMarkers(gray)
    
    # Draw detected markers
    debug_img = image.copy()
    if ids is not None:
        cv2.aruco.drawDetectedMarkers(debug_img, corners, ids)
        print(f"Detected {len(ids)} markers with IDs: {ids.flatten()}")
    else:
        print("No markers detected")
        return debug_img, [], []
    
    # Detect bubbles in the region defined by markers
    if len(corners) >= 4:
        # Get the corners of all markers
        all_corners = np.concatenate(corners)
        
        # Find the bounding box that contains all markers
        min_x = int(np.min(all_corners[:, :, 0]))
        min_y = int(np.min(all_corners[:, :, 1]))
        max_x = int(np.max(all_corners[:, :, 0]))
        max_y = int(np.max(all_corners[:, :, 1]))
        
        # Define the bubble detection region
        bubble_region = (min_x, min_y, max_x - min_x, max_y - min_y)
        
        # Detect bubbles
        bubbles = detect_bubbles(gray, bubble_region)
        
        # Draw bubble region and detected bubbles
        x, y, w, h = bubble_region
        cv2.rectangle(debug_img, (x, y), (x+w, y+h), (255, 0, 0), 1)
        for bx, by, bw, bh in bubbles:
            cv2.rectangle(debug_img, (bx, by), (bx+bw, by+bh), (0, 255, 255), 1)
        
        return debug_img, corners, bubbles
    
    return debug_img, corners, []

def detect_bubbles(image, region):
    """Detect bubbles in the given region."""
    # Extract region
    x, y, w, h = region
    roi = image[y:y+h, x:x+w]
    
    # Threshold
    _, thresh = cv2.threshold(roi, 127, 255, cv2.THRESH_BINARY_INV)
    
    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Filter circular contours
    bubbles = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 50:  # Skip tiny contours
            continue
            
        # Calculate circularity
        perimeter = cv2.arcLength(cnt, True)
        circularity = 4 * np.pi * area / (perimeter * perimeter) if perimeter > 0 else 0
        
        if circularity > 0.7:  # Threshold for circular shapes
            x_b, y_b, w_b, h_b = cv2.boundingRect(cnt)
            bubbles.append((x + x_b, y + y_b, w_b, h_b))
    
    return bubbles

def test_detection():
    # Read the image
    image = cv2.imread('trial7_with_markers.jpg')
    if image is None:
        print("Could not read image")
        return
    
    # Get image dimensions
    height, width = image.shape[:2]
    print(f"Image dimensions: {width}x{height}")
    
    # Detect markers and bubbles
    debug_img, corners, bubbles = detect_markers_and_bubbles(image)
    
    if len(corners) > 0:
        print(f"Detected {len(corners)} markers")
    else:
        print("No markers detected")
    
    print(f"Detected {len(bubbles)} bubbles")
    
    # Save debug image
    cv2.imwrite('detection_test.jpg', debug_img)
    print("Debug image saved as detection_test.jpg")

if __name__ == "__main__":
    test_detection() 