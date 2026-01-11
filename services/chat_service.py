import asyncio
from services.multimodal_embeddings import embed_text
from fastapi import Request
from langchain_core.runnables import (
    RunnableSerializable,
    RunnablePassthrough,
    RunnableBranch,
    RunnableLambda,
)
# Ignore the warning for now. This works.
from langchain_tavily import TavilySearch
from langchain_core.documents import Document
from typing import Dict, Any, Optional, List, Literal
import logging
from models.chat import ChatSession
from models.vehicle import VehicleModel
from config import settings
from services.dependencies import get_diagnostic_agent, get_image_analyzer, get_vectorstore
from services.simple_responses import SimpleResponseGenerator
from datetime import datetime

from services.dependencies import get_sandwich_processor

logger = logging.getLogger(__name__)

class ChatService:
    def __init__(self, request: Request):
        self.vectorstore, self.image_data_store = get_vectorstore(request)
        self.diagnostic_agent = get_diagnostic_agent(request)
        self.image_analyzer = get_image_analyzer(request)
        # self.intent_classifier = get_intent_classifier(request)
        self.chain = self._create_processing_chain()
        self.tavily_tool = TavilySearch(
            tavily_api_key=settings.TAVILY_API_KEY, 
            max_results=3
        )
         # Use SandwichProcessor instead of IntentClassifier
        self.sandwich = get_sandwich_processor(request)
    def _contains_non_english_script(self, text: str) -> bool:
        """Returns True if text contains significant non-Latin characters (like Urdu/Arabic)"""
        non_ascii_count = sum(1 for c in text if ord(c) > 127)
        # If more than 10% of the text is non-ASCII (Urdu), it failed.
        return len(text) > 0 and (non_ascii_count / len(text)) > 0.1
    def _is_off_topic_or_inappropriate(self, text: str) -> bool:
        """Check if the message is off-topic or inappropriate"""
        # List of non-automotive topics to redirect
        off_topic_keywords = [
        "food", "restaurant", "movie", "weather", "sports", "politics", 
        "dating", "crypto", "stock market", "price of tesla", "finance",
        "recipe", "music", "celebrity", "history", "gaming"
    ]
        
        # Check for off-topic conversations
        if any(keyword in text.lower() for keyword in off_topic_keywords):
            return True
            
        # Check for very short or nonsensical inputs
        if len(text.strip()) < 3 or text.strip().isdigit():
            return True
            
        return False

    def _determine_processing_path(self, intent: str, user_input: str, has_image: bool = False) -> str:
        clean_input = user_input.lower()
        if self._is_off_topic_or_inappropriate(clean_input): return "off_topic"
        
        # Follow-up keywords
        modification_keywords = ["shorter", "brief", "summarize", "detail", "explain", "repeat", "more"]
        
        if any(word in clean_input for word in modification_keywords):
            return "rag_static" # Will be handled by follow-up logic in retrieval_chain

        technical_indicators = ["car", "bike", "engine", "brake", "leak", "noise", "light", "start", "fix"]
        if intent == "technical_question" or any(ind in clean_input for ind in technical_indicators):
            dynamic_indicators = ["price", "cost", "near me", "worth", "2025", "latest", "software"]
            return "rag_dynamic" if any(w in clean_input for w in dynamic_indicators) else "rag_static"

        if intent in ["greeting", "small_talk"]: return "simple"
        return "rag_static"


    def _create_simple_response_chain(self) -> RunnableSerializable:
        """Chain for simple responses (greetings, small talk)"""
        async def simple_response(inputs: Dict[str, Any]) -> Dict[str, Any]:
            """Generate simple conversational responses"""
            try:
                # Get intent from inputs
                intent = inputs.get("intent", "other")
                
                # 1. Try predefined static responses first
                predefined_response = SimpleResponseGenerator.get_response(
                    intent,
                    inputs["prompt"]
                )
                
                if predefined_response:
                    return {**inputs, "diagnosis_output": predefined_response}
                
                # 2. Prepare History: Convert Pydantic objects to Dicts
                # --- FIX START ---
                raw_history = inputs.get("chat_history", [])
                chat_history_dicts = []
                for msg in raw_history:
                    if hasattr(msg, 'model_dump'):
                        # Pydantic v2
                        chat_history_dicts.append(msg.model_dump())
                    elif hasattr(msg, 'dict'):
                        # Pydantic v1
                        chat_history_dicts.append(msg.dict())
                    elif isinstance(msg, dict):
                        chat_history_dicts.append(msg)
                    else:
                        # Fallback for strings or unknown types
                        chat_history_dicts.append({"role": "user", "content": str(msg)})
                # --- FIX END ---

                # 3. Analyze context for off-topic check
                # (Use raw_history here since off_topic check handles objects)
                recent_messages = raw_history[-3:]
                off_topic_messages = sum(1 for msg in recent_messages 
                                       if self._is_off_topic_or_inappropriate(msg.content if hasattr(msg, 'content') else str(msg)))

                # In services/chat_service.py

                prompt = f"""
                User message: "{inputs['prompt']}"
                Detected Intent: "{intent}"

                You are a professional automotive technician.
                The user is NOT asking a technical question.

                Instructions:
                1. If the user is critical (e.g., "Don't be dramatic"), apologize professionally.
                2. If it's a greeting, greet back warmly.
                3. Keep it SHORT and conversational.

                !!! CRITICAL LANGUAGE RULE !!!
                You MUST write your response in **ENGLISH ONLY**. 
                Do NOT write in Urdu or the user's language. 
                Your output will be translated later. If you write in Urdu now, the system will break.
                """
                
                # 4. Call the Agent with the DICTIONARY history
                response = self.diagnostic_agent.invoke({
                    "system_prompt": "You are a friendly vehicle mechanic assistant. Engage in natural conversation.",
                    "input": prompt,
                    "chat_history": chat_history_dicts,  # <--- PASSING DICTS NOW
                    "is_simple_response": True
                })
                
                return {**inputs, "diagnosis_output": response}

            except Exception as e:
                logger.error(f"Simple response failed: {e}", exc_info=True)
                # This is the fallback message you are currently seeing
                return {**inputs, "diagnosis_output": "I apologize, I missed that. How can I help with your vehicle?"}
        
        return RunnableLambda(simple_response)
    
    async def stream_message(
        self,
        session: ChatSession,
        user_input_data: Dict[str, Any],
        image_url: Optional[str] = None,
        vehicle: Optional[VehicleModel] = None
    ):
        """Streaming version of process_message for low-latency responses."""
        try:
            english_text = user_input_data["english_translation"]
            intent = user_input_data["intent"]


            processing_path = self._determine_processing_path(intent, english_text, bool(image_url))
            
            if processing_path == "off_topic":
                chain = self._create_off_topic_chain()
            elif processing_path == "simple":
                chain = self._create_simple_response_chain()
            else:
                chain = self._create_rag_chain()

            chain_inputs = {
                "prompt": english_text,
                "image_url": image_url,
                "vehicle": vehicle.model_dump() if vehicle else {},
                "chat_history": session.chat_history,
                "intent": intent,
                "processing_path": processing_path # <--- ADD THIS LINE
            }
            # 🔥 Use astream() to yield chunks to the FastAPI route
            async for chunk in chain.astream(chain_inputs):
                if isinstance(chunk, dict) and "diagnosis_output" in chunk:
                    yield chunk["diagnosis_output"]
                elif isinstance(chunk, str):
                    yield chunk

        except Exception as e:
            logger.error(f"Streaming in ChatService failed: {e}")
            yield "I encountered an error while processing your request."
    
    def _create_rag_chain(self) -> RunnableSerializable:
        """Create the RAG processing chain"""
        async def image_analysis_chain(inputs: Dict[str, Any]) -> Dict[str, Any]:
            """Process images using the image analyzer"""
            try:
                if not inputs.get("image_url"):
                    return {"context_1": "No image provided", **inputs}
                
                vehicle_info = inputs.get("vehicle", {})
                user_question = inputs.get("prompt", "Analyze this vehicle image")
                
                analysis = await self.image_analyzer.analyze(
                    inputs["image_url"],
                    prompt=user_question,
                    vehicle_info=vehicle_info
                    
                )
                print(f"[DEBUG] Analysis Result: {str(analysis)[:100]}...")
                return {"context_1": analysis, **inputs}
            except Exception as e:
                logger.error(f"Image analysis failed: {e}", exc_info=True)
                return {"context_1": "Image analysis failed", **inputs}

        async def query_expansion_chain(inputs: Dict[str, Any]) -> Dict[str, Any]:
            """Rewrite user query to be more search-friendly, skipping for simple follow-ups."""
            original_prompt = inputs["prompt"]
            
            # LATENCY OPTIMIZATION: Skip expansion if the user is just modifying a previous answer
            modification_keywords = ["shorter", "brief", "summarize", "detail", "explain", "repeat", "more", "bullets"]
            if any(word in original_prompt.lower() for word in modification_keywords):
                logger.info("Follow-up modification detected. Skipping Query Expansion for speed.")
                return {**inputs, "search_queries": []}

            expansion_prompt = f"""
            You are an expert mechanic. Generate 3 distinct search queries for: "{original_prompt}"
            Consider the vehicle context and symptoms.
            
            Output ONLY the 3 queries separated by newlines. No numbering. No intro.
            """

            try:
                optimized_query = await self.diagnostic_agent.ainvoke({
                    "system_prompt": "You are a technical search optimizer.",
                    "input": expansion_prompt,
                    "chat_history": [],
                    "is_simple_response": True 
                })
                
                queries = [q.strip() for q in optimized_query.split('\n') if q.strip()]
                return {**inputs, "search_queries": queries[:3]}
            except Exception as e:
                logger.error(f"Query expansion failed: {e}")
                return {**inputs, "search_queries": []}


        async def parallel_step(inputs: Dict[str, Any]):
            """Runs expansion and image analysis at the same time to reduce latency."""
            expansion_task = query_expansion_chain(inputs)
            image_task = image_analysis_chain(inputs)
            results = await asyncio.gather(expansion_task, image_task)
            # Combine results from both chains
            return {**results[0], **results[1]}

        async def retrieval_chain(inputs: Dict[str, Any]) -> Dict[str, Any]:
            try:
                original_prompt = inputs.get("prompt", "").lower()
                chat_history = inputs.get("chat_history", [])
                
                # --- FIX 1: FOLLOW-UP CONTEXT LOGIC ---
                modification_keywords = ["shorter", "brief", "summarize", "detail", "explain", "more"]
                is_follow_up = any(word in original_prompt for word in modification_keywords)

                if is_follow_up and len(chat_history) > 0:
                    # Look for the last assistant response in history
                    last_ai_msgs = [m for m in chat_history if (isinstance(m, dict) and m.get("role") == "assistant") or (hasattr(m, 'role') and m.role == 'assistant')]
                    if last_ai_msgs:
                        content = last_ai_msgs[-1]["content"] if isinstance(last_ai_msgs[-1], dict) else last_ai_msgs[-1].content
                        logger.info("Follow-up detected. Using previous answer as context.")
                        return {**inputs, "context_2": f"PREVIOUS_ANSWER_TO_MODIFY: {content}", "retrieved_context": []}

                # --- PATH A: WEB SEARCH ---
                if inputs.get("processing_path") == "rag_dynamic":
                    web_results = await self.tavily_tool.ainvoke({"query": original_prompt})
                    content = str(web_results)
                    return {**inputs, "context_2": f"*** WEB DATA ***\n{content}", "retrieved_context": []}

                # --- PATH B: STATIC MANUAL SEARCH ---
                search_list = [original_prompt] + inputs.get("search_queries", [])
                async def fetch_docs(q):
                    emb = await embed_text(q)
                    return await self.vectorstore.asimilarity_search_with_score_by_vector(emb, k=3)

                results = await asyncio.gather(*[fetch_docs(q) for q in search_list])
                # Simple flatten and deduplicate
                unique_docs = {doc.page_content: doc for sublist in results for doc, score in sublist if score < 1.4}
                text_context = "\n---\n".join(unique_docs.keys()) if unique_docs else "NO_RELEVANT_TECHNICAL_DATA_FOUND"
                
                return {**inputs, "context_2": text_context, "retrieved_context": []}
            except Exception as e:
                logger.error(f"Retrieval failed: {e}")
                return {**inputs, "context_2": "Error", "retrieved_context": []}

        

        async def diagnostic_chain(inputs: Dict[str, Any]) -> Dict[str, Any]:
            """Generate diagnostic response using the LLM with Expert System Fallbacks."""
            try:
                # 1. Prepare Vehicle Info
                context_data = inputs.get('context_2', '')
                vehicle = inputs.get("vehicle", {})
                vehicle_info = f"{vehicle.get('brand', 'Unknown')} {vehicle.get('model', 'Unknown')} ({vehicle.get('year', 'Unknown')})"
                
                # 2. STANDARD HISTORY CONVERSION (Fixes history loss)
                chat_history_dicts = []
                for msg in inputs.get("chat_history", []):
                    if isinstance(msg, dict):
                        chat_history_dicts.append(msg)
                    elif hasattr(msg, 'model_dump'):
                        chat_history_dicts.append(msg.model_dump())
                    else:
                        chat_history_dicts.append({"role": "user", "content": str(msg)})

                user_prompt = inputs['prompt']
                user_prompt_lower = user_prompt.lower()

                # 3. EXPERT FALLBACK LOGIC (No Data Handling)
                is_fallback = "NO_DATA" in context_data or "NO_RELEVANT_TECHNICAL_DATA_FOUND" in context_data
                
                if is_fallback:
                    system_prompt = f"You are a professional mechanic. I do not have specific manual data for this {vehicle_info}. Provide universal safety checks and advise visiting a certified technician. ENGLISH ONLY."
                    user_input_content = f"Technical data unavailable for: {user_prompt}. Provide general safety advice."
                else:
                    # 4. DYNAMIC STYLE SELECTION
                    style = "CONCISE (Step-by-step, max 15 words per step)"
                    if any(w in user_prompt_lower for w in ["detail", "explain", "elaborate", "why"]):
                        style = "DETAILED (Explain the cause and step-by-step fix)"
                    elif "bullets" in user_prompt_lower:
                        style = "BULLET POINTS ONLY"

                    system_prompt = f"""
                    You are a skilled automotive technician. 
                    VEHICLE: {vehicle_info}
                    STYLE: {style}
                    
                    TECHNICAL RULES:
                    - Respond in ENGLISH ONLY.
                    - If follow-up instructions (like 'shorter') are given, obey them based on the context provided.
                    - Use logical troubleshooting.
                    """
                    user_input_content = user_prompt

                # 5. INVOKE AGENT
                llm_input = {
                    "system_prompt": system_prompt,
                    "input": user_input_content,
                    "context": f"Manual/Web Knowledge: {context_data}\nImage Analysis: {inputs.get('context_1', 'N/A')}",
                    "chat_history": chat_history_dicts,
                    "is_simple_response": False
                }
                
                response = await self.diagnostic_agent.ainvoke(llm_input)

                # 6. QUALITY CHECK
                if self._contains_non_english_script(response):
                    logger.warning("Urdu detected in Technical Response. Forcing English Correction.")
                    # Simple logic to re-prompt or translate if necessary
                    response = await self.sandwich.translate_output(response, target_language="English")

                return {**inputs, "diagnosis_output": response}

            except Exception as e:
                logger.error(f"Diagnostic failed: {e}", exc_info=True)
                return {**inputs, "diagnosis_output": "I encountered an error generating the diagnosis. Please try again."}


        return (
            RunnablePassthrough()
            | RunnableLambda(parallel_step)
            | RunnableLambda(retrieval_chain)
            | RunnableLambda(diagnostic_chain)
        )
    def _create_off_topic_chain(self) -> RunnableSerializable:
        """Chain for handling off-topic or inappropriate conversations"""
        async def off_topic_response(inputs: Dict[str, Any]) -> Dict[str, Any]:
            chat_history = inputs.get("chat_history", [])
            off_topic_count = sum(1 for msg in chat_history[-3:] if self._is_off_topic_or_inappropriate(msg.content if hasattr(msg, 'content') else str(msg)))
            
            # If multiple off-topic messages in a row, give stronger redirect
            if off_topic_count >= 2:
                response = """I am a specialized automotive diagnostic assistant. I can only help with vehicle-related questions and issues. 
                Please ask me about your car's maintenance, repairs, or technical problems. If you have other questions, 
                you might want to consult a different service."""
            else:
                response = """I'm your automotive diagnostic assistant, so I can only help with vehicle-related questions. 
                What would you like to know about your car? I can help with:
                - Vehicle diagnostics and repairs
                - Maintenance questions
                - Technical specifications
                - Common problems and solutions
                - Warning lights and error codes"""
            
            return {**inputs, "diagnosis_output": response}
        
        return RunnableLambda(off_topic_response)

    def _create_processing_chain(self) -> RunnableSerializable:
        """Create the complete processing chain with intent-based routing"""
        
        async def routing_chain(inputs: Dict[str, Any]) -> Dict[str, Any]:
            """Route to appropriate processing chain based on intent"""
            # This assumes intent is already provided in inputs from the Sandwich processor
            intent = inputs.get("intent", "technical_question")
            processing_path = self._determine_processing_path(
                intent, inputs["prompt"]
            )
            
            logger.info(f"Routing to: {processing_path} processing")
            
            if processing_path == "off_topic":
                # Handle off-topic conversations
                off_topic_chain = self._create_off_topic_chain()
                return await off_topic_chain.ainvoke(inputs)
            elif processing_path == "simple":
                # Use simple response chain
                simple_chain = self._create_simple_response_chain()
                return await simple_chain.ainvoke(inputs)
            else:
                # Use full RAG pipeline (for technical_question, vehicle_diagnosis, command, and fallback)
                rag_chain = self._create_rag_chain()
                return await rag_chain.ainvoke(inputs)
        
        return RunnableLambda(routing_chain)

    def _get_vehicle_system_prompt(self, vehicle_info: dict) -> str:
        """Generate system prompt for vehicle diagnosis"""
        return f"""You are an expert **vehicle mechanic assistant** trained to diagnose and resolve issues related to ground vehicles.

You are provided with:
- A user-described problem or symptoms
- Vehicle metadata:
    - Make: {vehicle_info.get("make", "Unknown")}
    - Model: {vehicle_info.get("model", "Unknown")}
    - Year: {vehicle_info.get("year", "Unknown")}
    - Fuel Type: {vehicle_info.get("fuel_type", "Unknown")}
    - Engine Type: {vehicle_info.get("engine_type", "Unknown")}
- Optional images or diagnostic documents
- Complete chat history for context

Guidelines:
1. Be professional but friendly and conversational when appropriate
2. Ask clarifying questions when needed
3. Provide step-by-step solutions when possible
4. Reference vehicle-specific information
5. Maintain conversation context
6. For complex issues, recommend professional help
7. Adapt your tone based on the conversation - be more technical for diagnosis, more conversational for greetings"""
    
    
    # ==========New Process Message Method========
    async def process_message(
        self,
        session: ChatSession,
        user_input_data: Dict[str, Any], # Receives result from Sandwich Step 1
        image_url: Optional[str] = None,
        vehicle: Optional[VehicleModel] = None
    ) -> Dict[str, Any]:
        """
        Args:
            user_input_data: Result from Sandwich Step 1 
                             {"english_translation", "intent", "detected_language", ...}
        """
        try:
            # 1. Update Session with Image/Vehicle
            if image_url:
                session.image_history.append(image_url)
            if vehicle:
                session.vehicle_info = vehicle

            # 🔥 CRITICAL: Extract English Text for "The Brain"
            english_text = user_input_data["english_translation"]
            # 🔥 CRITICAL: Extract Target Language (User's Preference) for "Output"
            target_lang = user_input_data["detected_language"]
            intent = user_input_data["intent"]

            # 2. Determine Path using the ENGLISH text (Brain understands English best)
            processing_path = self._determine_processing_path(
                intent, 
                english_text, 
                has_image=bool(image_url) 
            )
            # 3. Prepare Inputs for the Brain (Step 2)
            # IMPORTANT: We feed the BRAIN the ENGLISH text. 
            # This guarantees the RAG chain finds English documents.
            chain_inputs = {
                "prompt": english_text,  
                "image_url": image_url,
                "vehicle": vehicle.model_dump() if vehicle else {},
                "chat_history": session.chat_history,
                "intent": intent,
                "processing_path": processing_path  # <--- ADD THIS LINE
            }
            
            # 4. Execute "The Brain" (Step 2)
            if processing_path == "off_topic":
                result = await self._create_off_topic_chain().ainvoke(chain_inputs)
            elif processing_path == "simple":
                result = await self._create_simple_response_chain().ainvoke(chain_inputs)
            else:
                result = await self._create_rag_chain().ainvoke(chain_inputs)
            
            english_response = result.get("diagnosis_output", "")

            # 5. Translate Response (Step 3)
            # The Sandwich closes here. Translates English Diagnostic -> User's Preferred Language
            if target_lang.lower() in ["en", "english", "eng"]:
                final_response = english_response
                logger.info("Target language is English. Skipping translation step.")
            else:
                final_response = await self.sandwich.translate_output(english_response, target_language=target_lang)

            session.chat_history.append({"role": "user", "content": english_text})
            session.chat_history.append({"role": "assistant", "content": english_response})

            # 6. Title Generation
            if len(session.chat_history) <= 4 and not session.chat_title: # Use <= 4 because we just added 2 messages
                session.chat_title = await self.generate_chat_title(english_text)    
            return {
                "response": final_response,        # Localized response (Urdu/Hindi/etc)
                "english_response": english_response, # English version
                "updated_session": session,
                "detected_language": target_lang
            }

        except Exception as e:
            logger.error(f"Message processing failed: {e}", exc_info=True)
            raise
    async def generate_chat_title(self, first_message: str) -> str:
        """Generate a summary title for the chat based on the first message"""
        try:
            prompt = f"""
            Create a precise, technical title (3-5 words) for this automotive consultation:
            "{first_message}"
            
            Requirements:
            1. Use proper automotive terminology
            2. Be specific about the system or component
            3. Include the issue type (noise, malfunction, maintenance, etc.)
            4. Respond ONLY with the title - no quotes or formatting
            
            Example titles:
            - Brake Pad Wear Diagnosis
            - Engine Misfire Investigation
            - Transmission Fluid Service
            - Suspension Noise Analysis
            - Battery Charging System
            - Steering Alignment Check
            """
            
            response = await self.diagnostic_agent.ainvoke({
                "system_prompt": "You are a vehicle expert that creates concise, descriptive chat titles.",
                "input": prompt,
                "chat_history": [],
                "is_simple_response": True
            })
            
            return response.strip('"').strip("'").strip() or "Vehicle Consultation"
        except Exception as e:
            logger.error(f"Title generation failed: {e}")
            return "Vehicle Consultation"