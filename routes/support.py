from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.mail import send_help_support_email, send_support_response_email
from config import settings
router = APIRouter()

class SupportRequest(BaseModel):
    name: str
    email: str
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

@router.post("/support/response")
async def send_support_response(
    email: str, 
    name: str, 
    ticket_id: str, 
    response: str
):
    try:
        await send_support_response_email(
            user_email=email,
            user_name=name,
            ticket_id=ticket_id,
            response_message=response
        )
        return {"message": "Support response sent successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to send support response")