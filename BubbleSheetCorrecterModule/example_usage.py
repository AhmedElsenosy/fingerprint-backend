#!/usr/bin/env python3

"""
Example usage of the bubble sheet processor library.

This script shows how to use the bubble_sheet_processor as a library
to process bubble sheets and get results in different formats.
"""

import cv2
from bubble_sheet_processor import process_bubble_sheet, print_processing_summary

def main():
    print("🔍 Bubble Sheet Processor - Example Usage")
    print("=" * 50)
    
    # Example 1: Process a single image
    print("\n📄 Processing scanned bubble sheet...")
    result = process_bubble_sheet("scan_output copy.png")
    
    if result['success']:
        # Access the visualization image
        vis_image = result['visualization_image']
        print(f"✅ Visualization image shape: {vis_image.shape}")
        
        # Access the detailed results
        results = result['results']
        summary = results['summary']
        
        # Print some key information
        print(f"📊 Questions answered: {summary['questions_answered']}/{summary['total_questions']}")
        print(f"📝 Completion rate: {summary['completion_rate']}%")
        
        if 'exam_model' in summary:
            em = summary['exam_model']
            print(f"🎯 Exam Model: {em['value']} (Valid: {em['is_valid']})")
            print(f"   Fill percentages: {[f'{p:.1f}%' for p in em['fill_percentages']]}")
        
        # Access individual question results
        grade_data = results['grade_data']
        answered_questions = [a for a in grade_data['answers'] if a['answer']]
        print(f"📝 Sample answered questions: {len(answered_questions)}")
        
        # Files generated
        print(f"\n💾 Generated files:")
        print(f"   📊 CSV: {result['csv_path']}")
        print(f"   📄 JSON: {result['json_path']}")
        print(f"   🖼️ Visualization: {result['visualization_path']}")
        
    else:
        print(f"❌ Processing failed: {result['message']}")
    
    print("\n" + "=" * 50)
    
    # Example 2: Process reference image for comparison
    print("\n📄 Processing reference bubble sheet...")
    ref_result = process_bubble_sheet("Arabic@4x-20.jpg")
    
    if ref_result['success']:
        ref_summary = ref_result['results']['summary']
        print(f"📊 Reference completion: {ref_summary['completion_rate']}%")
        
        if 'exam_model' in ref_summary:
            ref_em = ref_summary['exam_model']
            print(f"🎯 Reference Exam Model: {ref_em['value']} (Valid: {ref_em['is_valid']})")
    
    print("\n" + "=" * 50)
    
    # Example 3: Compare results
    if result['success'] and ref_result['success']:
        print("\n🔍 Comparison:")
        
        scanned_em = result['results']['summary'].get('exam_model', {})
        ref_em = ref_result['results']['summary'].get('exam_model', {})
        
        print(f"   Scanned: Model {scanned_em.get('value', 'N/A')}")
        print(f"   Reference: Model {ref_em.get('value', 'N/A')}")
        
        if scanned_em.get('fill_percentages') and ref_em.get('fill_percentages'):
            print("   Fill percentage differences:")
            for i, (s_fill, r_fill) in enumerate(zip(scanned_em['fill_percentages'], ref_em['fill_percentages'])):
                model_letter = chr(65 + i)
                diff = s_fill - r_fill
                print(f"     Model {model_letter}: {diff:+.1f}% (scanned vs reference)")
    
    print("\n✅ Example completed!")

if __name__ == "__main__":
    main() 