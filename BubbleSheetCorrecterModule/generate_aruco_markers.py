import cv2
import numpy as np

def generate_aruco_markers():
    """Generate ArUco markers for the corners of the page."""
    # Create ArUco dictionary
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    
    # Parameters for marker generation
    marker_size = 80  # Size of each marker in pixels
    marker_ids = [0, 1, 2, 3]  # IDs for the four corners
    padding = 20  # Padding around markers
    
    # Create a white A4 page (2480 x 3508 pixels at 300 DPI)
    page_width = 2480
    page_height = 3508
    page = np.full((page_height, page_width), 255, dtype=np.uint8)
    
    # Generate and place markers
    for i, marker_id in enumerate(marker_ids):
        # Generate marker
        marker = np.zeros((marker_size, marker_size), dtype=np.uint8)
        cv2.aruco.generateImageMarker(aruco_dict, marker_id, marker_size, marker, 1)
        
        # Calculate position
        if i == 0:  # Top-left
            x, y = padding, padding
        elif i == 1:  # Top-right
            x, y = page_width - marker_size - padding, padding
        elif i == 2:  # Bottom-left
            x, y = padding, page_height - marker_size - padding
        else:  # Bottom-right
            x, y = page_width - marker_size - padding, page_height - marker_size - padding
        
        # Place marker on page
        page[y:y+marker_size, x:x+marker_size] = marker
    
    # Save the page with markers
    cv2.imwrite('aruco_markers.jpg', page)
    print("ArUco markers saved as aruco_markers.jpg")
    
    # Generate individual markers for testing
    for marker_id in marker_ids:
        marker = np.zeros((marker_size, marker_size), dtype=np.uint8)
        cv2.aruco.generateImageMarker(aruco_dict, marker_id, marker_size, marker, 1)
        cv2.imwrite(f'aruco_marker_{marker_id}.jpg', marker)
        print(f"Marker {marker_id} saved as aruco_marker_{marker_id}.jpg")

if __name__ == "__main__":
    generate_aruco_markers() 