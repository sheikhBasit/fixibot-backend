import logging
from bson import ObjectId, errors as bson_errors
from datetime import datetime, timezone
from fastapi import HTTPException

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
from models.user import UserInDB, UserRole
from database import db
from utils.self_help_record import record_self_help_view, update_helpful_stats

logger = logging.getLogger("self_help")

class SelfHelpService:

    @staticmethod
    async def create_article(article: SelfHelpIn, user: UserInDB):
        if user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
            raise HTTPException(status_code=403, detail="Admins only")
        data = article.model_dump(by_alias=True)
        data["created_at"] = datetime.now(timezone.utc)
        result = await db.self_help_collection.insert_one(data)
        created = await db.self_help_collection.find_one({"_id": result.inserted_id})
        return SelfHelpOut(**created)

    @staticmethod
    async def list_articles():
        articles = await db.self_help_collection.find({"is_active": True}).to_list(length=100)
        return [SelfHelpOut(**a) for a in articles]

    @staticmethod
    async def search_articles(search: SelfHelpSearch):
        query = {}
        if search.keyword:
            query["$or"] = [
                {"question": {"$regex": search.keyword, "$options": "i"}},
                {"answer": {"$regex": search.keyword, "$options": "i"}},
            ]
        if search.tag:
            query["tags"] = search.tag
        if search.is_active is not None:
            query["is_active"] = search.is_active

        results = await db.self_help_collection.find(query).to_list(length=100)
        return [SelfHelpOut(**r) for r in results]

    @staticmethod
    async def get_article(article_id: str):
        try:
            obj_id = ObjectId(article_id)
        except bson_errors.InvalidId:
            raise HTTPException(status_code=400, detail="Invalid ID")
        article = await db.self_help_collection.find_one({"_id": obj_id})
        if not article:
            raise HTTPException(status_code=404, detail="Not found")
        return SelfHelpOut(**article)

    @staticmethod
    async def update_article(article_id: str, update: SelfHelpUpdate, user: UserInDB):
        if user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
            raise HTTPException(status_code=403, detail="Admins only")
        try:
            obj_id = ObjectId(article_id)
        except bson_errors.InvalidId:
            raise HTTPException(status_code=400, detail="Invalid ID")

        data = update.model_dump(exclude_unset=True, by_alias=True)
        result = await db.self_help_collection.update_one({"_id": obj_id}, {"$set": data})
        if result.modified_count == 0:
            raise HTTPException(status_code=400, detail="No changes made")
        updated = await db.self_help_collection.find_one({"_id": obj_id})
        return SelfHelpOut(**updated)

    @staticmethod
    async def delete_article(article_id: str, user: UserInDB):
        if user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
            raise HTTPException(status_code=403, detail="Admins only")
        try:
            obj_id = ObjectId(article_id)
        except bson_errors.InvalidId:
            raise HTTPException(status_code=400, detail="Invalid ID")
        result = await db.self_help_collection.delete_one({"_id": obj_id})
        if result.deleted_count == 1:
            return {"message": "Deleted successfully"}
        raise HTTPException(status_code=404, detail="Not found")

    @staticmethod
    async def submit_feedback(feedback: SelfHelpFeedbackModel, user: UserInDB):
        data = feedback.model_dump(by_alias=True)
        data["user_id"] = user.id
        data["created_at"] = datetime.now(timezone.utc)
        await db.self_help_feedback_collection.insert_one(data)

        analytics_doc = await db.self_help_analytics_collection.find_one({"self_help_id": feedback.self_help_id})
        if analytics_doc:
            analytics = SelfHelpAnalyticsModel(**analytics_doc)
            updated = update_helpful_stats(analytics, feedback.is_helpful)
            await db.self_help_analytics_collection.replace_one({"_id": analytics_doc["_id"]}, updated.model_dump(by_alias=True))
        else:
            model = SelfHelpAnalyticsModel(
                self_help_id=feedback.self_help_id,
                helpful_count=1 if feedback.is_helpful else 0,
                not_helpful_count=0 if feedback.is_helpful else 1,
            )
            await db.self_help_analytics_collection.insert_one(model.model_dump(by_alias=True))

        return {"message": "Feedback submitted"}

    @staticmethod
    async def get_feedback(article_id: str):
        try:
            obj_id = ObjectId(article_id)
        except bson_errors.InvalidId:
            raise HTTPException(status_code=400, detail="Invalid ID")
        feedbacks = await db.self_help_feedback_collection.find({"self_help_id": obj_id}).to_list(length=100)
        return feedbacks

    @staticmethod
    async def get_analytics(article_id: str):
        try:
            obj_id = ObjectId(article_id)
        except bson_errors.InvalidId:
            raise HTTPException(status_code=400, detail="Invalid ID")
        analytics = await db.self_help_analytics_collection.find_one({"self_help_id": obj_id})
        if not analytics:
            raise HTTPException(status_code=404, detail="Not found")
        return SelfHelpAnalyticsModel(**analytics)

    @staticmethod
    async def increment_views(article_id: str):
        try:
            obj_id = ObjectId(article_id)
        except bson_errors.InvalidId:
            raise HTTPException(status_code=400, detail="Invalid ID")

        doc = await db.self_help_analytics_collection.find_one({"self_help_id": obj_id})
        if doc:
            analytics = SelfHelpAnalyticsModel(**doc)
            updated = record_self_help_view(analytics)
            await db.self_help_analytics_collection.replace_one({"_id": doc["_id"]}, updated.model_dump(by_alias=True))
        else:
            new_analytics = SelfHelpAnalyticsModel(
                self_help_id=obj_id,
                views=1,
                last_viewed_at=datetime.now(timezone.utc),
            )
            await db.self_help_analytics_collection.insert_one(new_analytics.model_dump(by_alias=True))

        return {"message": "View counted"}

    @staticmethod
    async def suggest_article(suggestion: SelfHelpSuggestionModel, user: UserInDB):
        data = suggestion.model_dump(by_alias=True)
        data["user_id"] = user.id
        data["created_at"] = datetime.now(timezone.utc)
        await db.self_help_suggestions_collection.insert_one(data)
        return {"message": "Suggestion submitted"}

    @staticmethod
    async def list_suggestions(user: UserInDB):
        if user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
            raise HTTPException(status_code=403, detail="Admins only")
        suggestions = await db.self_help_suggestions_collection.find().to_list(length=100)
        return suggestions

    @staticmethod
    async def review_suggestion(suggestion_id: str, status: SuggestionStatus, user: UserInDB):
        if user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
            raise HTTPException(status_code=403, detail="Admins only")
        try:
            obj_id = ObjectId(suggestion_id)
        except bson_errors.InvalidId:
            raise HTTPException(status_code=400, detail="Invalid ID")
        result = await db.self_help_suggestions_collection.update_one(
            {"_id": obj_id},
            {"$set": {"status": status, "reviewed_by": user.id, "reviewed_at": datetime.now(timezone.utc)}}
        )
        if result.modified_count == 1:
            return {"message": "Suggestion reviewed"}
        raise HTTPException(status_code=404, detail="Suggestion not found")
