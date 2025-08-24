from typing import List, Optional
from fastapi import HTTPException, UploadFile
from datetime import datetime, timezone
from bson import ObjectId, errors as bson_errors
from models.ai_service import (
    AIServiceIn, AIServiceOut, AIServiceUpdate, AIServiceSearch
)
from models.user import UserInDB, UserRole
from database import db
from services.cloudinary import upload_image
import logging

logger = logging.getLogger("ai_service")

valid_transitions = {
    "pending": ["in_progress", "cancelled", "escalated"],
    "in_progress": ["resolved", "cancelled", "escalated"],
    "resolved": [],
    "cancelled": [],
    "escalated": ["in_progress", "resolved", "cancelled"]
}


def is_valid_transition(current: str, new: str) -> bool:
    return new in valid_transitions.get(current, [])


def extract_tags(chat_history: List[dict]) -> List[str]:
    keywords = []
    for msg in chat_history:
        if msg.get("role") == "user":
            for word in msg.get("message", "").split():
                if len(word) > 3:
                    keywords.append(word.lower())
    return list(set(keywords))[:5]


class AIService:
    collection = db.ai_service_collection

    @staticmethod
    async def create(data: AIServiceIn, current_user: UserInDB, files: Optional[List[UploadFile]]) -> AIServiceOut:
        payload = data.model_dump(by_alias=True)
        payload["request_time"] = datetime.now(timezone.utc)
        payload["user_id"] = current_user.id
        if files:
            payload["attachments"] = [await upload_image(f) for f in files]
        payload["auto_tags"] = extract_tags(payload.get("chat_bot_history", []))

        result = await AIService.collection.insert_one(payload)
        saved = await AIService.collection.find_one({"_id": result.inserted_id})
        return AIServiceOut(**saved)

    @staticmethod
    async def get_by_id(service_id: str) -> AIServiceOut:
        try:
            oid = ObjectId(service_id)
        except bson_errors.InvalidId:
            raise HTTPException(status_code=400, detail="Invalid ID format")
        record = await AIService.collection.find_one({"_id": oid})
        if not record:
            raise HTTPException(status_code=404, detail="Service not found")
        record["feedback"] = await db.feedback_collection.find_one({"ai_service_id": oid})
        return AIServiceOut(**record)

    @staticmethod
    async def update(service_id: str, update: AIServiceUpdate, current_user: UserInDB, files: Optional[List[UploadFile]]) -> AIServiceOut:
        try:
            oid = ObjectId(service_id)
        except bson_errors.InvalidId:
            raise HTTPException(status_code=400, detail="Invalid ID format")
        existing = await AIService.collection.find_one({"_id": oid})
        if not existing:
            raise HTTPException(status_code=404, detail="Not found")

        if update.status and not is_valid_transition(existing["status"], update.status):
            raise HTTPException(status_code=400, detail="Invalid status transition")

        update_data = update.model_dump(exclude_unset=True, by_alias=True)
        if files:
            upload_urls = [await upload_image(f) for f in files]
            update_data.setdefault("attachments", existing.get("attachments", []))
            update_data["attachments"].extend(upload_urls)

        if "chat_bot_history" in update_data:
            update_data["auto_tags"] = extract_tags(update_data["chat_bot_history"])

        result = await AIService.collection.update_one({"_id": oid}, {"$set": update_data})
        if result.modified_count == 0:
            raise HTTPException(status_code=400, detail="No changes applied")

        # Audit log
        await db.audit_log_collection.insert_one({
            "entity": "ai_service",
            "entity_id": str(service_id),
            "action": "updated",
            "performed_by": str(current_user.id),
            "timestamp": datetime.now(timezone.utc)
        })

        updated = await AIService.collection.find_one({"_id": oid})
        return AIServiceOut(**updated)

    @staticmethod
    async def delete(service_id: str, current_user: UserInDB):
        try:
            oid = ObjectId(service_id)
        except bson_errors.InvalidId:
            raise HTTPException(status_code=400, detail="Invalid ID format")
        result = await AIService.collection.delete_one({"_id": oid})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Service not found")

        # Audit log
        await db.audit_log_collection.insert_one({
            "entity": "ai_service",
            "entity_id": str(service_id),
            "action": "deleted",
            "performed_by": str(current_user.id),
            "timestamp": datetime.now(timezone.utc)
        })

    @staticmethod
    async def search(search: AIServiceSearch, skip: int, limit: int) -> List[AIServiceOut]:
        q = {}
        for fld in ["user_id", "mechanic_id", "vehicle_id", "status", "priority"]:
            val = getattr(search, fld)
            if val:
                q[fld] = val
        if search.issue_subject:
            q["issue_subject"] = {"$regex": search.issue_subject, "$options": "i"}
        if search.date_from or search.date_to:
            q["request_time"] = {}
            if search.date_from:
                q["request_time"]["$gte"] = search.date_from
            if search.date_to:
                q["request_time"]["$lte"] = search.date_to

        docs = await AIService.collection.find(q).skip(skip).limit(limit).to_list(length=limit)
        return [AIServiceOut(**d) for d in docs]

    @staticmethod
    async def admin_get_all(current_user: UserInDB) -> List[AIServiceOut]:
        if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
            raise HTTPException(status_code=403, detail="Admin access required")
        docs = await AIService.collection.find().to_list(length=1000)
        return [AIServiceOut(**d) for d in docs]

    @staticmethod
    async def admin_get_by_user(user_id: str, current_user: UserInDB) -> List[AIServiceOut]:
        if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
            raise HTTPException(status_code=403, detail="Admin access required")
        try:
            uid = ObjectId(user_id)
        except bson_errors.InvalidId:
            raise HTTPException(status_code=400, detail="Invalid user ID")
        docs = await AIService.collection.find({"user_id": uid}).to_list(length=100)
        return [AIServiceOut(**d) for d in docs]
