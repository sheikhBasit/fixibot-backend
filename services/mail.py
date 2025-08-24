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