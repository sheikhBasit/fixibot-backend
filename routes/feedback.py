from asyncio.log import logger
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List
from bson import ObjectId, errors as bson_errors
from datetime import datetime, timezone
from models.feedback import FeedbackIn, FeedbackModel, FeedbackOut, FeedbackUpdate, FeedbackSearch
from models.user import UserInDB, UserRole
from database import db
from utils.user import get_current_user
from services.rating_service import update_mechanic_rating

router = APIRouter(prefix="/feedback", tags=["Feedback"])

# Dependency to get feedback collection
async def get_feedback_collection():
    if db.feedback_collection is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    return db.feedback_collection

# ✅ Create feedback
@router.post("/", response_model=FeedbackOut, summary="Create feedback for a mechanic or service")
async def create_feedback(
    feedback: FeedbackIn,
    current_user: UserInDB = Depends(get_current_user),
    feedback_collection=Depends(get_feedback_collection)
):
    feedback_data = feedback.model_dump(by_alias=True)
    feedback_data["created_at"] = datetime.now(timezone.utc)

    result = await feedback_collection.insert_one(feedback_data)
    created = await feedback_collection.find_one({"_id": result.inserted_id})

    # Update mechanic rating - Fixed: Ensure all datetime objects are timezone-aware
    feedbacks_cursor = feedback_collection.find({"mechanic_id": feedback.mechanic_id})
    feedbacks = await feedbacks_cursor.to_list(length=1000)
    
    # Convert MongoDB documents to FeedbackModel, ensuring datetime consistency
    feedback_models = []
    for fb in feedbacks:
        # Ensure created_at is timezone-aware if it exists
        if 'created_at' in fb and fb['created_at']:
            if fb['created_at'].tzinfo is None:
                fb['created_at'] = fb['created_at'].replace(tzinfo=timezone.utc)
        feedback_models.append(FeedbackModel(**fb))
    
    # This function should not cause the datetime error as it only processes ratings
    update_mechanic_rating(feedback.mechanic_id, feedback_models)

    return FeedbackOut(**created)

# ✅ Get feedback by ID
@router.get("/{feedback_id}", response_model=FeedbackOut, summary="Get feedback by ID")
async def get_feedback_by_id(
    feedback_id: str,
    current_user: UserInDB = Depends(get_current_user),
    feedback_collection=Depends(get_feedback_collection)
):
    try:
        obj_id = ObjectId(feedback_id)
    except bson_errors.InvalidId:
        raise HTTPException(status_code=400, detail="Invalid feedback ID")

    feedback = await feedback_collection.find_one({"_id": obj_id})
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")

    return FeedbackOut(**feedback)

# ✅ Update feedback
@router.put("/{feedback_id}", response_model=FeedbackOut, summary="Update feedback entry")
async def update_feedback(
    feedback_id: str,
    update: FeedbackUpdate,
    current_user: UserInDB = Depends(get_current_user),
    feedback_collection=Depends(get_feedback_collection)
):
    try:
        obj_id = ObjectId(feedback_id)
    except bson_errors.InvalidId:
        raise HTTPException(status_code=400, detail="Invalid feedback ID")

    update_data = update.model_dump(exclude_unset=True, by_alias=True)
    result = await feedback_collection.update_one({"_id": obj_id}, {"$set": update_data})

    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="No changes made")

    updated = await feedback_collection.find_one({"_id": obj_id})
    return FeedbackOut(**updated)

# ✅ Delete feedback
@router.delete("/{feedback_id}", summary="Delete feedback entry")
async def delete_feedback(
    feedback_id: str,
    current_user: UserInDB = Depends(get_current_user),
    feedback_collection=Depends(get_feedback_collection)
):
    try:
        obj_id = ObjectId(feedback_id)
    except bson_errors.InvalidId:
        raise HTTPException(status_code=400, detail="Invalid feedback ID")

    result = await feedback_collection.delete_one({"_id": obj_id})
    if result.deleted_count == 1:
        return {"message": "Feedback deleted successfully"}
    raise HTTPException(status_code=404, detail="Feedback not found")

# ✅ Search feedback (with pagination)
@router.post("/search", response_model=List[FeedbackOut], summary="Search feedback with filters and pagination")
async def search_feedback(
    search: FeedbackSearch,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
    current_user: UserInDB = Depends(get_current_user),
    feedback_collection=Depends(get_feedback_collection)
):
    query = {}
    
    # Simple field queries
    if search.user_id:
        query["user_id"] = search.user_id
    if search.mechanic_id:
        query["mechanic_id"] = search.mechanic_id
    if search.service_id:
        query["service_id"] = search.service_id
    if search.ai_service_id:
        query["ai_service_id"] = search.ai_service_id
    if search.status:
        query["status"] = search.status
    
    # Date range query
    if search.date_from or search.date_to:
        date_query = {}
        if search.date_from:
            date_query["$gte"] = search.date_from
        if search.date_to:
            date_query["$lte"] = search.date_to
        query["created_at"] = date_query
    
    # Rating range query - fixed logic
    rating_query = {}
    if search.min_rating is not None:
        rating_query["$gte"] = search.min_rating
    if search.max_rating is not None:
        rating_query["$lte"] = search.max_rating
    
    if rating_query:
        query["rating"] = rating_query

    try:
        results = await feedback_collection.find(query).skip(skip).limit(limit).to_list(length=limit)
        return [FeedbackOut(**f) for f in results]
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during search")
# ✅ Admin: Get all feedback
@router.get("/admin/all", response_model=List[FeedbackOut], summary="Admin: Get all feedback entries")
async def get_all_feedback(
    current_user: UserInDB = Depends(get_current_user),
    feedback_collection=Depends(get_feedback_collection)
):
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")

    feedbacks = await feedback_collection.find().to_list(length=1000)
    return [FeedbackOut(**fb) for fb in feedbacks]
