from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from services.mail import send_help_support_email
from config import settings
router = APIRouter()

class SupportRequest(BaseModel):
    name: str
    email: EmailStr
    subject: str
    message: str

@router.post("/support/request")
async def submit_support_request(request: SupportRequest):
    try:
        await send_help_support_email(
            user_email=request.email,
            user_name=request.name,
            subject=request.subject,
            message_content=request.message
        )
        return {"message": "Support request submitted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to send support request")