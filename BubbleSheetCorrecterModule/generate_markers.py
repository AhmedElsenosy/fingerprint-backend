import cv2
import numpy as np

def generate_tag_image(tag_id, size):
    """Generate a simple tag pattern."""
    # Create a blank image
    tag_img = np.ones((size, size), dtype=np.uint8) * 255
    
    # Draw a border
    border = size // 8
    cv2.rectangle(tag_img, (border, border), (size-border, size-border), 0, 2)
    
    # Draw tag ID as binary pattern
    cell_size = (size - 2*border) // 4
    binary = format(tag_id, '04b')  # Convert to 4-bit binary
    
    for i, bit in enumerate(binary):
        if bit == '1':
            x = border + (i % 2) * 2 * cell_size
            y = border + (i // 2) * 2 * cell_size
            cv2.rectangle(tag_img, (x, y), (x+cell_size, y+cell_size), 0, -1)
    
    return tag_img

def add_markers_to_image():
    # Read the existing image
    try:
        image = cv2.imread('trial7.jpeg')
        if image is None:
            raise Exception("Could not read trial7.jpeg")
    except Exception as e:
        print(f"Error reading image: {str(e)}")
        return
    
    # Get image dimensions
    height, width = image.shape[:2]
    print(f"Image dimensions: {width}x{height}")
    
    # Generate markers
    marker_size = 80  # Smaller markers
    padding = 20  # Smaller padding from edges
    
    # Generate and place markers in corners
    # Top-left
    marker = generate_tag_image(0, marker_size)
    image[padding:padding+marker_size, padding:padding+marker_size] = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
    
    # Top-right
    marker = generate_tag_image(1, marker_size)
    image[padding:padding+marker_size, width-padding-marker_size:width-padding] = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
    
    # Bottom-left
    marker = generate_tag_image(2, marker_size)
    image[height-padding-marker_size:height-padding, padding:padding+marker_size] = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
    
    # Bottom-right
    marker = generate_tag_image(3, marker_size)
    image[height-padding-marker_size:height-padding, width-padding-marker_size:width-padding] = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
    
    # Save the image with a new name to preserve the original
    output_path = 'trial7_with_markers.jpg'
    cv2.imwrite(output_path, image)
    print(f"Image with markers saved as {output_path}")

if __name__ == "__main__":
    add_markers_to_image() 