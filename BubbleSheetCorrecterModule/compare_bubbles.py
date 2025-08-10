import cv2
import numpy as np
import json
import csv
from BubbleSheetCorrecterModule.aruco_based_exam_model import calculate_exam_model_positions_from_aruco, detect_bubble_contour_at_position
from BubbleSheetCorrecterModule.bubble_edge_detector import detect_aruco_markers, compare_with_reference, detect_bubble_edges, load_coordinates
import os
from dotenv import load_dotenv
# Load environment variables from .env file
load_dotenv()

FILLING_PERCENT = int(os.getenv('FILLING_PERCENT', 50))  # Default to 50% if not set

def preprocess_image(image):
    """Apply preprocessing to optimize bubble detection."""
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # Apply adaptive histogram equalization
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    clahe_result = clahe.apply(gray)
    
    # Denoise
    denoised = cv2.fastNlMeansDenoising(clahe_result, None, 10, 7, 21)
    
    # Apply Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(denoised, (5, 5), 0)
    
    # Enhance contrast
    contrast_enhanced = cv2.convertScaleAbs(blurred, alpha=1.2, beta=0)
    
    return contrast_enhanced

def calculate_grade(bubbles_data, id_bubbles_data=None, exam_model_data=None):
    """
    Calculate grade based on filled bubbles and process ID and exam model if available.
    Assumes bubbles are organized in groups of 5 (A-E) for each question.
    Returns a dictionary with detailed grading information.
    """
    total_questions = len(bubbles_data) // 5  # 5 options per question
    answers = []
    
    # Process bubbles in groups of 5
    for q in range(total_questions):
        question_bubbles = bubbles_data[q * 5:(q + 1) * 5]
        
        # Find filled bubble (if any) for this question
        filled_bubbles = [i for i, bubble in enumerate(question_bubbles) if bubble['fill_percent'] > FILLING_PERCENT]
        
        if len(filled_bubbles) == 0:
            # No answer selected
            answer = None
        elif len(filled_bubbles) > 1:
            # Multiple answers selected
            answer = 'multiple'
        else:
            # Single answer selected
            answer = chr(65 + filled_bubbles[0])  # Convert to A, B, C, D, E
            
        answers.append({
            'question': q + 1,
            'answer': answer,
            'fill_percentages': [bubble['fill_percent'] for bubble in question_bubbles]
        })
    
    # Calculate statistics
    total_answered = sum(1 for a in answers if a['answer'] is not None and a['answer'] != 'multiple')
    multiple_answers = sum(1 for a in answers if a['answer'] == 'multiple')
    unanswered = sum(1 for a in answers if a['answer'] is None)
    
    result = {
        'total_questions': total_questions,
        'answers': answers,
        'statistics': {
            'total_answered': total_answered,
            'multiple_answers': multiple_answers,
            'unanswered': unanswered
        }
    }
    
    # Process exam model if available
    if exam_model_data:
        exam_model = None
        # Find the filled bubble for exam model (expecting 5 options A-E)
        filled_models = [i for i, model in enumerate(exam_model_data) if model['fill_percent'] > FILLING_PERCENT]
        
        if len(filled_models) == 1:
            exam_model = chr(65 + filled_models[0])  # Convert to A, B, C, D, E
        elif len(filled_models) > 1:
            exam_model = 'MULTIPLE'
        else:
            exam_model = 'BLANK'
        
        result['exam_model'] = {
            'value': exam_model,
            'fill_percentages': [model['fill_percent'] for model in exam_model_data],
            'is_valid': exam_model not in ['MULTIPLE', 'BLANK']
        }
    
    # Process ID if available
    if id_bubbles_data:
        id_number = ""
        # Only process columns 3-7 (exclude first 3 and last 2 columns)
        for col in range(3, 8):  # Changed from range(10) to range(3, 8)
            # Get bubbles for this column
            column_bubbles = [b for b in id_bubbles_data if b['column'] == col]
            column_bubbles.sort(key=lambda x: x['number'])  # Sort by number
            
            # Find filled bubble in this column
            filled_bubbles = [b for b in column_bubbles if b['fill_percent'] > FILLING_PERCENT]
            
            if len(filled_bubbles) == 1:
                id_number += str(filled_bubbles[0]['number'])
            elif len(filled_bubbles) > 1:
                id_number += 'X'  # Multiple bubbles filled
            else:
                id_number += '_'  # No bubble filled
        
        result['id'] = {
            'value': id_number,
            'is_complete': '_' not in id_number and 'X' not in id_number
        }
    
    return result

