import cv2
import numpy as np
from typing import Optional, Dict, Any

def detect_exam_model(image_path: str) -> Dict[str, Any]:
    """
    Detect the exam model number (1, 2, or 3) from the bubble sheet image.
    
    The model selection is at the top of the bubble sheet with 3 circles.
    Students fill one circle to indicate which model they're taking.
    
    Args:
        image_path: Path to the bubble sheet image
        
    Returns:
        Dict containing:
        - model_number: The detected model (1, 2, or 3), or None if not detected
        - confidence: Confidence score (0.0 to 1.0)
        - message: Description of detection result
        - debug_info: Additional debugging information
    """
    try:
        # Read the image
        image = cv2.imread(image_path)
        if image is None:
            return {
                "model_number": None,
                "confidence": 0.0,
                "message": "Could not read the image file",
                "debug_info": {"error": "Image loading failed"}
            }
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Get image dimensions
        height, width = gray.shape
        
        # Define region of interest (ROI) for model selection area
        # The model circles are typically in the top portion of the image
        # Made more flexible to catch circles in different positions
        roi_top = int(height * 0.02)    # Start from 2% of image height (was 5%)
        roi_bottom = int(height * 0.35)  # End at 35% of image height (was 25%)
        roi_left = int(width * 0.2)     # Start from 20% of image width (was 30%)
        roi_right = int(width * 0.8)    # End at 80% of image width (was 70%)
        
        # Extract ROI
        roi = gray[roi_top:roi_bottom, roi_left:roi_right]
        
        # Apply threshold to make circles more visible
        _, thresh = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Find circles using HoughCircles
        circles = cv2.HoughCircles(
            thresh,
            cv2.HOUGH_GRADIENT,
            dp=1,
            minDist=30,
            param1=50,
            param2=30,
            minRadius=10,
            maxRadius=50
        )
        
        if circles is None:
            return {
                "model_number": None,
                "confidence": 0.0,
                "message": "No model circles detected in the image",
                "debug_info": {"roi_shape": roi.shape, "circles_found": 0}
            }
        
        circles = np.round(circles[0, :]).astype("int")
        
        # Sort circles by x-coordinate (left to right)
        circles = sorted(circles, key=lambda c: c[0])
        
        if len(circles) < 3:
            return {
                "model_number": None,
                "confidence": 0.5,
                "message": f"Found {len(circles)} circles, expected 3 model circles",
                "debug_info": {"circles_found": len(circles), "circles": circles.tolist()}
            }
        
        # Take the first 3 circles (should be the model selection circles)
        model_circles = circles[:3]
        
        # Check which circle is filled by analyzing the darkness inside each circle
        model_scores = []
        for i, (x, y, r) in enumerate(model_circles):
            # Create a mask for the circle
            mask = np.zeros(roi.shape, dtype=np.uint8)
            cv2.circle(mask, (x, y), r - 5, 255, -1)  # Slightly smaller radius to avoid edge effects
            
            # Calculate the mean intensity inside the circle
            # Lower values indicate darker (filled) circles
            mean_intensity = cv2.mean(thresh, mask=mask)[0]
            
            # Calculate fill ratio (higher values indicate more filled)
            fill_ratio = mean_intensity / 255.0
            
            model_scores.append({
                "model_number": i + 1,
                "fill_ratio": fill_ratio,
                "mean_intensity": mean_intensity,
                "circle_pos": (x, y, r)
            })
        
        # Find the most filled circle (highest fill ratio)
        best_model = max(model_scores, key=lambda x: x["fill_ratio"])
        
        # Set confidence based on how clearly filled the circle is
        confidence = min(best_model["fill_ratio"], 1.0)
        
        # Require minimum confidence to detect a model
        if confidence < 0.3:
            return {
                "model_number": None,
                "confidence": confidence,
                "message": "Model circles detected but none appear to be clearly filled",
                "debug_info": {
                    "model_scores": model_scores,
                    "best_fill_ratio": best_model["fill_ratio"]
                }
            }
        
        return {
            "model_number": best_model["model_number"],
            "confidence": confidence,
            "message": f"Detected Model {best_model['model_number']} with {confidence:.2f} confidence",
            "debug_info": {
                "model_scores": model_scores,
                "best_model": best_model,
                "roi_coordinates": (roi_left, roi_top, roi_right, roi_bottom)
            }
        }
        
    except Exception as e:
        return {
            "model_number": None,
            "confidence": 0.0,
            "message": f"Error during model detection: {str(e)}",
            "debug_info": {"error": str(e)}
        }


def detect_model_from_image_array(image: np.ndarray) -> Dict[str, Any]:
    """
    Detect exam model from numpy image array (for already loaded images).
    
    Args:
        image: OpenCV image as numpy array
        
    Returns:
        Same format as detect_exam_model()
    """
    try:
        if image is None:
            return {
                "model_number": None,
                "confidence": 0.0,
                "message": "Invalid image array provided",
                "debug_info": {"error": "Image array is None"}
            }
        
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Get image dimensions
        height, width = gray.shape
        
        # Define ROI for model selection area
        roi_top = int(height * 0.05)
        roi_bottom = int(height * 0.25)
        roi_left = int(width * 0.3)
        roi_right = int(width * 0.7)
        
        # Extract ROI
        roi = gray[roi_top:roi_bottom, roi_left:roi_right]
        
        # Apply threshold
        _, thresh = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Find circles
        circles = cv2.HoughCircles(
            thresh,
            cv2.HOUGH_GRADIENT,
            dp=1,
            minDist=30,
            param1=50,
            param2=30,
            minRadius=10,
            maxRadius=50
        )
        
        if circles is None:
            return {
                "model_number": None,
                "confidence": 0.0,
                "message": "No model circles detected",
                "debug_info": {"roi_shape": roi.shape}
            }
        
        circles = np.round(circles[0, :]).astype("int")
        circles = sorted(circles, key=lambda c: c[0])
        
        if len(circles) < 3:
            return {
                "model_number": None,
                "confidence": 0.5,
                "message": f"Found {len(circles)} circles, expected 3",
                "debug_info": {"circles_found": len(circles)}
            }
        
        # Analyze first 3 circles
        model_circles = circles[:3]
        model_scores = []
        
        for i, (x, y, r) in enumerate(model_circles):
            mask = np.zeros(roi.shape, dtype=np.uint8)
            cv2.circle(mask, (x, y), r - 5, 255, -1)
            
            mean_intensity = cv2.mean(thresh, mask=mask)[0]
            fill_ratio = mean_intensity / 255.0
            
            model_scores.append({
                "model_number": i + 1,
                "fill_ratio": fill_ratio,
                "mean_intensity": mean_intensity
            })
        
        best_model = max(model_scores, key=lambda x: x["fill_ratio"])
        confidence = min(best_model["fill_ratio"], 1.0)
        
        if confidence < 0.3:
            return {
                "model_number": None,
                "confidence": confidence,
                "message": "Model circles detected but none clearly filled",
                "debug_info": {"model_scores": model_scores}
            }
        
        return {
            "model_number": best_model["model_number"],
            "confidence": confidence,
            "message": f"Detected Model {best_model['model_number']}",
            "debug_info": {
                "model_scores": model_scores,
                "best_model": best_model
            }
        }
        
    except Exception as e:
        return {
            "model_number": None,
            "confidence": 0.0,
            "message": f"Error during model detection: {str(e)}",
            "debug_info": {"error": str(e)}
        }
