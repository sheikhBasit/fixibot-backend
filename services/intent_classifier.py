# from groq import Groq
# from typing import Literal, Optional, List
# import logging
# from config import settings
# from fastapi import HTTPException

# logger = logging.getLogger(__name__)

# class IntentClassifier:
#     """Classify user intent to determine processing path"""
    
#     def __init__(self, api_key: str):
#         self.client = Groq(api_key=api_key)
#         self.intent_categories = [
#             "greeting", "small_talk", "technical_question", 
#             "command", "vehicle_diagnosis", "other"
#         ]
    
#     async def classify_intent(self, message: str, chat_history: List = None) -> str:
#         """Classify user intent using a fast LLM"""
#         try:
#             # Use chat history for context if available
#             history_context = ""
#             if chat_history:
#                 # Extract last 4 messages for context
#                 last_messages = []
#                 for msg in chat_history[-4:]:
#                     if hasattr(msg, 'content'):
#                         last_messages.append(f"{getattr(msg, 'role', 'user')}: {msg.content}")
#                     elif isinstance(msg, dict) and 'content' in msg:
#                         last_messages.append(f"{msg.get('role', 'user')}: {msg['content']}")
                
#                 history_context = "\n".join(last_messages)
            
#             prompt = f"""
#             Analyze this user message and classify its intent. Choose ONLY from these categories:
#             {', '.join(self.intent_categories)}
            
#             Chat History (for context):
#             {history_context}
            
#             User Message: "{message}"
            
#             Respond with ONLY the intent category name, nothing else.
#             """
            
#             response = self.client.chat.completions.create(
#                 model="llama-3.1-8b-instant",
#                 messages=[
#                     {"role": "system", "content": "You are an intent classification expert. Respond with only the category name."},
#                     {"role": "user", "content": prompt}
#                 ],
#                 temperature=0.2,
#                 max_tokens=20
#             )
            
#             intent = response.choices[0].message.content.strip().lower()
            
#             # Validate the response is a known category
#             if intent in self.intent_categories:
#                 return intent
#             else:
#                 # Default to technical_question if classification fails
#                 return "technical_question"
                
#         except Exception as e:
#             logger.error(f"Intent classification failed: {e}")
#             return "technical_question"  # Fallback to RAG

# def get_intent_classifier(request):
#     """Dependency injection for intent classifier"""
#     classifier = getattr(request.app.state, "intent_classifier", None)
#     if not classifier:
#         raise HTTPException(status_code=500, detail="Intent classifier not initialized")
#     return classifier