def create_visualization(image, reference_data, id_reference_data=None, exam_model_data=None, transform_matrix=None):
    """Create visualization highlighting bubbles marked in reference data."""
    vis_image = image.copy()
    overlay = np.zeros_like(image)
    alpha = 0.3
    
    # Get image dimensions
    height, width = image.shape[:2]
    
    # Count filled bubbles
    filled_count = 0
    
    # Preprocess image and apply Otsu's thresholding
    processed = preprocess_image(image)
    _, otsu = cv2.threshold(processed, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Store bubble data for grading
    bubbles_data = []
    id_bubbles_data = []
    exam_model_bubbles_data = []
    
    # Process exam model bubbles if available - using same approach as question bubbles
    if exam_model_data and 'exam_model_bubbles' in exam_model_data:
        print(f"Processing exam model using stored coordinate data...")
        
        # Check if this is ArUco-based exam model data
        is_aruco_based = any(bubble.get('aruco_based', False) for bubble in exam_model_data['exam_model_bubbles'])
        
        if is_aruco_based:
            print("Using dynamic ArUco-based positioning...")
            # Import the ArUco calculation function
            
            # Detect ArUco markers in current image
            current_aruco_markers = detect_aruco_markers(image)
            if current_aruco_markers:
                try:
                    # Calculate positions dynamically based on ArUco markers
                    exam_model_positions = calculate_exam_model_positions_from_aruco(current_aruco_markers)
                    
                    for pos in exam_model_positions:
                        center_x, center_y = pos['center']
                        
                        # Detect actual bubble contour around the calculated position
                        contour_points = detect_bubble_contour_at_position(image, center_x, center_y)
                        
                        # Ensure contour points are within image bounds
                        contour_points = np.clip(contour_points, [0, 0], [width-1, height-1])
                        
                        # Process bubble and store data
                        fill_percent = process_bubble(otsu, contour_points, vis_image, overlay)
                        exam_model_bubbles_data.append({'fill_percent': fill_percent})
                        
                        model_letter = pos['model_letter']
                
                except Exception as e:
                    print(f"Error with ArUco calculation, falling back to stored coordinates: {e}")
                    is_aruco_based = False
        
        # Fall back to stored coordinates if not ArUco-based or ArUco calculation failed
        if not is_aruco_based:
            # Get reference image dimensions for exam model coordinate conversion
            # This ensures exam model coordinates use the same reference system as question bubbles
            ref_width = reference_data['image_size']['width']
            ref_height = reference_data['image_size']['height']
            
            for bubble in exam_model_data['exam_model_bubbles']:
                # Convert relative coordinates to absolute using REFERENCE image dimensions
                if 'relative_contour' in bubble and bubble['relative_contour']:
                    contour_points = np.array([
                        [int(x * ref_width), int(y * ref_height)] 
                        for x, y in bubble['relative_contour']
                    ], dtype=np.int32)
                else:
                    # If no contour data, create circular contour from center
                    center_x = int(bubble['relative_center'][0] * ref_width)
                    center_y = int(bubble['relative_center'][1] * ref_height)
                    radius = 15  # Reasonable bubble radius
                    
                    # Create circle contour
                    contour_points = []
                    for angle in range(0, 360, 10):
                        x = center_x + int(radius * np.cos(np.radians(angle)))
                        y = center_y + int(radius * np.sin(np.radians(angle)))
                        contour_points.append([x, y])
                    contour_points = np.array(contour_points, dtype=np.int32)
                
                # Ensure contour points are within image bounds
                contour_points = np.clip(contour_points, [0, 0], [width-1, height-1])
                
                # Process bubble and store data (same as question bubbles)
                fill_percent = process_bubble(otsu, contour_points, vis_image, overlay)
                exam_model_bubbles_data.append({'fill_percent': fill_percent})
                
                model_letter = bubble.get('model_letter', 'Unknown')
                center_x = int(bubble['relative_center'][0] * ref_width)
                center_y = int(bubble['relative_center'][1] * ref_height)
                print(f"  Model {model_letter}: center ({center_x}, {center_y}), fill: {fill_percent:.1f}%")
    
    # Process answer bubbles
    for bubble in reference_data['bubbles']:
        # Convert relative coordinates back to absolute
        contour_points = np.array([
            [int(x * width), int(y * height)] 
            for x, y in bubble['relative_contour']
        ], dtype=np.int32)
        
        # Process bubble and store data
        fill_percent = process_bubble(otsu, contour_points, vis_image, overlay)
        bubbles_data.append({'fill_percent': fill_percent})
    
    # Process ID bubbles if available
    if id_reference_data:
        for bubble in id_reference_data['id_bubbles']:
            # Only process columns 3-7 (exclude first 3 and last 2 columns)
            if bubble['column'] not in [0, 1, 2, 8, 9]:
                # Create circular contour for ID bubble
                center_x = int(bubble['relative_x'] * width)
                center_y = int(bubble['relative_y'] * height)
                radius = 10  # Adjust this based on your bubble size
                
                # Create circle contour
                contour_points = []
                for angle in range(0, 360, 10):
                    x = center_x + int(radius * np.cos(np.radians(angle)))
                    y = center_y + int(radius * np.sin(np.radians(angle)))
                    contour_points.append([x, y])
                contour = np.array(contour_points, dtype=np.int32)
                
                # Process bubble and store data
                fill_percent = process_bubble(otsu, contour, vis_image, overlay)
                id_bubbles_data.append({
                    'column': bubble['column'],
                    'number': bubble['number'],
                    'fill_percent': fill_percent
                })
    
    # Calculate grades
    grade_data = calculate_grade(bubbles_data, id_bubbles_data if id_reference_data else None, 
                               exam_model_bubbles_data if exam_model_data else None)
    
    # Combine visualization with overlay
    result = cv2.addWeighted(vis_image, 1-alpha, overlay, alpha, 0)
    
    # Add legend with more information
    legend_height = 120 if (id_reference_data or exam_model_data) else 80  # Extra space for ID/exam model
    legend = np.ones((legend_height, result.shape[1], 3), dtype=np.uint8) * 255
    
    # Legend entries
    entries = [
        (f"Filled (>{FILLING_PERCENT}%): {filled_count}", (0, 0, 255)),
        (f"Other bubbles: {len(reference_data['bubbles']) - filled_count}", (0, 255, 0)),
        (f"Questions: {grade_data['total_questions']}", (0, 0, 0)),
        (f"Answered: {grade_data['statistics']['total_answered']}", (0, 0, 0)),
        (f"Multiple: {grade_data['statistics']['multiple_answers']}", (0, 0, 0)),
        (f"Unanswered: {grade_data['statistics']['unanswered']}", (0, 0, 0))
    ]
    
    if 'exam_model' in grade_data:
        entries.append((f"Exam Model: {grade_data['exam_model']['value']}", (0, 0, 0)))
    
    if 'id' in grade_data:
        entries.append((f"ID: {grade_data['id']['value']}", (0, 0, 0)))
    
    # Draw legend entries in rows
    for i, (text, color) in enumerate(entries):
        row = i // 3
        col = i % 3
        y_offset = 20 + row * 30
        x_offset = 10 + col * (result.shape[1] // 3)
        
        # Draw color box for first row only
        if row == 0:
            cv2.rectangle(legend, (x_offset, y_offset-10), (x_offset+20, y_offset+10), color, -1)
            cv2.rectangle(legend, (x_offset, y_offset-10), (x_offset+20, y_offset+10), (0, 0, 0), 1)
            text_x = x_offset + 30
        else:
            text_x = x_offset
        
        # Add text
        cv2.putText(legend, text, (text_x, y_offset+5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    
    # Combine with legend
    result = np.vstack([result, legend])
    
    return result, grade_data

def process_bubble(threshold_image, contour, vis_image, overlay):
    """Process a single bubble and update visualizations."""
    # Calculate fill percentage
    mask = np.zeros_like(threshold_image)
    cv2.drawContours(mask, [contour], -1, 255, -1)
    roi = cv2.bitwise_and(threshold_image, threshold_image, mask=mask)
    total_pixels = cv2.countNonZero(mask)
    
    if total_pixels > 0:
        filled_pixels = cv2.countNonZero(roi)
        fill_percent = (filled_pixels / total_pixels) * 100
    else:
        fill_percent = 0
    
    # Determine color and thickness based on fill percentage
    if fill_percent > FILLING_PERCENT:
        color = (0, 0, 255)  # Red
        thickness = 2
        alpha_local = 0.6
    else:
        color = (0, 255, 0)  # Green
        thickness = 1
        alpha_local = 0.3
    
    # Draw filled contour on overlay
    overlay_contour = overlay.copy()
    cv2.drawContours(overlay_contour, [contour], -1, color, -1)
    cv2.addWeighted(overlay_contour, alpha_local, overlay, 1 - alpha_local, 0, overlay)
    
    # Draw contour on main visualization
    cv2.drawContours(vis_image, [contour], -1, color, thickness)
    
    # Add fill percentage
    M = cv2.moments(contour)
    if M['m00'] != 0:
        cx = int(M['m10'] / M['m00'])
        cy = int(M['m01'] / M['m00'])
        
        # Draw white background with border for text
        text = f"{fill_percent:.0f}%"
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.4
        thickness = 1
        (text_width, text_height), _ = cv2.getTextSize(text, font, scale, thickness)
        
        # Background rectangle with border
        padding = 2
        bg_rect_pts = np.array([
            [cx-text_width//2-padding, cy-text_height-padding],
            [cx+text_width//2+padding, cy+padding]
        ])
        
        # Draw white background with black border
        cv2.rectangle(vis_image, 
                    tuple(bg_rect_pts[0]),
                    tuple(bg_rect_pts[1]),
                    (255, 255, 255),
                    -1)
        cv2.rectangle(vis_image,
                    tuple(bg_rect_pts[0]),
                    tuple(bg_rect_pts[1]),
                    (0, 0, 0),
                    1)
        
        # Draw text
        cv2.putText(vis_image, text,
                  (cx-text_width//2, cy),
                  font, scale, color, thickness)
    
    return fill_percent

def highlight_reference_bubbles(image_path, reference_data_file='reference_data.json', id_reference_file='id_coordinates.json', exam_models_file='exam_models.json', output_file='highlighted_bubbles.jpg', exam_model_key='exam_model_1'):
    """Create visualization of bubbles from reference data on the actual image."""
    # Load reference data
    with open(reference_data_file, 'r') as f:
        reference_data = json.load(f)
    
    # Load ID reference data if available
    id_reference_data = None
    if os.path.exists(id_reference_file):
        with open(id_reference_file, 'r') as f:
            id_reference_data = json.load(f)
    
    # Load exam model reference data if available
    exam_model_reference_data = None
    if os.path.exists(exam_models_file):
        with open(exam_models_file, 'r') as f:
            exam_models_data = json.load(f)
            
        # Select the specified exam model or the first available one
        if exam_model_key in exam_models_data:
            exam_model_reference_data = exam_models_data[exam_model_key]
            print(f"Using exam model: {exam_model_key}")
        elif exam_models_data:
            # Use the first available exam model
            first_key = list(exam_models_data.keys())[0]
            exam_model_reference_data = exam_models_data[first_key]
            print(f"Exam model '{exam_model_key}' not found, using: {first_key}")
        else:
            print("No exam models found in file")
    
    # Load and align the image
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError("Could not load image")
    
    # Align image with reference using ArUco markers
    aligned_image, transform = compare_with_reference(image, reference_data_file)
    
    # Create visualization and get grade data
    vis_image, grade_data = create_visualization(aligned_image, reference_data, id_reference_data, exam_model_reference_data, transform)
    
    # Save result
    cv2.imwrite(output_file, vis_image)
    
    # Save grade data to CSV
    csv_output = os.path.splitext(output_file)[0] + '_grades.csv'
    with open(csv_output, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Write exam model if available
        if 'exam_model' in grade_data:
            writer.writerow(['Exam_Model', grade_data['exam_model']['value']])
            writer.writerow([])  # Empty row for separation
        
        # Write ID if available
        if 'id' in grade_data:
            writer.writerow(['ID', grade_data['id']['value']])
            writer.writerow([])  # Empty row for separation
        
        # Write answers
        writer.writerow(['Question', 'Answer'])
        for answer in grade_data['answers']:
            status = answer['answer'] if answer['answer'] else 'BLANK'
            if status == 'multiple':
                status = 'MULTIPLE'
            writer.writerow([answer['question'], status])
    
    # Print results
    if 'exam_model' in grade_data:
        print(f"Exam Model: {grade_data['exam_model']['value']}")
    if 'id' in grade_data:
        print(f"ID: {grade_data['id']['value']}")
    for answer in grade_data['answers']:
        print(f"Question {answer['question']}: {answer['answer']}")
    return grade_data

def print_stats(grade_data):
    """Print grading statistics."""
    print("\nGrading Statistics")
    print("=================")
    
    if 'exam_model' in grade_data:
        print(f"Exam Model: {grade_data['exam_model']['value']}")
        print(f"Exam Model Fill Percentages: {[f'{p:.1f}%' for p in grade_data['exam_model']['fill_percentages']]}")
        if not grade_data['exam_model']['is_valid']:
            print("Warning: Exam model is blank or has multiple marks")
        print()
    
    if 'id' in grade_data:
        print(f"ID Number: {grade_data['id']['value']}")
        if not grade_data['id']['is_complete']:
            print("Warning: ID is incomplete or has multiple marks")
        print()
    
    print(f"Total questions: {grade_data['total_questions']}")
    print(f"Questions answered: {grade_data['statistics']['total_answered']}")
    print(f"Multiple answers: {grade_data['statistics']['multiple_answers']}")
    print(f"Unanswered: {grade_data['statistics']['unanswered']}")
    print("\nDetailed Answers:")
    print("----------------")
    for answer in grade_data['answers']:
        status = answer['answer'] if answer['answer'] else 'BLANK'
        if status == 'multiple':
            status = 'MULTIPLE'
        print(f"Question {answer['question']:3d}: {status:8} (Fill %: {', '.join(f'{p:.0f}%' for p in answer['fill_percentages'])})")

def print_filter_info():
    """Print information about the filter steps."""
    print("\nFilter Steps Explanation:")
    print("========================")
    print("0_original.jpg: Original input image")
    print("0_aligned.jpg: Image aligned using ArUco markers")
    print("1_grayscale.jpg: Converted to grayscale")
    print("2_clahe.jpg: After adaptive histogram equalization")
    print("3_denoised.jpg: After noise reduction")
    print("4_gaussian_blur.jpg: After Gaussian blur")
    print("5_contrast_enhanced.jpg: After contrast enhancement")
    print("\nThresholding Methods:")
    print("6a_otsu_threshold.jpg: Otsu's thresholding")
    print("6b_adaptive_gaussian.jpg: Adaptive Gaussian thresholding")
    print("6c_adaptive_mean.jpg: Adaptive Mean thresholding")
    print("6d_threshold_comparison.jpg: Side-by-side comparison of thresholding methods")

def main():
    """Main function to highlight reference bubbles."""
    import argparse
    parser = argparse.ArgumentParser(description='Highlight bubbles on the image')
    parser.add_argument('image_path', help='Path to the image with filled bubbles')
    parser.add_argument('--reference', default='reference_data.json',
                      help='Path to reference data file (default: reference_data.json)')
    parser.add_argument('--id', default='id_coordinates.json',
                      help='Path to ID coordinates file (default: id_coordinates.json)')
    parser.add_argument('--exam_model', default='exam_models.json',
                      help='Path to exam model coordinates file (default: exam_models.json)')
    parser.add_argument('--exam_model_key', default='exam_model_1',
                      help='Which exam model to use from the file (default: exam_model_1)')
    parser.add_argument('--output', default='highlighted_bubbles.jpg',
                      help='Output image path (default: highlighted_bubbles.jpg)')
    
    args = parser.parse_args()
    
    try:
        print("\nProcessing image and saving filter steps...")
        stats = highlight_reference_bubbles(args.image_path, args.reference, args.id, args.exam_model, args.output, args.exam_model_key)
        print("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
        print_stats(stats)
        print("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
        print_filter_info()
        print("\nAll filter steps have been saved in the 'filter_steps' directory.")
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 