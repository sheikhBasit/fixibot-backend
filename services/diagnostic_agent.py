from groq import Groq
from langchain_core.runnables import RunnableLambda
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

def create_diagnostic_agent(api_key: str):
    try:
        client = Groq(api_key=api_key)

        def run_gemma_chat(inputs: dict) -> str:
            # 1. Extract inputs with safety fallbacks
            if isinstance(inputs, dict):
                system_prompt = inputs.get("system_prompt", "You are a professional mechanic.")
                user_input = inputs.get("input", "")
                context = inputs.get("context", "")
                chat_history = inputs.get("chat_history", [])
                is_simple_response = inputs.get("is_simple_response", False)
            else:
                # Fallback for non-dict inputs (LangChain compatibility)
                system_prompt = "You are a professional mechanic."
                user_input = str(inputs)
                context = ""
                chat_history = []
                is_simple_response = False

            # 2. Model Configuration
            if is_simple_response:
                model = "llama-3.1-8b-instant"
                temperature = 0.0
                max_tokens = 256
            else:
                model = "llama-3.3-70b-versatile"
                temperature = 0.2
                max_tokens = 1024  # Increased to prevent JSON/Response cutoff

            # 3. Build Message List (Correct Order: System -> History -> Current Input)
            messages = []
            
            # A. System Instruction & Technical Context
            # We put the context here so the LLM treats it as "Knowledge" rather than a "User Command"
            full_system_content = f"{system_prompt}"
            if context and "NO_DATA" not in context:
                full_system_content += f"\n\nTECHNICAL REFERENCE DATA:\n{context}\n\nUse the above data to answer the user's request accurately."
            
            messages.append({"role": "system", "content": full_system_content})

            # B. Add Chat History (Limit to last 6 messages to save tokens and maintain focus)
            # Standardize role names to 'user' and 'assistant'
            for msg in chat_history[-6:]:
                role = msg.get("role", "user")
                # Groq expects 'assistant', not 'ai'
                if role == "ai": role = "assistant"
                messages.append({
                    "role": role,
                    "content": msg.get("content", "")
                })

            # C. Add Current User Message
            # We keep this clean so the LLM follows the specific instruction (like "5 bullets only")
            messages.append({"role": "user", "content": user_input})

            # 4. API Call
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    top_p=1,
                    max_completion_tokens=max_tokens,
                    stream=False
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                logger.error(f"Groq API Error: {e}")
                return "I'm having trouble connecting to the diagnostic engine. Please try again in a moment."

        return RunnableLambda(run_gemma_chat)
    except Exception as e:
        logger.error(f"Failed to initialize diagnostic agent: {e}")
        return RunnableLambda(lambda x: "Diagnostic service is currently offline.")