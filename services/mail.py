from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from pydantic import EmailStr
from config import settings  # import your settings instance

conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_STARTTLS=settings.MAIL_STARTTLS,
    MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
    USE_CREDENTIALS=True,
)

async def send_verification_email(email_to: EmailStr, otp: str):
    message = MessageSchema(
        subject="Email Verification OTP",
        recipients=[email_to],
        body=f"Your verification OTP is: {otp}. It expires in 15 minutes.",
        subtype="plain"
    )
    fm = FastMail(conf)
    await fm.send_message(message)

async def send_password_reset_email(email_to: EmailStr, otp: str):
    message = MessageSchema(
        subject="Password Reset Request",
        recipients=[email_to],
        body=f"""
        You requested a password reset. 
        Your OTP code is: {otp}
        This code expires in 15 minutes.
        """,
        subtype="plain"
    )
    fm = FastMail(conf)
    await fm.send_message(message)

async def send_help_support_email(
    user_email: EmailStr, 
    user_name: str, 
    subject: str, 
    message_content: str,
    support_email: str = settings.SUPPORT_EMAIL  # Default support email
):
    """
    Send a help and support email from user to support team
    
    Args:
        user_email: Email of the user requesting help
        user_name: Name of the user
        subject: Subject of the support request
        message_content: Detailed message from the user
        support_email: Support team email address
    """
    # Email to support team
    support_message = MessageSchema(
        subject=f"Support Request: {subject}",
        recipients=[support_email],
        body=f"""
        New Support Request Received:
        
        From: {user_name} ({user_email})
        Subject: {subject}
        
        Message:
        {message_content}
        
        ---
        This is an automated support request from the system.
        """,
        subtype="plain"
    )
    
    # Confirmation email to user
    user_confirmation = MessageSchema(
        subject="Support Request Received",
        recipients=[user_email],
        body=f"""
        Dear {user_name},
        
        Thank you for contacting our support team. We have received your request and will get back to you shortly.
        
        Your Request Details:
        Subject: {subject}
        
        We typically respond within 24-48 hours. For urgent matters, please call our support hotline.
        
        Best regards,
        Support Team
        """,
        subtype="plain"
    )
    
    fm = FastMail(conf)
    
    # Send both emails
    await fm.send_message(support_message)
    await fm.send_message(user_confirmation)

async def send_support_response_email(
    user_email: EmailStr,
    user_name: str,
    ticket_id: str,
    response_message: str,
    support_agent: str = "Support Team"
):
    """
    Send a response email from support team to user
    
    Args:
        user_email: Email of the user
        user_name: Name of the user
        ticket_id: Support ticket ID
        response_message: Response message from support
        support_agent: Name of the support agent or team
    """
    message = MessageSchema(
        subject=f"Re: Your Support Request [Ticket: {ticket_id}]",
        recipients=[user_email],
        body=f"""
        Dear {user_name},
        
        Thank you for your patience. Here is our response to your support request:
        
        Ticket ID: {ticket_id}
        
        Response:
        {response_message}
        
        If you have any further questions or need additional assistance, please reply to this email 
        or reference your ticket ID in any future communications.
        
        Best regards,
        {support_agent}
        Support Team
        """,
        subtype="plain"
    )
    
    fm = FastMail(conf)
    await fm.send_message(message)