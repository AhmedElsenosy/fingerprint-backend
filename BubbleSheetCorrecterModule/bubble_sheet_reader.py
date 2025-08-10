import cv2
import numpy as np
import pandas as pd
import imutils
import os
from pathlib import Path
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors
from sklearn.cluster import DBSCAN
import matplotlib.pyplot as plt
from pupil_apriltags import Detector

class BubbleSheetReader:
    def __init__(self):
        self.DEBUG = True
        self.ID_KEY = {0: '0', 1: '1', 2: '2', 3: '3', 4: '4', 
                       5: '5', 6: '6', 7: '7', 8: '8', 9: '9'}
        self.ANSWER_KEY = {0: 'A', 1: 'B', 2: 'C', 3: 'D', 4: 'E'}
        self.EXAM_MODEL_KEY = {0: 'A', 1: 'B', 2: 'C', 3: 'D', 4: 'E'}  # New: exam model mapping
        # Initialize AprilTag detector
        self.detector = Detector(families='tag36h11')
        
    def detect_tag(self, image, region):
        """Detect a tag in the given region."""
        # Extract region
        x, y, w, h = region
        roi = image[y:y+h, x:x+w]
        
        # Threshold
        _, thresh = cv2.threshold(roi, 127, 255, cv2.THRESH_BINARY)
        
        # Find contours
        contours = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = imutils.grab_contours(contours)
        
        if not contours:
            return None
        
        # Find the largest contour (should be the border)
        border = max(contours, key=cv2.contourArea)
        
        # Get the bounding box
        x_b, y_b, w_b, h_b = cv2.boundingRect(border)
        
        # Extract the inner region
        inner = thresh[y_b:y_b+h_b, x_b:x_b+w_b]
        
        # Split into 2x2 grid
        h_inner, w_inner = inner.shape
        cell_h = h_inner // 2
        cell_w = w_inner // 2
        
        # Read the binary pattern
        pattern = []
        for i in range(2):
            for j in range(2):
                cell = inner[i*cell_h:(i+1)*cell_h, j*cell_w:(j+1)*cell_w]
                # Cell is considered filled if more than 50% is black
                filled = np.sum(cell == 0) > cell.size * 0.5
                pattern.append(1 if filled else 0)
        
        # Convert pattern to tag ID
        tag_id = int(''.join(map(str, pattern)), 2)
        
        # Get corners
        corners = cv2.boxPoints(cv2.minAreaRect(border))
        corners = corners + [x, y]  # Adjust for ROI offset
        
        return tag_id, corners
        
    def detect_markers(self, image):
        """Detect tag markers in the image."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Define regions to search for markers
        h, w = gray.shape
        marker_size = 64
        padding = 20
        
        # Region for exam model section marker (top center)
        exam_model_x = w // 2 - marker_size // 2 - padding
        exam_model_y = 30 - padding  # Very top
        exam_model_region = (exam_model_x, exam_model_y, marker_size + 2*padding, marker_size + 2*padding)
        
        # Regions for question section markers (moved down)
        question_regions = []
        section_width = w // 4
        question_start_y = 180  # Moved down to make room for exam model section
        for i in range(4):
            x = i * section_width + (section_width - marker_size) // 2 - padding
            y = question_start_y - padding
            region = (x, y, marker_size + 2*padding, marker_size + 2*padding)
            question_regions.append(region)
        
        # Region for ID section marker (bottom)
        id_x = w // 2 - marker_size // 2 - padding
        id_y = int(h * 0.75) - padding  # Moved down slightly
        id_region = (id_x, id_y, marker_size + 2*padding, marker_size + 2*padding)
        
        # Detect markers
        corners = []
        ids = []
        
        # Process exam model region
        result = self.detect_tag(gray, exam_model_region)
        if result:
            tag_id, tag_corners = result
            corners.append(tag_corners)
            ids.append([tag_id])
        
        # Process question regions
        for i, region in enumerate(question_regions):
            result = self.detect_tag(gray, region)
            if result:
                tag_id, tag_corners = result
                corners.append(tag_corners)
                ids.append([tag_id])
        
        # Process ID region
        result = self.detect_tag(gray, id_region)
        if result:
            tag_id, tag_corners = result
            corners.append(tag_corners)
            ids.append([tag_id])
        
        if self.DEBUG:
            # Draw detected markers
            debug_img = image.copy()
            for i, (corner, tag_id) in enumerate(zip(corners, ids)):
                # Draw corners
                pts = corner.astype(int)
                pts = pts.reshape((-1, 1, 2))
                cv2.polylines(debug_img, [pts], True, (0, 255, 0), 2)
                
                # Draw tag ID
                center = np.mean(corner, axis=0).astype(int)
                cv2.putText(debug_img, str(tag_id[0]), tuple(center), 
                          cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            
            cv2.imwrite('debug_markers.jpg', debug_img)
            print(f"Found {len(corners)} tag markers")
        
        return corners, np.array(ids)
        
    def detect_sections(self, image):
        # Detect tag markers
        corners, ids = self.detect_markers(image)
        
        if corners is None or len(corners) < 6:  # We need at least 6 markers now
            if self.DEBUG:
                print(f"Not enough markers found: {len(corners) if corners else 0}")
            return None, None, None
        
        # Convert corners to numpy array if needed
        if not isinstance(corners, np.ndarray):
            corners = np.array(corners)
        
        # Sort markers by y-coordinate to separate sections
        y_coords = [np.mean(c[:, 1]) for c in corners]
        sorted_indices = np.argsort(y_coords)
        
        # Identify sections based on marker IDs and positions
        exam_model_marker = None
        question_markers = []
        id_marker = None
        
        # Map markers by their IDs
        for i, corner in enumerate(corners):
            marker_id = ids[i][0] if len(ids[i]) > 0 else -1
            
            if marker_id == 5:  # Exam model marker
                exam_model_marker = corner
            elif marker_id in [0, 1, 2, 3]:  # Question markers
                question_markers.append((marker_id, corner))
            elif marker_id == 4:  # ID marker
                id_marker = corner
        
        if exam_model_marker is None or len(question_markers) < 4 or id_marker is None:
            if self.DEBUG:
                print(f"Missing required markers: exam_model={exam_model_marker is not None}, "
                      f"questions={len(question_markers)}, id={id_marker is not None}")
            return None, None, None
        
        # Sort question markers by their IDs (0, 1, 2, 3)
        question_markers.sort(key=lambda x: x[0])
        question_markers = [marker for _, marker in question_markers]
        
        # Define regions based on marker positions
        h, w = image.shape[:2]
        
        # Exam model section
        exam_center_x = np.mean(exam_model_marker[:, 0])
        exam_center_y = np.mean(exam_model_marker[:, 1])
        
        exam_width = int(w * 0.6)
        exam_height = 120  # Height for exam model section
        
        exam_x = int(exam_center_x - exam_width/2)
        exam_y = int(exam_center_y + 64 + 10)  # Below the marker
        
        exam_model_section = {
            'paper': image[exam_y:exam_y+exam_height, exam_x:exam_x+exam_width],
            'warped': cv2.cvtColor(image[exam_y:exam_y+exam_height, exam_x:exam_x+exam_width], cv2.COLOR_BGR2GRAY),
            'thresh': None,  # Will be set by process_section
            'bounds': (exam_x, exam_y, exam_width, exam_height)
        }
        
        # Question sections
        question_sections = []
        for i, marker in enumerate(question_markers):
            # Get marker center
            center_x = np.mean(marker[:, 0])
            center_y = np.mean(marker[:, 1])
            
            # Define section bounds relative to marker
            section_width = w // 4  # Quarter of image width
            section_height = int(h * 0.4)  # Reduced height to make room
            
            x = int(center_x - section_width/2)
            y = int(center_y + 64 + 20)  # Below the marker
            
            section = {
                'paper': image[y:y+section_height, x:x+section_width],
                'warped': cv2.cvtColor(image[y:y+section_height, x:x+section_width], cv2.COLOR_BGR2GRAY),
                'thresh': None,  # Will be set by process_section
                'bounds': (x, y, section_width, section_height)
            }
            question_sections.append(section)
        
        # ID section
        id_center_x = np.mean(id_marker[:, 0])
        id_center_y = np.mean(id_marker[:, 1])
        
        id_width = int(w * 0.3)
        id_height = int(h * 0.15)  # Reduced height
        
        id_x = int(id_center_x - id_width/2)
        id_y = int(id_center_y + 64 + 20)  # Below the marker
        
        id_section = {
            'paper': image[id_y:id_y+id_height, id_x:id_x+id_width],
            'warped': cv2.cvtColor(image[id_y:id_y+id_height, id_x:id_x+id_width], cv2.COLOR_BGR2GRAY),
            'thresh': None,  # Will be set by process_section
            'bounds': (id_x, id_y, id_width, id_height)
        }
        
        if self.DEBUG:
            # Draw the regions
            region_vis = image.copy()
            
            # Draw exam model section
            x, y, w, h = exam_model_section['bounds']
            cv2.rectangle(region_vis, (x, y), (x+w, y+h), (255, 0, 255), 3)  # Magenta
            cv2.putText(region_vis, 'EXAM MODEL', (x+10, y+30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 0, 255), 2)
            
            # Draw question sections
            for i, qs in enumerate(question_sections):
                x, y, w, h = qs['bounds']
                cv2.rectangle(region_vis, (x, y), (x+w, y+h), (0, 255, 0), 3)
                cv2.putText(region_vis, f'Q{i+1}', (x+10, y+30),
                          cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
            
            # Draw ID section
            x, y, w, h = id_section['bounds']
            cv2.rectangle(region_vis, (x, y), (x+w, y+h), (0, 0, 255), 3)
            cv2.putText(region_vis, 'ID', (x+10, y+30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
            
            cv2.imwrite('debug_regions.jpg', region_vis)
        
        # Process all sections
        # Process exam model section
        exam_model_section['thresh'] = self.preprocess_image(exam_model_section['paper'], is_id=False)
        
        # Process question sections
        question_data = []
        for i, qs in enumerate(question_sections):
            qs['thresh'] = self.preprocess_image(qs['paper'], is_id=False)
            question_data.append(qs)
        
        # Process ID section
        id_section['thresh'] = self.preprocess_image(id_section['paper'], is_id=True)
        
        return question_data, id_section, exam_model_section
    
    def process_section(self, image, gray, section, section_type):
        try:
            # Get section bounds
            x, y, w, h = section['bounds']
            
            # Extract the section with padding
            padding = 10
            x1 = max(0, x - padding)
            y1 = max(0, y - padding)
            x2 = min(image.shape[1], x + w + padding)
            y2 = min(image.shape[0], y + h + padding)
            
            # Check bounds
            if x1 >= x2 or y1 >= y2:
                if self.DEBUG:
                    print(f"Invalid {section_type} section bounds: ({x1}, {y1}, {x2}, {y2})")
                return None
            
            # Extract section
            section_img = image[y1:y2, x1:x2]
            section_gray = gray[y1:y2, x1:x2]
            
            if section_img is None or section_img.size == 0:
                if self.DEBUG:
                    print(f"Empty {section_type} section image")
                return None
            
            # Calculate the height to skip (top portion with text)
            skip_height = int(section_img.shape[0] * 0.15)  # Skip top 15%
            
            # Crop out the top portion
            section_img = section_img[skip_height:, :]
            section_gray = section_gray[skip_height:, :]
            
            if self.DEBUG:
                cv2.imwrite(f'debug_{section_type}_extracted.jpg', section_img)
            
            # Enhance contrast
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
            enhanced = clahe.apply(section_gray)
            
            if self.DEBUG and enhanced is not None and enhanced.size > 0:
                cv2.imwrite(f'debug_{section_type}_enhanced.jpg', enhanced)
            
            # Denoise
            denoised = cv2.fastNlMeansDenoising(enhanced, None, 10, 7, 21)
            
            if self.DEBUG and denoised is not None and denoised.size > 0:
                cv2.imwrite(f'debug_{section_type}_denoised.jpg', denoised)
            
            # Blur
            blurred = cv2.GaussianBlur(denoised, (5, 5), 0)
            
            if self.DEBUG and blurred is not None and blurred.size > 0:
                cv2.imwrite(f'debug_{section_type}_blurred.jpg', blurred)
            
            # Threshold with different parameters for each section
            if section_type == "id":
                # For ID section - more aggressive thresholding
                thresh = cv2.adaptiveThreshold(
                    blurred, 255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY_INV,
                    21,  # Larger block size
                    8)   # Higher C value
            else:
                # For question section - more sensitive thresholding
                thresh = cv2.adaptiveThreshold(
                    blurred, 255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY_INV,
                    15,
                    4)
            
            if self.DEBUG and thresh is not None and thresh.size > 0:
                cv2.imwrite(f'debug_{section_type}_thresh.jpg', thresh)
            
            # Clean up with morphological operations
            kernel = np.ones((3,3), np.uint8)
            cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)
            cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel, iterations=1)
            
            if self.DEBUG and cleaned is not None and cleaned.size > 0:
                cv2.imwrite(f'debug_{section_type}_cleaned.jpg', cleaned)
            
            return {
                'paper': section_img,
                'thresh': cleaned,
                'warped': section_gray,
                'bounds': (x, y + skip_height, w, h - skip_height)  # Adjusted bounds
            }
            
        except Exception as e:
            if self.DEBUG:
                print(f"Failed to process {section_type} section: {str(e)}")
            return None
    
    def four_point_transform(self, image, pts):
        rect = np.zeros((4, 2), dtype="float32")
        
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        
        (tl, tr, br, bl) = rect
        
        widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        maxWidth = max(int(widthA), int(widthB))
        
        heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        maxHeight = max(int(heightA), int(heightB))
        
        dst = np.array([
            [0, 0],
            [maxWidth - 1, 0],
            [maxWidth - 1, maxHeight - 1],
            [0, maxHeight - 1]], dtype="float32")
        
        M = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
        
        return warped
    
    def preprocess_image(self, image, is_id=False):
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
            
        if self.DEBUG:
            cv2.imwrite(f'debug_{"id" if is_id else "question"}_1_gray.jpg', gray)
        
        # Apply different preprocessing for ID section
        if is_id:
            # Enhance contrast for ID section
            clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8,8))
            gray = clahe.apply(gray)
            
            if self.DEBUG:
                cv2.imwrite(f'debug_{"id" if is_id else "question"}_2_clahe.jpg', gray)
            
            # Denoise
            gray = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
            
            if self.DEBUG:
                cv2.imwrite(f'debug_{"id" if is_id else "question"}_3_denoised.jpg', gray)
            
            # Blur
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            if self.DEBUG:
                cv2.imwrite(f'debug_{"id" if is_id else "question"}_4_blurred.jpg', blurred)
            
            # Try multiple thresholding methods
            # 1. Adaptive thresholding
            thresh1 = cv2.adaptiveThreshold(
                blurred, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY_INV,
                15, 5)
            
            # 2. Otsu's thresholding
            _, thresh2 = cv2.threshold(blurred, 0, 255, 
                                     cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            # Combine both thresholds
            thresh = cv2.bitwise_or(thresh1, thresh2)
            
            if self.DEBUG:
                cv2.imwrite(f'debug_{"id" if is_id else "question"}_5a_thresh1.jpg', thresh1)
                cv2.imwrite(f'debug_{"id" if is_id else "question"}_5b_thresh2.jpg', thresh2)
                cv2.imwrite(f'debug_{"id" if is_id else "question"}_5c_thresh_combined.jpg', thresh)
            
            # Clean up the image with morphological operations
            kernel = np.ones((3,3), np.uint8)
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
            
            if self.DEBUG:
                cv2.imwrite(f'debug_{"id" if is_id else "question"}_6_morph.jpg', thresh)
        else:
            # Regular preprocessing for question section
            # Enhance contrast
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
            gray = clahe.apply(gray)
            
            if self.DEBUG:
                cv2.imwrite(f'debug_{"id" if is_id else "question"}_2_clahe.jpg', gray)
            
            # Denoise
            gray = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
            
            if self.DEBUG:
                cv2.imwrite(f'debug_{"id" if is_id else "question"}_3_denoised.jpg', gray)
            
            # Blur
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            if self.DEBUG:
                cv2.imwrite(f'debug_{"id" if is_id else "question"}_4_blurred.jpg', blurred)
            
            # Try multiple thresholding methods
            # 1. Adaptive thresholding
            thresh1 = cv2.adaptiveThreshold(
                blurred, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY_INV,
                11, 2)
            
            # 2. Otsu's thresholding
            _, thresh2 = cv2.threshold(blurred, 0, 255, 
                                     cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            # Combine both thresholds
            thresh = cv2.bitwise_or(thresh1, thresh2)
            
            if self.DEBUG:
                cv2.imwrite(f'debug_{"id" if is_id else "question"}_5a_thresh1.jpg', thresh1)
                cv2.imwrite(f'debug_{"id" if is_id else "question"}_5b_thresh2.jpg', thresh2)
                cv2.imwrite(f'debug_{"id" if is_id else "question"}_5c_thresh_combined.jpg', thresh)
            
            # Clean up the image
            kernel = np.ones((3,3), np.uint8)
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
            
            if self.DEBUG:
                cv2.imwrite(f'debug_{"id" if is_id else "question"}_6_morph.jpg', thresh)
        
        if self.DEBUG:
            # Save histogram
            plt.figure()
            plt.hist(gray.ravel(), 256, [0, 256])
            plt.savefig(f'debug_{"id" if is_id else "question"}_histogram.png')
            plt.close()
        
        return thresh

    def find_bubbles(self, thresh, min_size=10, max_size=40, is_id=False):
        bubble_cnts = []
        debug_image = None
        if self.DEBUG:
            if thresh is not None and thresh.size > 0:
                debug_image = cv2.cvtColor(thresh.copy(), cv2.COLOR_GRAY2BGR)
                # Save the original thresholded image
                cv2.imwrite(f'debug_{"id" if is_id else "question"}_thresh_input.jpg', thresh)
            else:
                print(f"Warning: Empty {'ID' if is_id else 'question'} section image")
                return []
        
        # Get image dimensions
        h, w = thresh.shape[:2]
        
        # Define grid parameters based on section type
        if is_id:
            rows = 10  # 10 rows
            cols = 10  # 10 columns for digits 0-9
            expected_bubbles = 100  # Total expected bubbles
        else:
            rows = 25  # 25 rows
            cols = 1   # Each section has 1 column
            expected_bubbles = 25  # 25 bubbles per column
        
        # Calculate cell size
        cell_height = h // rows
        cell_width = w // cols
        
        if self.DEBUG:
            print(f"\nProcessing {'ID' if is_id else 'question'} section:")
            print(f"Image size: {w}x{h}")
            print(f"Grid: {rows}x{cols} cells")
            print(f"Cell size: {cell_width}x{cell_height}")
            
            # Create grid visualization
            grid_vis = cv2.cvtColor(thresh.copy(), cv2.COLOR_GRAY2BGR)
            
            # Draw grid
            for i in range(rows + 1):
                y = i * cell_height
                cv2.line(grid_vis, (0, y), (w, y), (0, 255, 0), 1)
            for j in range(cols + 1):
                x = j * cell_width
                cv2.line(grid_vis, (x, 0), (x, h), (0, 255, 0), 1)
            
            if grid_vis is not None and grid_vis.size > 0:
                cv2.imwrite(f'debug_{"id" if is_id else "question"}_grid.jpg', grid_vis)
        
        # Process each cell in the grid
        for row in range(rows):
            for col in range(cols):
                # Calculate cell boundaries with padding
                padding = 2
                x1 = max(0, col * cell_width + padding)
                y1 = max(0, row * cell_height + padding)
                x2 = min(w, (col + 1) * cell_width - padding)
                y2 = min(h, (row + 1) * cell_height - padding)
                
                # Extract cell region
                cell = thresh[y1:y2, x1:x2]
                
                if self.DEBUG:
                    # Save every 10th cell for debugging
                    if (row * cols + col) % 10 == 0 and cell is not None and cell.size > 0:
                        cv2.imwrite(f'debug_{"id" if is_id else "question"}_cell_{row}_{col}.jpg', cell)
                
                # Skip if cell is empty or too small
                if cell is None or cell.size == 0 or cv2.countNonZero(cell) < 5:
                    continue
                
                # Find contours in the cell
                cell_cnts = cv2.findContours(cell.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                cell_cnts = imutils.grab_contours(cell_cnts)
                
                if not cell_cnts:
                    continue
                
                # Find the largest contour in the cell
                c = max(cell_cnts, key=cv2.contourArea)
                
                # Get bounding box relative to cell
                bx, by, bw, bh = cv2.boundingRect(c)
                
                # Convert coordinates to full image space
                x = x1 + bx
                y = y1 + by
                w = bw
                h = bh
                
                # Calculate shape metrics
                area = cv2.contourArea(c)
                perimeter = cv2.arcLength(c, True)
                
                # Skip if too small
                if area < 5 or perimeter < 8:
                    continue
                
                # Calculate circularity
                circularity = 4 * np.pi * area / (perimeter * perimeter) if perimeter > 0 else 0
                
                # Calculate aspect ratio
                ar = w / float(h)
                
                # Calculate extent (area vs bounding box area)
                extent = float(area) / (w * h)
                
                # Calculate solidity
                hull = cv2.convexHull(c)
                hull_area = cv2.contourArea(hull)
                solidity = float(area) / hull_area if hull_area > 0 else 0
                
                # Adjust thresholds based on section
                if is_id:
                    min_circularity = 0.2
                    min_extent = 0.3
                    min_solidity = 0.8
                    size_range = (3, 25)
                else:
                    min_circularity = 0.3
                    min_extent = 0.4
                    min_solidity = 0.8
                    size_range = (5, 35)
                
                # Check if the contour meets bubble criteria
                if (0.5 <= ar <= 1.5 and
                    circularity >= min_circularity and
                    extent >= min_extent and
                    solidity >= min_solidity and
                    size_range[0] <= w <= size_range[1] and
                    size_range[0] <= h <= size_range[1]):
                    
                    # Create mask for this region
                    mask = np.zeros(thresh.shape[:2], dtype="uint8")
                    cv2.rectangle(mask, (x, y), (x + w, y + h), 255, -1)
                    
                    # Calculate fill percentage
                    fill = cv2.countNonZero(cv2.bitwise_and(thresh, thresh, mask=mask))
                    fill_percent = (fill / (w * h)) * 100
                    
                    bubble_cnts.append({
                        'x': x, 'y': y, 'w': w, 'h': h,
                        'row': row, 'col': col,
                        'fill': fill_percent,
                        'circularity': circularity,
                        'area': area
                    })
                    
                    if self.DEBUG:
                        color = (0, 255, 0)
                        cv2.rectangle(debug_image, (x, y), (x + w, y + h), color, 1)
                        cv2.putText(debug_image, f"{fill_percent:.0f}%", 
                                  (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
        
        if self.DEBUG:
            print(f"Found {len(bubble_cnts)} potential bubbles")
            
            # Sort bubbles by row and column for visualization
            sorted_bubbles = sorted(bubble_cnts, key=lambda x: (x['row'], x['col']))
            
            # Create visualization with numbered bubbles
            numbered_vis = cv2.cvtColor(thresh.copy(), cv2.COLOR_GRAY2BGR)
            for i, bubble in enumerate(sorted_bubbles):
                x, y, w, h = bubble['x'], bubble['y'], bubble['w'], bubble['h']
                cv2.rectangle(numbered_vis, (x, y), (x + w, y + h), (0, 255, 0), 1)
                cv2.putText(numbered_vis, str(i+1), 
                          (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
            
            # Save visualizations
            if debug_image is not None and debug_image.size > 0:
                cv2.imwrite(f'debug_{"id" if is_id else "question"}_bubbles.jpg', debug_image)
            if numbered_vis is not None and numbered_vis.size > 0:
                cv2.imwrite(f'debug_{"id" if is_id else "question"}_numbered.jpg', numbered_vis)
            
            # Create clean binary visualization
            binary_vis = np.zeros_like(thresh)
            for bubble in bubble_cnts:
                x, y, w, h = bubble['x'], bubble['y'], bubble['w'], bubble['h']
                cv2.rectangle(binary_vis, (x, y), (x + w, y + h), 255, 1)
            cv2.imwrite(f'debug_{"id" if is_id else "question"}_binary.jpg', binary_vis)
            
            # Print bubble statistics
            print("\nBubble statistics:")
            print(f"Expected bubbles: {expected_bubbles}")
            print(f"Found bubbles: {len(bubble_cnts)}")
            if bubble_cnts:
                areas = [b['area'] for b in bubble_cnts]
                fills = [b['fill'] for b in bubble_cnts]
                print(f"Average area: {np.mean(areas):.1f} px²")
                print(f"Average fill: {np.mean(fills):.1f}%")
                print(f"Fill range: {min(fills):.1f}% - {max(fills):.1f}%")
        
        return bubble_cnts

    def extract_highlighted_section(self, image, thresh):
        # Create a mask for the highlighted bubbles
        mask = cv2.threshold(thresh, 127, 255, cv2.THRESH_BINARY)[1]
        
        # Apply the mask to the original image
        highlighted = cv2.bitwise_and(image, image, mask=mask)
        
        # Enhance contrast
        lab = cv2.cvtColor(highlighted, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        cl = clahe.apply(l)
        enhanced = cv2.merge((cl, a, b))
        enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
        
        return enhanced

    def analyze_bubbles(self, thresh, bubbles, num_rows, num_cols, is_id=False):
        if not bubbles:
            return None
        
        # Convert list of dictionaries to list of tuples for backward compatibility
        bubble_coords = [(b['x'], b['y'], b['w'], b['h']) for b in bubbles]
        
        # Extract coordinates for clustering
        centers = np.array([(x + w/2, y + h/2) for x, y, w, h in bubble_coords])
        
        # Scale coordinates to normalize distances
        scaler = StandardScaler()
        scaled_coords = scaler.fit_transform(centers)
        
        # First cluster by columns
        x_coords = scaled_coords[:, 0].reshape(-1, 1)
        
        # Estimate epsilon based on data distribution
        nbrs = NearestNeighbors(n_neighbors=min(2, len(x_coords))).fit(x_coords)
        distances, _ = nbrs.kneighbors(x_coords)
        eps = max(0.1, np.percentile(distances[:, -1], 90) * 0.5)
        
        if self.DEBUG:
            print(f"Using epsilon={eps:.3f} for column clustering")
        
        # Apply DBSCAN for column detection
        db = DBSCAN(eps=eps, min_samples=3).fit(x_coords)
        column_labels = db.labels_
        
        # Group bubbles by column
        columns = {}
        for i, (x, y, w, h) in enumerate(bubble_coords):
            col_label = column_labels[i]
            if col_label == -1:  # Skip noise points
                continue
            if col_label not in columns:
                columns[col_label] = []
            columns[col_label].append((x, y, w, h))
        
        if self.DEBUG:
            print(f"Found {len(columns)} columns")
            for k in columns:
                print(f"Column {k}: {len(columns[k])} bubbles")
        
        # Sort columns by x-coordinate
        sorted_col_labels = sorted(columns.keys(), 
                                 key=lambda k: np.mean([x for x, _, _, _ in columns[k]]))
        
        # Process each column independently
        grid = {}
        all_row_bounds = []
        
        # Calculate expected number of rows based on actual bubbles
        if is_id:
            expected_rows = 10  # Fixed for ID section
        else:
            # Estimate number of rows from the data
            avg_bubbles_per_col = np.mean([len(col) for col in columns.values()])
            expected_rows = min(100, max(20, int(avg_bubbles_per_col)))
            if self.DEBUG:
                print(f"Estimated {expected_rows} rows based on average {avg_bubbles_per_col:.1f} bubbles per column")
        
        # Process each column
        for col_idx, col_label in enumerate(sorted_col_labels):
            col_bubbles = columns[col_label]
            
            # Sort bubbles in this column by y-coordinate
            col_bubbles.sort(key=lambda b: b[1])
            
            # Get y-coordinates for clustering
            y_coords = np.array([y + h/2 for _, y, _, h in col_bubbles]).reshape(-1, 1)
            
            try:
                # Use DBSCAN for row detection in this column
                scaler_y = StandardScaler()
                scaled_y = scaler_y.fit_transform(y_coords)
                
                # Estimate epsilon for row clustering
                nbrs_y = NearestNeighbors(n_neighbors=min(2, len(scaled_y))).fit(scaled_y)
                distances_y, _ = nbrs_y.kneighbors(scaled_y)
                eps_y = max(0.1, np.percentile(distances_y[:, -1], 90) * 0.5)
                
                if self.DEBUG and col_idx == 0:
                    print(f"Using epsilon={eps_y:.3f} for row clustering in column {col_idx}")
                
                db_y = DBSCAN(eps=eps_y, min_samples=1).fit(scaled_y)
                row_labels = db_y.labels_
                
                # Group bubbles by row
                rows = {}
                for i, (x, y, w, h) in enumerate(col_bubbles):
                    row_label = row_labels[i]
                    if row_label == -1:  # Skip noise points
                        continue
                    if row_label not in rows:
                        rows[row_label] = []
                    rows[row_label].append((x, y, w, h))
                
                if self.DEBUG and col_idx == 0:
                    print(f"Found {len(rows)} rows in column {col_idx}")
                
                # Process each row
                for row_idx, row_bubbles in rows.items():
                    if len(row_bubbles) != 1:  # Skip if not exactly one bubble
                        continue
                    
                    x, y, w, h = row_bubbles[0]
                    
                    # Create mask for this bubble
                    mask = np.zeros(thresh.shape[:2], dtype="uint8")
                    cv2.rectangle(mask, (x, y), (x + w, y + h), 255, -1)
                    
                    # Calculate fill percentage
                    bubble_area = w * h
                    filled_pixels = cv2.countNonZero(cv2.bitwise_and(thresh, thresh, mask=mask))
                    fill_percentage = (filled_pixels / bubble_area) * 100
                    
                    if self.DEBUG and col_idx == 0:
                        print(f"Col {col_idx}, Row {row_idx}: {fill_percentage:.1f}% filled")
                    
                    # Consider it marked if filled above threshold
                    if fill_percentage > 30:  # Lower threshold for better detection
                        if row_idx not in grid:
                            grid[row_idx] = {}
                        grid[row_idx][col_idx] = fill_percentage
                    
                    # Add row bounds
                    padding = 3
                    all_row_bounds.append((
                        x - padding,
                        y - padding,
                        x + w + padding,
                        y + h + padding
                    ))
                
            except Exception as e:
                if self.DEBUG:
                    print(f"Error processing column {col_idx}: {str(e)}")
                continue
        
        # Calculate column boundaries
        column_bounds = []
        if len(bubble_coords) > 0:
            # Calculate mean x-coordinates for each column
            col_centers = [np.mean([x for x, _, _, _ in columns[k]]) 
                         for k in sorted_col_labels]
            sorted_centers = np.sort(col_centers)
            
            # Find min and max y for the entire section
            min_y = min(y for _, y, _, _ in bubble_coords)
            max_y = max(y + h for _, y, _, h in bubble_coords)
            
            # Calculate column boundaries with padding
            padding = 10
            for i in range(len(sorted_centers)):
                if i == 0:
                    left = min(x for x, _, _, _ in bubble_coords) - padding
                else:
                    left = (sorted_centers[i] + sorted_centers[i-1]) / 2
                
                if i == len(sorted_centers) - 1:
                    right = max(x + w for x, _, w, _ in bubble_coords) + padding
                else:
                    right = (sorted_centers[i] + sorted_centers[i+1]) / 2
                
                column_bounds.append((int(left), int(min_y - padding), 
                                   int(right), int(max_y + padding)))
        
        return grid, all_row_bounds, column_bounds

    def visualize_section(self, section_data, bubbles, name, column_bounds=None, filled_bubbles=None):
        if not bubbles:
            return
            
        # Create a color visualization
        if len(section_data.shape) == 2:
            vis_image = cv2.cvtColor(section_data, cv2.COLOR_GRAY2BGR)
        else:
            vis_image = section_data.copy()
            
        # Draw grid lines for better visualization
        h, w = section_data.shape[:2]
        cell_height = h // (10 if name == 'id' else 25)  # Approximate grid size
        cell_width = w // (10 if name == 'id' else 4)
        
        # Draw horizontal grid lines
        for i in range(1, (10 if name == 'id' else 25)):
            y = i * cell_height
            cv2.line(vis_image, (0, y), (w, y), (200, 200, 200), 1)
            
        # Draw vertical grid lines
        for i in range(1, (10 if name == 'id' else 4)):
            x = i * cell_width
            cv2.line(vis_image, (x, 0), (x, h), (200, 200, 200), 1)
        
        # Draw all detected bubbles in green (thin outline)
        for x, y, w, h in bubbles:
            cv2.rectangle(vis_image, (x, y), (x + w, y + h), (0, 255, 0), 1)
            
            # Create mask for this bubble
            mask = np.zeros(section_data.shape[:2], dtype="uint8")
            cv2.rectangle(mask, (x, y), (x + w, y + h), 255, -1)
            
            # Calculate fill percentage
            bubble_area = w * h
            filled_pixels = cv2.countNonZero(cv2.bitwise_and(
                section_data if len(section_data.shape) == 2 else cv2.cvtColor(section_data, cv2.COLOR_BGR2GRAY),
                section_data if len(section_data.shape) == 2 else cv2.cvtColor(section_data, cv2.COLOR_BGR2GRAY),
                mask=mask
            ))
            fill_percentage = (filled_pixels / bubble_area) * 100
            
            # Add fill percentage text
            cv2.putText(vis_image, f"{fill_percentage:.0f}%", 
                      (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 
                      0.4, (0, 0, 255), 1)
        
        # Draw column boundaries if available
        if column_bounds:
            for x1, y1, x2, y2 in column_bounds:
                cv2.rectangle(vis_image, (x1, y1), (x2, y2), (0, 255, 255), 2)
        
        # Draw filled bubbles in blue (thick outline)
        if filled_bubbles:
            for x, y, w, h in filled_bubbles:
                cv2.rectangle(vis_image, (x, y), (x + w, y + h), (255, 0, 0), 2)
        
        # Save visualization
        cv2.imwrite(f'debug_{name}_visualization.jpg', vis_image)
        
        # Create a binary visualization showing just the bubbles
        binary_vis = np.zeros(section_data.shape[:2], dtype="uint8")
        for x, y, w, h in bubbles:
            cv2.rectangle(binary_vis, (x, y), (x + w, y + h), 127, 1)
        if filled_bubbles:
            for x, y, w, h in filled_bubbles:
                cv2.rectangle(binary_vis, (x, y), (x + w, y + h), 255, -1)
        
        cv2.imwrite(f'debug_{name}_binary.jpg', binary_vis)

    def process_image(self, image_path):
        try:
            # Read image
            image = cv2.imread(str(image_path))
            if image is None:
                raise Exception(f"Could not read image: {image_path}")
            
            if self.DEBUG:
                print(f"Image shape: {image.shape}")
                # Save original image
                cv2.imwrite('debug_original.jpg', image)
            
            # Detect and process sections
            question_sections, id_section, exam_model_section = self.detect_sections(image)
            
            if question_sections is None or id_section is None or exam_model_section is None:
                raise Exception("Failed to detect sections")
            
            # Process exam model section
            exam_model = None
            exam_model_bubbles = self.find_bubbles(exam_model_section['thresh'], min_size=10, max_size=35, is_id=False)
            if exam_model_bubbles:
                # For exam model, we expect 5 bubbles in a horizontal line (A, B, C, D, E)
                # Sort bubbles by x-coordinate (left to right)
                exam_model_bubbles_sorted = sorted(
                    [(b['x'], b['y'], b['w'], b['h']) for b in exam_model_bubbles], 
                    key=lambda x: x[0]
                )
                
                # Check each bubble for fill percentage
                for i, (x, y, w, h) in enumerate(exam_model_bubbles_sorted):
                    # Create mask for this bubble
                    mask = np.zeros(exam_model_section['thresh'].shape[:2], dtype="uint8")
                    cv2.rectangle(mask, (x, y), (x + w, y + h), 255, -1)
                    
                    # Calculate fill percentage
                    bubble_area = w * h
                    filled_pixels = cv2.countNonZero(cv2.bitwise_and(
                        exam_model_section['thresh'], exam_model_section['thresh'], mask=mask))
                    fill_percentage = (filled_pixels / bubble_area) * 100
                    
                    if self.DEBUG:
                        print(f"Exam Model Bubble {i} (Model {chr(65+i)}): {fill_percentage:.1f}% filled")
                    
                    # Consider it marked if filled above threshold
                    if fill_percentage > 30:
                        exam_model = self.EXAM_MODEL_KEY.get(i, '?')
                        break  # Take the first marked bubble
            
            # Process bubbles in each question section
            answers = {}
            for i, section in enumerate(question_sections):
                bubbles = self.find_bubbles(section['thresh'], min_size=15, max_size=50, is_id=False)
                if bubbles:
                    grid, row_bounds, col_bounds = self.analyze_bubbles(
                        section['thresh'], bubbles, num_rows=25, num_cols=1)
                    if grid:
                        # Convert grid to answers
                        for row in grid:
                            for col in grid[row]:
                                question_num = i * 25 + row + 1  # Each section has 25 questions, 1-indexed
                                answers[question_num] = self.ANSWER_KEY.get(col, '?')
            
            # Process ID section
            id_bubbles = self.find_bubbles(id_section['thresh'], min_size=8, max_size=30, is_id=True)
            id_number = None
            if id_bubbles:
                grid, row_bounds, col_bounds = self.analyze_bubbles(
                    id_section['thresh'], id_bubbles, num_rows=10, num_cols=10, is_id=True)
                if grid:
                    # Convert grid to ID number
                    id_digits = []
                    for col in range(10):  # Process columns 0-9
                        digit_found = False
                        for row in sorted(grid.keys()):
                            if col in grid[row]:
                                id_digits.append(self.ID_KEY.get(row, '?'))
                                digit_found = True
                                break
                        if not digit_found:
                            id_digits.append('_')  # No digit selected for this column
                    id_number = ''.join(id_digits)
            
            # Save results
            results = {
                'exam_model': exam_model,
                'id_number': id_number,
                'answers': answers
            }
            self.save_to_csv(results)
            
            print("\nProcessing complete!")
            print(f"Exam Model: {exam_model}")
            print(f"ID Number: {id_number}")
            print(f"Questions answered: {len(answers)}")
            print("\nResults have been saved to results.csv")
            
            return results
            
        except Exception as e:
            print(f"Error processing image: {str(e)}")
            raise

    def save_to_csv(self, results, output_path='results.csv'):
        # Prepare data for CSV
        data = {
            'Exam_Model': results['exam_model'],
            'ID': results['id_number'],
            **{f'Q{q}': a for q, a in results['answers'].items()}
        }
        
        # Create DataFrame and save to CSV
        df = pd.DataFrame([data])
        df.to_csv(output_path, index=False)
        
        if self.DEBUG:
            print(f"\nResults saved to {output_path}")
            print(f"\nExam Model: {results['exam_model']}")
            print("First few answers:")
            for q in sorted(results['answers'].keys())[:5]:
                print(f"Q{q}: {results['answers'][q]}")

def main():
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Process bubble sheet images.')
    parser.add_argument('image_path', help='Path to the image file')
    args = parser.parse_args()
    
    reader = BubbleSheetReader()
    
    # Process single image
    try:
        results = reader.process_image(args.image_path)
        reader.save_to_csv(results)
        
        print("\nProcessing complete!")
        print(f"Exam Model: {results['exam_model']}")
        print(f"ID Number: {results['id_number']}")
        print(f"Questions answered: {len(results['answers'])}")
        print("\nResults have been saved to results.csv")
        
    except Exception as e:
        print(f"Error processing image: {str(e)}")

if __name__ == "__main__":
    main() 