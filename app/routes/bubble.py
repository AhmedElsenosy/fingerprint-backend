from io import BytesIO
from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse
import cv2
import numpy as np
import base64
from app.utils.bubble_sheet_processor import process_bubble_sheet

router = APIRouter(prefix="/bubble", tags=["Bubble Processing"])

@router.post("/process")
async def process_bubble_sheet_endpoint(image_file: UploadFile = File(...)):
    """
    Process a bubble sheet image and return the results with visualization.
    This endpoint handles bubble sheet analysis and answer extraction.
    """
    try:
        contents = await image_file.read()
        image = cv2.imdecode(np.frombuffer(contents, np.uint8), cv2.IMREAD_COLOR)

        if image is None:
            return {
                "error": "Could not decode image. Please ensure it's a valid image file.",
                "results": {}
            }

        result = process_bubble_sheet(image)
        visualization_image = result.get("visualization_image")

        if visualization_image is None:
            return {
                "error": "No visualization image returned from processor",
                "results": result.get("results", {})
            }

        # Encode image to PNG and then to base64
        success, buffer = cv2.imencode(".png", visualization_image)
        if not success:
            return {"error": "Failed to encode image"}

        base64_image = base64.b64encode(buffer.tobytes()).decode("utf-8")

        # Build response
        return {
            "image_base64": base64_image,
            "results": result.get("results", {}),
            "success": result.get("success", True),
            "message": result.get("message", "Processing completed successfully")
        }

    except Exception as e:
        return {
            "error": "An error occurred while processing the bubble sheet",
            "details": str(e),
            "results": {}
        }