# services/sandwich_processor.py
from groq import Groq
import logging
import json
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class SandwichProcessor:
    """
    Handles Step 1 (Input Translation + Intent) and Step 3 (Output Translation).
    Uses fast Llama-3.1-8b-instant model.
    """
    
    def __init__(self, api_key: str):
        self.client = Groq(api_key=api_key)
        self.model = "llama-3.1-8b-instant"
        self.intent_categories = [
            "greeting", "small_talk", "technical_question", 
            "command", "vehicle_diagnosis", "other"
        ]

    async def process_input(self, user_text: str, language_hint: Optional[str] = None, chat_history: list = None) -> Dict[str, Any]:
        """
        Step 1: Translate to English + Classify Intent + Detect Language
        """
        try:
            # Context builder for better intent classification
            history_context = ""
            if chat_history:
                last_msgs = chat_history[-3:]
                history_context = "\n".join([f"{msg.role}: {msg.content}" for msg in last_msgs])

            system_prompt = f"""
            You are the 'Input Processor' for an automotive AI. 
            Your task is to analyze the User Input and return a JSON object.
            
            Steps:
            1. Detect the language of the User Input (e.g., Urdu, English, Spanish).
            2. Translate the User Input into clear, technical English. 
            3. Classify the intent into one of: {self.intent_categories}.
            
            Rules:
            - If the user provides a language hint '{language_hint}', prioritize that for detection logic.
            - If the input is already English, the translation is the same as input.
            - JSON Format ONLY. No markdown, no explanations.
            
            Output Structure:
            {{
                "detected_language": "string",
                "english_translation": "string",
                "intent": "string",
                "confidence": float
            }}
            """

            user_prompt = f"Chat History Context:\n{history_context}\n\nUser Input: {user_text}"

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
                max_tokens=256
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Fallback defaults if JSON is partial
            return {
                "detected_language": result.get("detected_language", "English"),
                "english_translation": result.get("english_translation", user_text),
                "intent": result.get("intent", "technical_question").lower(),
                "original_input": user_text
            }

        except Exception as e:
            logger.error(f"Sandwich Input Processing failed: {e}")
            # Fallback: Assume English, Intent unknown
            return {
                "detected_language": "unknown",
                "english_translation": user_text,
                "intent": "technical_question",
                "original_input": user_text
            }

    async def translate_output(self, english_response: str, target_language: str) -> str:
        """
        Step 3: Translate the Brain's response back to the user's language.
        Uses a larger, more capable model for better translation quality.
        """
        # Optimization: Don't translate if target is English
        if not target_language or target_language.lower() in ["english", "en", "eng"]:
            return english_response

        try:
            system_prompt = f"""You are a professional automotive translator specializing in technical automotive diagnostics.

Your task: Translate the following automotive diagnostic response from English into {target_language}.

CRITICAL INSTRUCTIONS:
1. PRESERVE the exact structure: Solution 1, Solution 2, etc. with bullet points
2. DO NOT condense, merge, or rephrase paragraphs
3. Maintain ALL bold formatting (**text**)
4. Keep technical terms in English where they are industry standard (ECU, OBDII, ABS, etc.)
5. Use natural {target_language} for explanations and instructions
6. AVOID repetition and word loops - translate each phrase once correctly
7. If translating to Urdu: Use proper Urdu script, avoid word repetition
8. Output ONLY the translated response, no explanations or metadata

Remember: Each phrase should appear ONCE. No repetition of words or phrases."""

            # Use a more capable model for translation (70B model for better quality)
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Translate this automotive response:\n\n{english_response}"}
                ],
                temperature=0.3,
                max_tokens=2048,
                top_p=0.9
            )
            
            translated = response.choices[0].message.content.strip()
            
            # Safety check: Detect if translation got corrupted (excessive repetition)
            if self._detect_corrupted_translation(translated):
                logger.warning(f"Corrupted translation detected, using fallback with simple model")
                # Fallback to simpler, direct translation
                return await self._fallback_translate(english_response, target_language)
            
            return translated

        except Exception as e:
            logger.error(f"Sandwich Output Translation failed: {e}", exc_info=True)
            # Try fallback translation
            try:
                return await self._fallback_translate(english_response, target_language)
            except:
                return english_response  # Last resort: return English

    def _detect_corrupted_translation(self, text: str) -> bool:
        """Detect if translation is corrupted (stuck in word loops)"""
        # Check for excessive repetition of short words/phrases
        words = text.split()
        if len(words) < 10:
            return False
        
        # Check if same word appears too frequently in sequence
        for i in range(len(words) - 3):
            word = words[i]
            if len(word) > 2:  # Skip short words like "the", "is", etc
                count = sum(1 for j in range(i, min(i + 10, len(words))) if words[j] == word)
                if count >= 5:  # Same word appearing 5+ times in 10 word window
                    logger.warning(f"Detected word loop: '{word}' repeated {count} times")
                    return True
        
        return False

    async def _fallback_translate(self, english_response: str, target_language: str) -> str:
        """Fallback translation using a different approach"""
        try:
            system_prompt = f"""Translate this automotive diagnostic into {target_language}. Keep structure simple. Use clear, direct language."""
            
            response = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",  # Faster, simpler model for fallback
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": english_response}
                ],
                temperature=0.2,
                max_tokens=1024
            )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Fallback translation also failed: {e}")
            return english_response
