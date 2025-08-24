from typing import List, Optional, Tuple
from models.feedback import FeedbackModel
from utils.py_object import PyObjectId

def update_mechanic_rating(mechanic_id: PyObjectId, feedbacks: List[FeedbackModel]) -> Tuple[Optional[float], int]:
    # Filter out feedbacks with None ratings and ensure we're working with valid data
    valid_ratings = [f.rating for f in feedbacks if f.rating is not None]
    
    if valid_ratings:
        average = sum(valid_ratings) / len(valid_ratings)
        total = len(valid_ratings)
        return round(average, 2), total
    return None, 0