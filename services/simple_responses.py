import random
from typing import Optional

class SimpleResponseGenerator:
    """Generate simple responses for common intents"""
    
    GREETING_RESPONSES = [
        "Hello! I'm your vehicle assistant. How can I help with your car today?",
        "Hi there! What vehicle issue can I help you with?",
        "Greetings! I'm here to help with any vehicle questions or problems.",
        "Hey! Ready to assist with your vehicle needs.",
        "Good day! I'm your automotive assistant. What can I help you with?"
    ]
    
    SMALL_TALK_RESPONSES = [
        "I'm doing well, thank you! Ready to help with your vehicle.",
        "I'm here and ready to assist with any car questions you have!",
        "Great to chat! Let me know if you have any vehicle concerns.",
        "I'm functioning perfectly! How can I assist you today?",
        "All systems operational! What vehicle issue are you facing?"
    ]
    
    THANKS_RESPONSES = [
        "You're welcome! Happy to help with your vehicle needs.",
        "Glad I could assist! Feel free to ask if you have more questions.",
        "Anytime! I'm here to help with all your vehicle concerns.",
        "My pleasure! Don't hesitate to reach out if you need more help.",
        "You're very welcome! Safe driving!"
    ]
    
    FAREWELL_RESPONSES = [
        "Goodbye! Feel free to reach out if you have more vehicle questions.",
        "See you later! Drive safe and take care.",
        "Farewell! Remember to schedule regular maintenance.",
        "Bye for now! Don't hesitate to ask if more issues come up.",
        "Take care! I'll be here if you need automotive advice."
    ]
    
    @classmethod
    def get_response(cls, intent: str, user_message: str) -> Optional[str]:
        """Get appropriate simple response"""
        user_message_lower = user_message.lower()
        
        if intent == "greeting":
            return random.choice(cls.GREETING_RESPONSES)
        
        elif intent == "small_talk":
            if any(word in user_message_lower for word in ["how are you", "how do you do", "how's it going"]):
                return random.choice(cls.SMALL_TALK_RESPONSES)
            elif any(word in user_message_lower for word in ["thank", "thanks", "appreciate"]):
                return random.choice(cls.THANKS_RESPONSES)
            elif any(word in user_message_lower for word in ["bye", "goodbye", "see you", "farewell"]):
                return random.choice(cls.FAREWELL_RESPONSES)
            elif any(word in user_message_lower for word in ["hello", "hi", "hey"]):
                return random.choice(cls.GREETING_RESPONSES)
        
        return None