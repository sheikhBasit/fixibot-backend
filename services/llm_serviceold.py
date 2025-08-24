from groq import Groq
from groq.types.chat.chat_completion import ChatCompletion 
from langchain_core.runnables import RunnableLambda
from langchain_core.runnables.base import RunnableLambda as RunnableLambdaType
from typing import Dict, Any, Optional, Union, Literal, List, cast
from pydantic import BaseModel
from config import settings
import logging
from typing import TypedDict
from threading import Lock
logger = logging.getLogger(__name__)
from typing import Union


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str

class MessageDict(TypedDict):
    role: str
    content: str

class ChatInputDict(TypedDict, total=False):
    system_prompt: str
    input: str
    context: str
    chat_history: List[Union[Dict[str, str], ChatMessage]]

_diagnostic_agent: Optional[RunnableLambda[Union[ChatInputDict, Any], str]] = None

_lock = Lock()

def _create_diagnostic_agent() -> RunnableLambdaType[Union[ChatInputDict, Any], str]:
    """
    Returns a runnable Lambda that processes chat inputs using the Groq API.
    
    Returns:
        RunnableLambda that takes either a dict or ChatPromptValue and returns a string response
    """
    try:
        client = Groq(api_key=settings.GROQ_API_KEY)

        def run_gemma_chat(inputs: Union[ChatInputDict, Any]) -> str:
            """
            Process chat inputs and return a response from Groq API.
            
            Args:
                inputs: Either a dictionary with chat components or a ChatPromptValue
                
            Returns:
                The generated response as string
            """
            system_prompt = ""
            user_input = ""
            context = ""
            chat_history: List[Union[Dict[str, str], ChatMessage]] = []
            messages: List[MessageDict] = []

            try:
                # Handle dictionary input
                if isinstance(inputs, dict):
                    input_dict = cast(ChatInputDict, inputs)
                    system_prompt = str(input_dict.get("system_prompt", ""))
                    user_input = str(input_dict.get("input", ""))
                    context = str(input_dict.get("context", ""))
                    chat_history = input_dict.get("chat_history", [])
                # Handle ChatPromptValue input
                elif hasattr(inputs, 'messages'):
                    messages_list = getattr(inputs, 'messages', [])
                    system_prompt = str(next(
                        (getattr(msg, 'content', '') 
                        for msg in messages_list 
                        if getattr(msg, 'role', None) == "system"), 
                        ""
                    ))
                    user_input = str(next(
                        (getattr(msg, 'content', '') 
                        for msg in messages_list 
                        if getattr(msg, 'role', None) == "user"), 
                        ""
                    ))
                    context = ""
                    chat_history = []

                # Build messages list
                messages = [{"role": "system", "content": system_prompt}]
                
                # Process chat history
                for msg in chat_history[-4:]:
                    if isinstance(msg, dict):
                        messages.append({
                            "role": str(msg.get("role", "user")),
                            "content": str(msg.get("content", ""))
                        })
                    else:  # ChatMessage
                        messages.append({
                            "role": msg.role,
                            "content": msg.content
                        })

                # Add user message
                messages.append({
                    "role": "user", 
                    "content": f"{user_input}\n\n{context}"
                })

                # Get and return response
                response: ChatCompletion = client.chat.completions.create( # type: ignore
                    model="gemma2-9b-it",
                    messages=messages,  # type: ignore  # Workaround for messages type mismatch
                    temperature=0.8,
                    top_p=1,
                    max_tokens=1024,  # Changed from max_completion_tokens to max_tokens
                    stream=False
                )
                
                # Now with proper type hints for the response structure
                if response.choices and len(response.choices) > 0: # type: ignore
                    first_choice = response.choices[0] # type: ignore
                    message: Optional[ChatCompletionMessage] = first_choice.message # type: ignore
                    if message and message.content: # type: ignore
                        return str(message.content).strip() # type: ignore
                return ""
                
            except Exception as e:
                logger.error(f"Error in diagnostic agent: {e}", exc_info=True)
                return "I'm having trouble processing your request. Please try again."

        return RunnableLambda(run_gemma_chat)
    except Exception as e:
        logger.error(f"Failed to initialize diagnostic agent: {e}")
        return RunnableLambda(lambda _: "Diagnostic service is currently unavailable")

def get_diagnostic_agent() -> RunnableLambdaType[Union[ChatInputDict, Any], str]:
    if _diagnostic_agent is None:
        raise RuntimeError("Diagnostic agent not initialized. Call initialize_llm_services() first.")
    return _diagnostic_agent


def initialize_llm_services() -> RunnableLambdaType[Union[ChatInputDict, Any], str]:
    global _diagnostic_agent
    with _lock:
        if _diagnostic_agent is None:
            _diagnostic_agent = _create_diagnostic_agent()
    return _diagnostic_agent