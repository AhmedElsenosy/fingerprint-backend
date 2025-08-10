import cv2
import numpy as np

def place_markers_on_image(image_path):
    """Place ArUco markers on the corners of the given image."""
    # Read the input image
    image = cv2.imread(image_path)
    if image is None:
        print(f"Could not read image: {image_path}")
        return
    
    # Create ArUco dictionary
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    
    # Parameters for marker generation
    marker_size = 50  # Reduced from 80 to 50 pixels
    marker_ids = [0, 1, 2, 3]  # IDs for the four corners
    padding = 10  # Reduced padding from 20 to 10 pixels
    
    # Get image dimensions
    height, width = image.shape[:2]
    print(f"Image dimensions: {width}x{height}")
    
    # Generate and place markers
    for i, marker_id in enumerate(marker_ids):
        # Generate marker
        marker = np.zeros((marker_size, marker_size), dtype=np.uint8)
        cv2.aruco.generateImageMarker(aruco_dict, marker_id, marker_size, marker, 1)
        
        # Create white background with black marker
        marker_bgr = np.full((marker_size, marker_size, 3), 255, dtype=np.uint8)
        for c in range(3):  # Apply to each color channel
            marker_bgr[:, :, c] = np.where(marker == 0, 0, 255)
        
        # Calculate position
        if i == 0:  # Top-left
            x, y = padding, padding
        elif i == 1:  # Top-right
            x, y = width - marker_size - padding, padding
        elif i == 2:  # Bottom-left
            x, y = padding, height - marker_size - padding
        else:  # Bottom-right
            x, y = width - marker_size - padding, height - marker_size - padding
        
        # Place marker on image
        image[y:y+marker_size, x:x+marker_size] = marker_bgr
    
    # Save the result
    output_path = 'trial7_with_markers.jpg'
    cv2.imwrite(output_path, image)
    print(f"Image with markers saved as {output_path}")

if __name__ == "__main__":
    place_markers_on_image('trial7.jpeg') 