from fastapi import APIRouter, Depends
from typing import List
from models.self_help import (
    SelfHelpIn,
    SelfHelpOut,
    SelfHelpUpdate,
    SelfHelpSearch,
    SelfHelpFeedbackModel,
    SelfHelpAnalyticsModel,
    SelfHelpSuggestionModel,
    SuggestionStatus
)
from models.user import UserInDB
from utils.user import get_current_user
from services.self_help import SelfHelpService

router = APIRouter(prefix="/self-help", tags=["Self Help"])

@router.post("/", response_model=SelfHelpOut, summary="Create a new self-help article")
async def create_article(article: SelfHelpIn, current_user: UserInDB = Depends(get_current_user)):
    return await SelfHelpService.create_article(article, current_user)

@router.get("/", response_model=List[SelfHelpOut], summary="List all active self-help articles")
async def list_articles():
    return await SelfHelpService.list_articles()

@router.post("/search", response_model=List[SelfHelpOut], summary="Search self-help articles with filters")
async def search_articles(search: SelfHelpSearch):
    return await SelfHelpService.search_articles(search)

@router.get("/{id}", response_model=SelfHelpOut, summary="Get a self-help article by ID")
async def get_article(id: str):
    return await SelfHelpService.get_article(id)

@router.put("/{id}", response_model=SelfHelpOut, summary="Update an existing self-help article")
async def update_article(id: str, update: SelfHelpUpdate, current_user: UserInDB = Depends(get_current_user)):
    return await SelfHelpService.update_article(id, update, current_user)

@router.delete("/{id}", summary="Delete a self-help article by ID")
async def delete_article(id: str, current_user: UserInDB = Depends(get_current_user)):
    return await SelfHelpService.delete_article(id, current_user)

@router.post("/feedback", summary="Submit feedback on a self-help article")
async def submit_feedback(feedback: SelfHelpFeedbackModel, current_user: UserInDB = Depends(get_current_user)):
    return await SelfHelpService.submit_feedback(feedback, current_user)

@router.get("/feedback/{self_help_id}", summary="Get all feedback for a specific article")
async def get_feedback(self_help_id: str):
    return await SelfHelpService.get_feedback(self_help_id)

@router.get("/analytics/{self_help_id}", response_model=SelfHelpAnalyticsModel, summary="Get analytics for a specific article")
async def get_analytics(self_help_id: str):
    return await SelfHelpService.get_analytics(self_help_id)

@router.patch("/analytics/view/{self_help_id}", summary="Increment view count for an article")
async def increment_views(self_help_id: str):
    return await SelfHelpService.increment_views(self_help_id)

@router.post("/suggestions", summary="Suggest a new self-help article")
async def suggest_article(suggestion: SelfHelpSuggestionModel, current_user: UserInDB = Depends(get_current_user)):
    return await SelfHelpService.suggest_article(suggestion, current_user)

@router.get("/suggestions", summary="Admin: List all user suggestions")
async def list_suggestions(current_user: UserInDB = Depends(get_current_user)):
    return await SelfHelpService.list_suggestions(current_user)

@router.patch("/suggestions/{id}/review", summary="Admin: Review and approve/reject a user suggestion")
async def review_suggestion(id: str, status: SuggestionStatus, current_user: UserInDB = Depends(get_current_user)):
    return await SelfHelpService.review_suggestion(id, status, current_user)
