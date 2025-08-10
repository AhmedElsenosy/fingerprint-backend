import cv2
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import json
import datetime

def load_coordinates(coord_file='bubble_coordinates.txt'):
    """Load bubble coordinates from the file."""
    coords = []
    with open(coord_file, 'r') as f:
        for line in f:
            qb, x, y = line.strip().split(',')
            coords.append({
                'id': qb,
                'x': int(x),
                'y': int(y)
            })
    return coords

def is_b1_bubble(bubble_id):
    """Check if the bubble is a B1 (first bubble of a question)."""
    return bubble_id.endswith('B1')

def is_b5_bubble(bubble_id):
    """Check if the bubble is a B5 (last bubble of a question)."""
    return bubble_id.endswith('B5')

def is_b4_bubble(bubble_id):
    """Check if the bubble is a B4 bubble."""
    return bubble_id.endswith('B4')

def get_bubble_number(bubble_id):
    """Get the bubble number (1-5) from the ID."""
    return int(bubble_id.split('B')[1])

def enhance_roi(roi, is_b1=False, is_b5=False, is_b4=False):
    """Apply appropriate enhancements based on bubble position."""
    # Apply CLAHE with different parameters based on bubble position
    if is_b1:
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(3,3))
    elif is_b5:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4,4))
    elif is_b4:
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(3,3))
    else:
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(3,3))
    
    enhanced = clahe.apply(roi)
    
    # Additional enhancement for problematic bubbles
    if is_b5 or is_b4:
        # Sharpen the image
        kernel = np.array([[-1,-1,-1],
                         [-1, 9,-1],
                         [-1,-1,-1]])
        enhanced = cv2.filter2D(enhanced, -1, kernel)
        
        # Denoise
        enhanced = cv2.fastNlMeansDenoising(enhanced, None, 10, 7, 21)
    
    return enhanced

def find_circle_hough(roi, min_radius=8, max_radius=15):
    """Find circles using Hough Circle Transform."""
    # Blur the image to reduce noise
    blurred = cv2.GaussianBlur(roi, (5, 5), 0)
    
    # Try different parameters for Hough Circle detection
    circles = None
    params = [
        # param1 (gradient value), param2 (threshold), min_dist
        (50, 25, 20),
        (40, 20, 20),
        (30, 15, 20),
        (20, 10, 20)
    ]
    
    for param1, param2, min_dist in params:
        circles = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=1,
            minDist=min_dist,
            param1=param1,
            param2=param2,
            minRadius=min_radius,
            maxRadius=max_radius
        )
        if circles is not None:
            break
    
    return circles

def create_circular_mask(roi_shape, center, radius):
    """Create a circular mask."""
    Y, X = np.ogrid[:roi_shape[0], :roi_shape[1]]
    dist_from_center = np.sqrt((X - center[0])**2 + (Y - center[1])**2)
    mask = dist_from_center <= radius
    return mask.astype(np.uint8) * 255

