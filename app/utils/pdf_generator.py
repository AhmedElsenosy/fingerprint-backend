from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Image, PageBreak
from PIL import Image as PILImage
from datetime import datetime
import os
from typing import List, Dict, Any


async def generate_exam_results_pdf(
    exam_id: str,
    exam_data: Dict[str, Any],
    processed_results: List[Dict[str, Any]],
    scanner_info: Dict[str, Any] = None,
    scan_settings: Dict[str, Any] = None
) -> str:
    """
    Generate a PDF containing all scanned exam paper images.
    
    Args:
        exam_id: The exam identifier
        exam_data: Exam information from the database
        processed_results: List of individual sheet processing results
        scanner_info: Information about the scanner used (not used)
        scan_settings: Scanner settings used for the session (not used)
    
    Returns:
        str: Path to the generated PDF file
    """
    
    # Create output directory if it doesn't exist
    reports_dir = "upload/reports"
    os.makedirs(reports_dir, exist_ok=True)
    
    # Generate unique filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_filename = f"exam_papers_{exam_id}_{timestamp}.pdf"
    pdf_path = os.path.join(reports_dir, pdf_filename)
    
    # Create PDF document
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        rightMargin=20,
        leftMargin=20,
        topMargin=20,
        bottomMargin=20
    )
    
    # Get page dimensions
    page_width, page_height = A4
    available_width = page_width - 40  # Account for margins
    available_height = page_height - 40  # Account for margins
    
    # Build document content - just images
    content = []
    
    # Get all image paths from processed results
    image_paths = []
    for result in processed_results:
        solution_path = result.get('solution_path')
        if solution_path and os.path.exists(solution_path):
            image_paths.append(solution_path)
    
    if not image_paths:
        print("⚠️ No valid image paths found for PDF generation")
        return None
    
    # Add each image to the PDF (one per page)
    for i, image_path in enumerate(image_paths):
        try:
            # Calculate image dimensions to fit page while maintaining aspect ratio
            with PILImage.open(image_path) as pil_img:
                img_width, img_height = pil_img.size
                
                # Calculate scaling to fit within page
                width_scale = available_width / img_width
                height_scale = available_height / img_height
                scale = min(width_scale, height_scale)
                
                # Calculate final dimensions
                final_width = img_width * scale
                final_height = img_height * scale
            
            # Create ReportLab Image object
            img = Image(image_path, width=final_width, height=final_height)
            content.append(img)
            
            # Add page break except for the last image
            if i < len(image_paths) - 1:
                content.append(PageBreak())
                
            print(f"📄 Added image {i+1}/{len(image_paths)}: {os.path.basename(image_path)}")
            
        except Exception as e:
            print(f"⚠️ Failed to add image {image_path}: {str(e)}")
            continue
    
    # Build PDF
    if content:
        doc.build(content)
        print(f"📄 PDF with {len(image_paths)} exam papers generated successfully: {pdf_path}")
        return pdf_path
    else:
        print("❌ No images could be added to PDF")
        return None
