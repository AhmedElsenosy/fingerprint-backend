#!/usr/bin/env python3

import cv2
import numpy as np
import os
from typing import Dict, Optional, Tuple
from app.utils.bubble_sheet_processor import process_bubble_sheet


class ExamCorrector:
    """
    Service class for correcting student exams by comparing their bubble sheet 
    solutions with the exam's answer key using image processing.
    """
    
    def __init__(self):
        self.reference_data_file = 'BubbleSheetCorrecterModule/reference_data.json'
        self.id_reference_file = 'BubbleSheetCorrecterModule/id_coordinates.json'
        self.exam_models_file = 'BubbleSheetCorrecterModule/exam_models.json'
        self.exam_model_key = 'exam_model_aruco'
    
    def correct_exam(
        self, 
        student_solution_path: str, 
        exam_solution_path: str,
        final_degree: int
    ) -> Dict:
        """
        Correct a student's exam by comparing their solution with the answer key.
        
        Args:
            student_solution_path: Path to student's bubble sheet image
            exam_solution_path: Path to exam's answer key bubble sheet image
            final_degree: Maximum possible score for the exam
            
        Returns:
            Dict containing:
            - success: bool
            - student_score: float (calculated score)
            - percentage: float (percentage score)
            - total_questions: int
            - correct_answers: int
            - student_answers: list
            - correct_answers_key: list
            - message: str
        """
        
        try:
            # Process student's solution
            student_result = self._process_bubble_sheet(student_solution_path)
            if not student_result['success']:
                return {
                    'success': False,
                    'message': f"Failed to process student solution: {student_result['message']}"
                }
            
            # Process exam's answer key
            exam_result = self._process_bubble_sheet(exam_solution_path)
            if not exam_result['success']:
                return {
                    'success': False,
                    'message': f"Failed to process exam answer key: {exam_result['message']}"
                }
            
            # Extract answers from both sheets
            student_answers = self._extract_answers(student_result['results'])
            correct_answers = self._extract_answers(exam_result['results'])
            
            # Compare answers and calculate score
            score_result = self._calculate_score(
                student_answers, 
                correct_answers, 
                final_degree
            )
            
            return {
                'success': True,
                'student_score': score_result['score'],
                'percentage': score_result['percentage'],
                'total_questions': score_result['total_questions'],
                'correct_answers': score_result['correct_count'],
                'student_answers': student_answers,
                'correct_answers_key': correct_answers,
                'comparison_details': score_result['details'],
                'message': 'Exam corrected successfully'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f"Error during exam correction: {str(e)}"
            }
    
    def _process_bubble_sheet(self, image_path: str) -> Dict:
        """
        Process a bubble sheet image using the existing bubble sheet processor.
        
        Args:
            image_path: Path to the bubble sheet image
            
        Returns:
            Dict with processing results
        """
        try:
            # Check if file exists
            if not os.path.exists(image_path):
                return {
                    'success': False,
                    'message': f"Image file not found: {image_path}"
                }
            
            # Load image
            image = cv2.imread(image_path)
            if image is None:
                return {
                    'success': False,
                    'message': f"Could not load image: {image_path}"
                }
            
            # Process using existing bubble sheet processor
            result = process_bubble_sheet(
                image=image,
                reference_data_file=self.reference_data_file,
                id_reference_file=self.id_reference_file,
                exam_models_file=self.exam_models_file,
                exam_model_key=self.exam_model_key
            )
            
            return result
            
        except Exception as e:
            return {
                'success': False,
                'message': f"Error processing bubble sheet: {str(e)}"
            }
    
    def _extract_answers(self, processing_results: Dict) -> list:
        """
        Extract the answers from bubble sheet processing results.
        
        Args:
            processing_results: Results from bubble sheet processing
            
        Returns:
            List of answers (A, B, C, D, E, or None for unanswered)
        """
        try:
            if not processing_results or 'grade_data' not in processing_results:
                return []
            
            answers = []
            grade_data = processing_results['grade_data']
            
            if 'answers' in grade_data:
                for answer_data in grade_data['answers']:
                    answer = answer_data.get('answer')
                    # Handle special cases
                    if answer == 'multiple':
                        answer = None  # Treat multiple answers as incorrect
                    elif not answer or answer == '':
                        answer = None  # Unanswered
                    
                    answers.append(answer)
            
            return answers
            
        except Exception as e:
            print(f"Error extracting answers: {str(e)}")
            return []
    
    def _calculate_score(
        self, 
        student_answers: list, 
        correct_answers: list, 
        final_degree: int
    ) -> Dict:
        """
        Calculate the student's score by comparing their answers with correct answers.
        
        Args:
            student_answers: List of student's answers
            correct_answers: List of correct answers
            final_degree: Maximum possible score
            
        Returns:
            Dict with score calculation results
        """
        try:
            # Ensure both lists have the same length
            max_questions = max(len(student_answers), len(correct_answers))
            
            # Pad shorter list with None values
            while len(student_answers) < max_questions:
                student_answers.append(None)
            while len(correct_answers) < max_questions:
                correct_answers.append(None)
            
            # Compare answers
            correct_count = 0
            comparison_details = []
            
            for i, (student_ans, correct_ans) in enumerate(zip(student_answers, correct_answers)):
                is_correct = (
                    student_ans is not None and 
                    correct_ans is not None and 
                    str(student_ans).upper() == str(correct_ans).upper()
                )
                
                if is_correct:
                    correct_count += 1
                
                comparison_details.append({
                    'question': i + 1,
                    'student_answer': student_ans,
                    'correct_answer': correct_ans,
                    'is_correct': is_correct
                })
            
            # Calculate score and percentage using final_degree as the total possible score
            # The logic: if student gets all questions correct, they get final_degree points and 100%
            if final_degree > 0:
                # Use final_degree as the total questions for percentage calculation
                # This means: percentage = (correct_count / final_degree) * 100
                # And score = correct_count (since each correct answer = 1 point toward final_degree)
                percentage = (correct_count / final_degree) * 100
                score = correct_count  # Each correct answer is worth 1 point
            else:
                percentage = 0
                score = 0
            
            return {
                'score': round(score, 2),
                'percentage': round(percentage, 2),
                'correct_count': correct_count,
                'total_questions': final_degree,  # Use final_degree as total questions
                'details': comparison_details
            }
            
        except Exception as e:
            print(f"Error calculating score: {str(e)}")
            return {
                'score': 0,
                'percentage': 0,
                'correct_count': 0,
                'total_questions': 0,
                'details': []
            }


# Convenience function for easy usage
def correct_student_exam(
    student_solution_path: str, 
    exam_solution_path: str, 
    final_degree: int
) -> Dict:
    """
    Convenience function to correct a student's exam.
    
    Args:
        student_solution_path: Path to student's bubble sheet image
        exam_solution_path: Path to exam's answer key bubble sheet image  
        final_degree: Maximum possible score for the exam
        
    Returns:
        Dict with correction results
    """
    corrector = ExamCorrector()
    return corrector.correct_exam(student_solution_path, exam_solution_path, final_degree)
