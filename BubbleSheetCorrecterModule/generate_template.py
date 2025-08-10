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

def generate_template(output_path='template.jpg', width=1000, height=1400):
    # Create a white image
    template = np.ones((height, width, 3), dtype=np.uint8) * 255
    
    # Generate markers
    marker_size = 64
    
    # Generate marker for exam model section (new)
    exam_model_marker = generate_tag_image(5, marker_size)  # ID 5
    
    # Generate markers for question sections
    question_markers = []
    for i in range(4):
        marker = generate_tag_image(i, marker_size)
        question_markers.append(marker)
    
    # Generate marker for ID section (bottom)
    id_marker = generate_tag_image(4, marker_size)
    
    # Place exam model section marker and bubbles (top section)
    exam_model_x = width // 2 - marker_size // 2
    exam_model_y = 30  # Very top of the page
    template[exam_model_y:exam_model_y+marker_size, exam_model_x:exam_model_x+marker_size] = cv2.cvtColor(exam_model_marker, cv2.COLOR_GRAY2BGR)
    
    # Draw exam model bubbles section
    exam_model_section_width = int(width * 0.6)
    exam_model_section_height = 80
    exam_model_section_x = width // 2 - exam_model_section_width // 2
    exam_model_section_y = exam_model_y + marker_size + 10
    
    cv2.rectangle(template,
                 (exam_model_section_x, exam_model_section_y),
                 (exam_model_section_x + exam_model_section_width, exam_model_section_y + exam_model_section_height),
                 (0, 0, 0), 2)
    
    # Draw exam model bubbles (horizontal layout: Model A, B, C, D, E)
    bubble_size = 20
    num_models = 5
    bubble_spacing = exam_model_section_width // (num_models + 1)
    
    for i in range(num_models):
        center_x = exam_model_section_x + (i + 1) * bubble_spacing
        center_y = exam_model_section_y + exam_model_section_height // 2
        cv2.circle(template, (center_x, center_y), bubble_size // 2, (0, 0, 0), 2)
        
        # Add model labels
        model_label = chr(65 + i)  # A, B, C, D, E
        cv2.putText(template, f"Model {model_label}", (center_x - 25, center_y + 35),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    
    # Calculate positions for question section markers (moved down)
    question_start_y = exam_model_section_y + exam_model_section_height + 40
    section_width = width // 4
    for i in range(4):
        x = i * section_width + (section_width - marker_size) // 2
        y = question_start_y  # Start below exam model section
        template[y:y+marker_size, x:x+marker_size] = cv2.cvtColor(question_markers[i], cv2.COLOR_GRAY2BGR)
        
        # Draw question bubbles
        bubble_start_y = y + marker_size + 20
        bubble_height = height * 0.4  # Reduced height to make room
        cv2.rectangle(template, 
                     (x, bubble_start_y), 
                     (x + section_width - 10, int(bubble_start_y + bubble_height)),
                     (0, 0, 0), 2)
        
        # Draw bubbles
        bubble_size = 20
        bubbles_per_col = 25
        bubble_spacing = int(bubble_height / bubbles_per_col)
        
        for row in range(bubbles_per_col):
            center_y = bubble_start_y + row * bubble_spacing + bubble_spacing // 2
            center_x = x + section_width // 2
            cv2.circle(template, (center_x, center_y), bubble_size // 2, (0, 0, 0), 1)
    
    # Place ID section marker (moved down slightly)
    id_x = width // 2 - marker_size // 2
    id_y = int(height * 0.75)  # Moved down slightly
    template[id_y:id_y+marker_size, id_x:id_x+marker_size] = cv2.cvtColor(id_marker, cv2.COLOR_GRAY2BGR)
    
    # Draw ID bubbles section
    id_section_width = int(width * 0.3)
    id_section_height = int(height * 0.15)  # Reduced height
    id_section_x = width // 2 - id_section_width // 2
    id_section_y = id_y + marker_size + 20
    
    cv2.rectangle(template,
                 (id_section_x, id_section_y),
                 (id_section_x + id_section_width, id_section_y + id_section_height),
                 (0, 0, 0), 2)
    
    # Draw ID bubbles (10x10 grid)
    bubble_size = 15
    rows, cols = 10, 10
    cell_width = id_section_width // cols
    cell_height = id_section_height // rows
    
    for row in range(rows):
        for col in range(cols):
            center_x = id_section_x + col * cell_width + cell_width // 2
            center_y = id_section_y + row * cell_height + cell_height // 2
            cv2.circle(template, (center_x, center_y), bubble_size // 2, (0, 0, 0), 1)
    
    # Add labels and instructions
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(template, 'Bubble Sheet', (width//2 - 100, 20), font, 1, (0, 0, 0), 2)
    cv2.putText(template, 'Exam Model', (width//2 - 50, exam_model_y - 10), font, 0.8, (0, 0, 0), 2)
    cv2.putText(template, 'ID Number', (width//2 - 50, id_y - 10), font, 0.8, (0, 0, 0), 2)
    
    # Save the template
    cv2.imwrite(output_path, template)
    print(f"Template saved as {output_path}")

if __name__ == "__main__":
    generate_template() 