def detect_bubble_fallback(roi, target_area=200, methods=['contour', 'hough', 'template']):
    """Try multiple methods to detect a bubble."""
    h, w = roi.shape
    center = (w//2, h//2)
    best_contour = None
    best_circularity = 0
    
    for method in methods:
        if method == 'contour':
            # Try different thresholding approaches
            thresholds = []
            
            # 1. Adaptive threshold
            thresh1 = cv2.adaptiveThreshold(
                roi, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY_INV, 15, 3
            )
            thresholds.append(thresh1)
            
            # 2. Otsu's threshold
            _, thresh2 = cv2.threshold(
                roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
            )
            thresholds.append(thresh2)
            
            # 3. Mean-based threshold
            mean = cv2.mean(roi)[0]
            _, thresh3 = cv2.threshold(
                roi, mean * 0.85, 255, cv2.THRESH_BINARY_INV
            )
            thresholds.append(thresh3)
            
            # Try each threshold
            for thresh in thresholds:
                contours, _ = cv2.findContours(
                    thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE
                )
                
                for contour in contours:
                    area = cv2.contourArea(contour)
                    # Check size is within reasonable range
                    if not (0.5 * target_area <= area <= 1.5 * target_area):
                        continue
                    
                    perimeter = cv2.arcLength(contour, True)
                    circularity = 4 * np.pi * area / (perimeter * perimeter) if perimeter > 0 else 0
                    
                    if circularity > best_circularity:
                        best_circularity = circularity
                        best_contour = contour
        
        elif method == 'hough':
            circles = find_circle_hough(roi)
            if circles is not None:
                circle = circles[0][0]
                center = (int(circle[0]), int(circle[1]))
                radius = int(circle[2])
                
                # Create circular contour with target area
                target_radius = int(np.sqrt(target_area / np.pi))
                mask = create_circular_mask(roi.shape, center, target_radius)
                contours, _ = cv2.findContours(
                    mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE
                )
                
                if contours:
                    contour = contours[0]
                    area = cv2.contourArea(contour)
                    if 0.7 * target_area <= area <= 1.3 * target_area:
                        perimeter = cv2.arcLength(contour, True)
                        circularity = 4 * np.pi * area / (perimeter * perimeter) if perimeter > 0 else 0
                        
                        if circularity > best_circularity:
                            best_circularity = circularity
                            best_contour = contour
        
        elif method == 'template':
            # Calculate template size based on target area
            template_radius = int(np.sqrt(target_area / np.pi))
            template_size = template_radius * 2 + 1
            
            template = np.zeros((template_size, template_size), dtype=np.uint8)
            center = (template_size // 2, template_size // 2)
            cv2.circle(template, center, template_radius, 255, -1)
            
            # Match template
            result = cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED)
            _, _, _, max_loc = cv2.minMaxLoc(result)
            
            # Create contour from template match
            mask = np.zeros_like(roi)
            x, y = max_loc
            mask[y:y+template_size, x:x+template_size] = template
            contours, _ = cv2.findContours(
                mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE
            )
            
            if contours:
                contour = contours[0]
                area = cv2.contourArea(contour)
                if 0.7 * target_area <= area <= 1.3 * target_area:
                    perimeter = cv2.arcLength(contour, True)
                    circularity = 4 * np.pi * area / (perimeter * perimeter) if perimeter > 0 else 0
                    
                    if circularity > best_circularity:
                        best_circularity = circularity
                        best_contour = contour
    
    return best_contour, best_circularity

def calculate_fill_percentage(roi_gray, roi_mask):
    """Calculate fill percentage using multiple methods."""
    if roi_mask.size == 0 or roi_gray.size == 0:
        return 0
    
    # Method 1: Mean intensity
    mean_intensity = cv2.mean(roi_gray, mask=roi_mask)[0]
    fill_1 = (255 - mean_intensity) / 255 * 100
    
    # Method 2: Otsu's thresholding
    _, thresh = cv2.threshold(roi_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    mask_pixels = cv2.countNonZero(roi_mask)
    if mask_pixels > 0:
        fill_2 = (cv2.countNonZero(cv2.bitwise_and(thresh, roi_mask)) / mask_pixels) * 100
    else:
        fill_2 = 0
    
    # Method 3: Adaptive thresholding
    thresh_adapt = cv2.adaptiveThreshold(roi_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY_INV, 11, 2)
    if mask_pixels > 0:
        fill_3 = (cv2.countNonZero(cv2.bitwise_and(thresh_adapt, roi_mask)) / mask_pixels) * 100
    else:
        fill_3 = 0
    
    # Combine methods with weights
    fill_percent = (fill_1 * 0.4 + fill_2 * 0.3 + fill_3 * 0.3)
    
    return fill_percent

def normalize_bubble_size(contour, target_area=200):
    """Normalize bubble size to be consistent with others."""
    area = cv2.contourArea(contour)
    if area == 0:
        return contour
    
    # Calculate scaling factor
    scale = np.sqrt(target_area / area)
    
    # Get contour center
    M = cv2.moments(contour)
    if M['m00'] == 0:
        return contour
    
    cx = int(M['m10'] / M['m00'])
    cy = int(M['m01'] / M['m00'])
    
    # Create transformation matrix
    M = np.float32([[scale, 0, cx*(1-scale)],
                    [0, scale, cy*(1-scale)]])
    
    # Reshape contour for transformation
    contour_array = contour.reshape(-1, 2).astype(np.float32)
    
    # Apply transformation
    scaled_contour = cv2.transform(contour_array.reshape(-1, 1, 2), M)
    
    return scaled_contour.astype(np.int32)

def get_average_bubble_area(reference_bubbles):
    """Calculate the average area of detected bubbles."""
    if not reference_bubbles:
        return 200  # Default target area
    
    # Get areas from reference bubbles
    areas = [b['area'] for b in reference_bubbles]
    
    if not areas:
        return 200
    
    # Use median to avoid outliers
    return np.median(areas)

def detect_bubble_edges(image, coordinates, radius=20):
    """Detect precise edges of bubbles using the known coordinates."""
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    
    # Create output images
    edges = np.zeros_like(gray)
    semantic = np.zeros((image.shape[0], image.shape[1], 3), dtype=np.uint8)
    debug = image.copy()
    failure_debug = image.copy()
    heatmap = np.zeros_like(gray, dtype=np.float32)
    
    bubble_data = []
    failed_coords = []
    
    # Apply global preprocessing
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Group coordinates by question number
    questions = {}
    for coord in coordinates:
        q_num = coord['id'].split('B')[0]
        if q_num not in questions:
            questions[q_num] = []
        questions[q_num].append(coord)
    
    # First pass: detect non-B5 bubbles to establish size reference
    reference_bubbles = []
    for q_num, q_coords in questions.items():
        q_coords.sort(key=lambda x: get_bubble_number(x['id']))
        for coord in q_coords:
            if not (is_b5_bubble(coord['id']) or is_b4_bubble(coord['id'])):
                try:
                    x, y = coord['x'], coord['y']
                    roi = blurred[max(0, y-radius):min(gray.shape[0], y+radius),
                               max(0, x-radius):min(gray.shape[1], x+radius)]
                    
                    if roi.size == 0:
                        continue
                    
                    roi = enhance_roi(roi, is_b1=is_b1_bubble(coord['id']))
                    best_contour, best_circularity = detect_bubble_fallback(roi)
                    
                    if best_contour is not None:
                        # Adjust contour coordinates to image space
                        best_contour += np.array([max(0, x-radius), max(0, y-radius)])
                        area = cv2.contourArea(best_contour)
                        if area > 0:  # Only add valid contours
                            reference_bubbles.append({
                                'area': area
                            })
                except Exception as e:
                    continue
    
    # Calculate target area from reference bubbles
    target_area = get_average_bubble_area(reference_bubbles)
    
    # Main detection loop
    for q_num, q_coords in questions.items():
        q_coords.sort(key=lambda x: get_bubble_number(x['id']))
        
        for coord in q_coords:
            try:
                x, y = coord['x'], coord['y']
                is_b1 = is_b1_bubble(coord['id'])
                is_b5 = is_b5_bubble(coord['id'])
                is_b4 = is_b4_bubble(coord['id'])
                
                roi = blurred[max(0, y-radius):min(gray.shape[0], y+radius),
                           max(0, x-radius):min(gray.shape[1], x+radius)]
                
                if roi.size == 0:
                    raise ValueError("Empty ROI")
                
                roi = enhance_roi(roi, is_b1, is_b5, is_b4)
                
                if is_b5 or is_b4:
                    best_contour, best_circularity = detect_bubble_fallback(roi, target_area=target_area)
                else:
                    # Standard detection method
                    thresholds = []
                    
                    # 1. Adaptive thresholding with different parameters
                    block_size = 15 if (is_b1 or is_b5) else 21
                    c_value = 3 if (is_b1 or is_b5) else 5
                    thresh1 = cv2.adaptiveThreshold(
                        roi, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                        cv2.THRESH_BINARY_INV, block_size, c_value
                    )
                    thresholds.append(thresh1)
                    
                    # 2. Otsu's thresholding
                    _, thresh2 = cv2.threshold(
                        roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
                    )
                    thresholds.append(thresh2)
                    
                    # Combine thresholds
                    thresh = cv2.bitwise_or(thresh1, thresh2)
                    
                    # Find contours
                    contours, _ = cv2.findContours(
                        thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE
                    )
                    
                    best_contour = None
                    best_circularity = 0
                    
                    for contour in contours:
                        area = cv2.contourArea(contour)
                        if not (0.5 * target_area <= area <= 1.5 * target_area):
                            continue
                        
                        perimeter = cv2.arcLength(contour, True)
                        circularity = 4 * np.pi * area / (perimeter * perimeter) if perimeter > 0 else 0
                        
                        if circularity > best_circularity:
                            best_circularity = circularity
                            best_contour = contour
                
                if best_contour is None:
                    raise ValueError("No suitable contour found")
                
                # Adjust contour coordinates to image space
                best_contour += np.array([max(0, x-radius), max(0, y-radius)])
                
                # Normalize bubble size
                best_contour = normalize_bubble_size(best_contour, target_area)
                
                # Verify size is within acceptable range
                area = cv2.contourArea(best_contour)
                if not (0.7 * target_area <= area <= 1.3 * target_area):
                    raise ValueError(f"Abnormal bubble size: {area} vs target {target_area}")
                
                # Create mask for this bubble
                mask = np.zeros_like(gray)
                cv2.drawContours(mask, [best_contour], -1, 255, -1)
                
                # Calculate fill percentage
                roi_mask = mask[max(0, y-radius):min(gray.shape[0], y+radius),
                              max(0, x-radius):min(gray.shape[1], x+radius)]
                roi_gray = gray[max(0, y-radius):min(gray.shape[0], y+radius),
                              max(0, x-radius):min(gray.shape[1], x+radius)]
                
                fill_percent = calculate_fill_percentage(roi_gray, roi_mask)
                
                # Update visualizations and data
                cv2.drawContours(edges, [best_contour], -1, 255, 1)
                cv2.drawContours(heatmap, [best_contour], -1, fill_percent, -1)
                
                # Color code based on fill percentage
                if fill_percent > 40:
                    color = (0, 0, 255)  # Red for filled
                elif fill_percent > 20:
                    color = (0, 165, 255)  # Orange for partially filled
                else:
                    color = (0, 255, 0)  # Green for empty
                
                cv2.drawContours(semantic, [best_contour], -1, color, -1)
                cv2.drawContours(debug, [best_contour], -1, color, 2)
                cv2.putText(debug, f"{fill_percent:.0f}%", (x-10, y-10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
                
                bubble_data.append({
                    'id': coord['id'],
                    'contour': best_contour,
                    'area': area,
                    'circularity': best_circularity,
                    'fill_percent': fill_percent,
                    'is_b1': is_b1,
                    'is_b5': is_b5,
                    'is_b4': is_b4
                })
                
            except Exception as e:
                # Mark failed detection in red
                cv2.circle(failure_debug, (x, y), radius, (0, 0, 255), 2)
                cv2.putText(failure_debug, "X", (x-5, y+5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 2)
                failed_coords.append({
                    'id': coord['id'],
                    'x': x,
                    'y': y,
                    'error': str(e)
                })
    
    return edges, semantic, debug, failure_debug, heatmap, bubble_data, failed_coords

def create_visualizations(image, bubble_data, heatmap):
    """Create additional visualizations."""
    # 1. Create fill percentage distribution plot
    plt.figure(figsize=(10, 6))
    fill_percentages = [b['fill_percent'] for b in bubble_data]
    plt.hist(fill_percentages, bins=50, color='blue', alpha=0.7)
    plt.title('Distribution of Bubble Fill Percentages')
    plt.xlabel('Fill Percentage')
    plt.ylabel('Count')
    plt.savefig('fill_distribution.png')
    plt.close()
    
    # 2. Create circularity distribution plot
    plt.figure(figsize=(10, 6))
    circularities = [b['circularity'] for b in bubble_data]
    plt.hist(circularities, bins=50, color='green', alpha=0.7)
    plt.title('Distribution of Bubble Circularity')
    plt.xlabel('Circularity')
    plt.ylabel('Count')
    plt.savefig('circularity_distribution.png')
    plt.close()
    
    # 3. Create heatmap visualization
    plt.figure(figsize=(12, 8))
    plt.imshow(heatmap, cmap='hot')
    plt.colorbar(label='Fill Percentage')
    plt.title('Bubble Fill Percentage Heatmap')
    plt.savefig('fill_heatmap.png')
    plt.close()
    
    # 4. Create overlay visualization
    overlay = image.copy()
    for bubble in bubble_data:
        fill = bubble['fill_percent']
        # Create color gradient based on fill percentage
        if fill > 40:
            color = (0, 0, 255)  # Red
        elif fill > 20:
            color = (0, 165, 255)  # Orange
        else:
            color = (0, 255, 0)  # Green
        cv2.drawContours(overlay, [bubble['contour']], -1, color, 2)
    
    # Blend with original image
    alpha = 0.7
    cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0, overlay)
    cv2.imwrite('bubble_overlay.jpg', overlay)
    
    # Add bubble size distribution plot
    plt.figure(figsize=(10, 6))
    areas = [cv2.contourArea(b['contour']) for b in bubble_data]
    plt.hist(areas, bins=50, color='purple', alpha=0.7)
    plt.title('Distribution of Bubble Areas')
    plt.xlabel('Area (pixels²)')
    plt.ylabel('Count')
    plt.savefig('area_distribution.png')
    plt.close()
    
    # Add size comparison visualization
    size_vis = image.copy()
    for bubble in bubble_data:
        area = cv2.contourArea(bubble['contour'])
        # Color based on relative size
        if area > 250:  # Too large
            color = (0, 0, 255)  # Red
        elif area < 150:  # Too small
            color = (255, 0, 0)  # Blue
        else:
            color = (0, 255, 0)  # Green
        cv2.drawContours(size_vis, [bubble['contour']], -1, color, 2)
        cv2.putText(size_vis, f"{area:.0f}", 
                   tuple(bubble['contour'][0][0]),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
    cv2.imwrite('bubble_sizes.jpg', size_vis)

def detect_aruco_markers(image):
    """Detect ArUco markers in the image and return their coordinates."""
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    
    # Initialize the ArUco dictionary and parameters
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    parameters = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)
    
    # Detect markers
    corners, ids, _ = detector.detectMarkers(gray)
    
    if ids is None:
        return None
    
    # Extract corner coordinates and IDs
    markers = []
    for marker_corners, marker_id in zip(corners, ids):
        corners_array = marker_corners[0]
        center = np.mean(corners_array, axis=0)
        markers.append({
            'id': int(marker_id[0]),
            'corners': corners_array.tolist(),
            'center': center.tolist()
        })
    
    return markers

def save_reference_data(image, bubble_data, output_file='BubbleSheetCorrecterModule/reference_data.json'):
    """Save bubble data and ArUco marker information for later comparison."""
    # Detect ArUco markers
    markers = detect_aruco_markers(image)
    if markers is None:
        raise ValueError("No ArUco markers detected in the image")
    
    # Calculate image dimensions
    height, width = image.shape[:2]
    
    # Prepare bubble data for saving
    serializable_bubbles = []
    for bubble in bubble_data:
        # Convert contour to relative coordinates
        contour = bubble['contour'].squeeze().tolist()
        relative_contour = [
            [x/width, y/height] for x, y in contour
        ]
        
        serializable_bubbles.append({
            'id': bubble['id'],
            'relative_contour': relative_contour,
            'area': float(bubble['area']),
            'circularity': float(bubble['circularity']),
            'fill_percent': float(bubble['fill_percent']),
            'is_b1': bubble['is_b1'],
            'is_b5': bubble['is_b5'],
            'is_b4': bubble['is_b4']
        })
    
    # Create reference data structure
    reference_data = {
        'image_size': {
            'width': width,
            'height': height
        },
        'aruco_markers': markers,
        'bubbles': serializable_bubbles,
        'timestamp': datetime.datetime.now().isoformat()
    }
    
    # Save to file
    with open(output_file, 'w') as f:
        json.dump(reference_data, f, indent=2)
    
    return reference_data

def compare_with_reference(current_image, reference_data_file='reference_data.json'):
    """Compare current image with reference data and return differences."""
    # Load reference data
    with open(reference_data_file, 'r') as f:
        reference_data = json.load(f)
    
    # Get current markers
    current_markers = detect_aruco_markers(current_image)
    if current_markers is None:
        raise ValueError("No ArUco markers detected in current image")
    
    # Calculate transformation matrix between reference and current markers
    ref_marker_points = []
    cur_marker_points = []
    
    for ref_marker in reference_data['aruco_markers']:
        for cur_marker in current_markers:
            if ref_marker['id'] == cur_marker['id']:
                ref_marker_points.append(ref_marker['center'])
                cur_marker_points.append(cur_marker['center'])
    
    if len(ref_marker_points) < 3:
        raise ValueError("Not enough matching markers found")
    
    # Convert to numpy arrays
    ref_points = np.float32(ref_marker_points)
    cur_points = np.float32(cur_marker_points)
    
    # Calculate transformation matrix
    transform_matrix = cv2.getAffineTransform(
        cur_points[:3],
        ref_points[:3]
    )
    
    # Transform current image to match reference coordinates
    height, width = reference_data['image_size']['height'], reference_data['image_size']['width']
    aligned_image = cv2.warpAffine(current_image, transform_matrix, (width, height))
    
    return aligned_image, transform_matrix

def main():
    # Load the image
    image = cv2.imread('trial7_with_markers.jpg')
    if image is None:
        print("Error: Could not load image")
        return
    
    # Load coordinates
    coordinates = load_coordinates()
    print(f"Loaded {len(coordinates)} bubble coordinates")
    
    # Detect bubble edges
    edges, semantic, debug, failure_debug, heatmap, bubble_data, failed_coords = detect_bubble_edges(image, coordinates)
    
    # Save reference data
    try:
        reference_data = save_reference_data(image, bubble_data)
        print("\nReference data saved successfully")
        print(f"Number of ArUco markers detected: {len(reference_data['aruco_markers'])}")
        print("Marker IDs:", [m['id'] for m in reference_data['aruco_markers']])
    except Exception as e:
        print(f"\nError saving reference data: {str(e)}")
    
    # Save outputs
    cv2.imwrite('bubble_edges.jpg', edges)
    cv2.imwrite('bubble_semantic.jpg', semantic)
    cv2.imwrite('bubble_debug.jpg', debug)
    cv2.imwrite('bubble_failures.jpg', failure_debug)
    
    # Create additional visualizations
    create_visualizations(image, bubble_data, heatmap)
    
    # Print statistics
    print("\nBubble Statistics:")
    print(f"Total bubbles processed: {len(bubble_data)}")
    print(f"Failed detections: {len(failed_coords)}")
    
    # Separate statistics for different bubble positions
    b1_bubbles = [b for b in bubble_data if b['is_b1']]
    b5_bubbles = [b for b in bubble_data if b['is_b5']]
    b4_bubbles = [b for b in bubble_data if b['is_b4']]
    other_bubbles = [b for b in bubble_data if not (b['is_b1'] or b['is_b5'] or b['is_b4'])]
    
    print(f"\nB1 bubbles detected: {len(b1_bubbles)} / {len([c for c in coordinates if is_b1_bubble(c['id'])])}")
    print(f"B5 bubbles detected: {len(b5_bubbles)} / {len([c for c in coordinates if is_b5_bubble(c['id'])])}")
    print(f"B4 bubbles detected: {len(b4_bubbles)} / {len([c for c in coordinates if is_b4_bubble(c['id'])])}")
    print(f"Other bubbles detected: {len(other_bubbles)} / {len([c for c in coordinates if not (is_b1_bubble(c['id']) or is_b5_bubble(c['id']) or is_b4_bubble(c['id']))])}")
    
    if failed_coords:
        print("\nFailed Bubble IDs:")
        for fail in failed_coords:
            print(f"{fail['id']}: {fail['error']}")
    
    # Print fill percentage statistics
    filled_bubbles = [b for b in bubble_data if b['fill_percent'] > 40]
    partially_filled = [b for b in bubble_data if 20 < b['fill_percent'] <= 40]
    empty_bubbles = [b for b in bubble_data if b['fill_percent'] <= 20]
    
    print(f"\nFill Analysis:")
    print(f"Filled bubbles (>40%): {len(filled_bubbles)}")
    print(f"Partially filled (20-40%): {len(partially_filled)}")
    print(f"Empty bubbles (≤20%): {len(empty_bubbles)}")
    
    if bubble_data:
        # Overall statistics
        print(f"\nOverall Statistics:")
        avg_circularity = np.mean([b['circularity'] for b in bubble_data])
        print(f"Average circularity: {avg_circularity:.3f}")
        
        avg_fill = np.mean([b['fill_percent'] for b in bubble_data])
        print(f"Average fill percentage: {avg_fill:.1f}%")
        
        # B1 statistics
        if b1_bubbles:
            print(f"\nB1 Bubble Statistics:")
            avg_b1_circ = np.mean([b['circularity'] for b in b1_bubbles])
            print(f"Average B1 circularity: {avg_b1_circ:.3f}")
            avg_b1_fill = np.mean([b['fill_percent'] for b in b1_bubbles])
            print(f"Average B1 fill percentage: {avg_b1_fill:.1f}%")
        
        # B5 statistics
        if b5_bubbles:
            print(f"\nB5 Bubble Statistics:")
            avg_b5_circ = np.mean([b['circularity'] for b in b5_bubbles])
            print(f"Average B5 circularity: {avg_b5_circ:.3f}")
            avg_b5_fill = np.mean([b['fill_percent'] for b in b5_bubbles])
            print(f"Average B5 fill percentage: {avg_b5_fill:.1f}%")
        
        # Save detailed bubble data
        with open('bubble_analysis.txt', 'w') as f:
            f.write("ID,Fill%,Circularity,Area,IsB1,IsB5,IsB4\n")
            for bubble in bubble_data:
                f.write(f"{bubble['id']},{bubble['fill_percent']:.1f}," +
                       f"{bubble['circularity']:.3f},{bubble['area']}," +
                       f"{bubble['is_b1']},{bubble['is_b5']},{bubble['is_b4']}\n")

if __name__ == "__main__":
    main() 