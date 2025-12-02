from services.multimodal_embeddings import embed_text
from fastapi import Request
from langchain_core.runnables import (
    RunnableSerializable,
    RunnablePassthrough,
    RunnableBranch,
    RunnableLambda,
)
from typing import Dict, Any, Optional, List, Literal
import logging
from models.chat import ChatSession
from models.vehicle import VehicleModel
from config import settings
from services.dependencies import get_diagnostic_agent, get_image_analyzer, get_vectorstore
from services.simple_responses import SimpleResponseGenerator
from datetime import datetime

# from services.intent_classifier import get_intent_classifier
# ... imports ...
from services.dependencies import get_sandwich_processor

logger = logging.getLogger(__name__)

class ChatService:
    def __init__(self, request: Request):
        self.vectorstore, self.image_data_store = get_vectorstore(request)
        self.diagnostic_agent = get_diagnostic_agent(request)
        self.image_analyzer = get_image_analyzer(request)
        # self.intent_classifier = get_intent_classifier(request)
        self.chain = self._create_processing_chain()

         # Use SandwichProcessor instead of IntentClassifier
        self.sandwich = get_sandwich_processor(request)
    
    def _is_off_topic_or_inappropriate(self, text: str) -> bool:
        """Check if the message is off-topic or inappropriate"""
        # List of non-automotive topics to redirect
        off_topic_keywords = [
            "food", "restaurant", "movie", "weather", "sports", "game",
            "politics", "dating", "cryptocurrency", "stock market"
        ]
        
        # Check for off-topic conversations
        if any(keyword in text.lower() for keyword in off_topic_keywords):
            return True
            
        # Check for very short or nonsensical inputs
        if len(text.strip()) < 3 or text.strip().isdigit():
            return True
            
        return False

    def _determine_processing_path(self, intent: str, user_input: str) -> Literal["simple", "rag", "command", "off_topic"]:
        """Determine the processing path based on user intent"""
        # Intent is already determined by Sandwich Step 1
        logger.info(f"Detected intent: {intent} for message: '{user_input}'")
        
        # Check for off-topic or inappropriate content first
        if self._is_off_topic_or_inappropriate(user_input):
            return "off_topic"
        
        # More specific intent classification
        if any(word.lower() in user_input.lower() for word in ["hi", "hello", "hey", "good morning", "good afternoon", "good evening"]) and len(user_input.split()) <= 4:
            return "simple"
        elif any(word.lower() in user_input.lower() for word in ["bye", "goodbye", "thanks", "thank you"]) and len(user_input.split()) <= 4:
            return "simple"
        elif any(keyword in user_input.lower() for keyword in ["fix", "repair", "broken", "not working", "problem", "issue", "help", "diagnose", "check", "car", "vehicle", "engine", "brake", "tire", "wheel", "battery", "oil", "maintenance"]):
            return "rag"  # Technical questions get full diagnosis
        elif intent in ["technical_question", "vehicle_diagnosis"]:
            return "rag"
        elif intent == "command":
            return "command"
        else:
            # Check if the message is very short or unclear
            if len(user_input.split()) <= 2:
                return "off_topic"
            return "rag"  # Default to RAG for unknown intents
    
    def _create_simple_response_chain(self) -> RunnableSerializable:
        """Chain for simple responses (greetings, small talk)"""
        async def simple_response(inputs: Dict[str, Any]) -> Dict[str, Any]:
            """Generate simple conversational responses"""
            try:
                # Get intent from inputs (provided by Sandwich processor)
                intent = inputs.get("intent", "other")
                
                # First try to get a predefined response
                predefined_response = SimpleResponseGenerator.get_response(
                    intent,
                    inputs["prompt"]
                )
                
                if predefined_response:
                    return {**inputs, "diagnosis_output": predefined_response}
                
                # Fallback to LLM for more complex simple responses
                # Analyze chat history for context
                recent_messages = inputs.get("chat_history", [])[-3:]
                off_topic_messages = sum(1 for msg in recent_messages 
                                       if self._is_off_topic_or_inappropriate(msg.content if hasattr(msg, 'content') else str(msg)))

                prompt = f"""
                User message: "{inputs['prompt']}"
                Recent chat history shows {'several off-topic messages' if off_topic_messages > 1 else 'normal conversation'}.
                
                You are a professional automotive technician. Keep your responses natural and conversational while maintaining expertise.
                
                Guidelines:
                1. Keep responses brief and natural
                2. Be friendly and approachable
                3. Focus on automotive topics naturally
                4. Redirect off-topic conversations smoothly
                5. Maintain professional expertise
                
                Style Requirements:
                - Be conversational but professional
                - Avoid repetitive phrases
                - Don't mention vehicle specs unless asked
                - Keep technical terms simple unless needed
                - Use natural transitions in conversation
                
                Examples:
                - "Hello! I'm your automotive specialist. What vehicle concerns can I address for you today?"
                - "I'm here to help with any vehicle-related questions. What seems to be the issue with your car?"
                - "While I appreciate the conversation, I'm specifically trained for automotive diagnostics. How can I help with your vehicle today?"
                - "Let's focus on your vehicle needs. What automotive concerns would you like me to address?"
                """
                
                response = await self.diagnostic_agent.ainvoke({
                    "system_prompt": "You are a friendly vehicle mechanic assistant. Engage in natural conversation. Keep responses brief for greetings and small talk.",
                    "input": prompt,
                    "chat_history": inputs.get("chat_history", []),
                    "is_simple_response": True
                })
                
                return {**inputs, "diagnosis_output": response}
            except Exception as e:
                logger.error(f"Simple response failed: {e}")
                return {**inputs, "diagnosis_output": "Hello! How can I help with your vehicle today?"}
        
        return RunnableLambda(simple_response)
    
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

        # def retrieval_chain(inputs: Dict[str, Any]) -> Dict[str, Any]:
        #     """Retrieve relevant information from vector store"""
        #     try:
        #         vehicle = inputs.get("vehicle", {})
        #         prompt = inputs["prompt"]
        #         chat_history = inputs.get("chat_history", [])

        #         # Get last 2 user messages for context
        #         history_context = "\n".join(
        #             [msg.content for msg in chat_history[-4:] if hasattr(msg, 'content')]
        #         )

        #         # Build context-aware query
        #         is_model_specific = any(word in prompt.lower() for word in [
        #             "where is", "location", "specific", "particular", "this model",
        #             "my model", "different", "varies", "compatible"
        #         ])

        #         enhanced_question = (
        #             f"Conversation Context:\n{history_context}\n\n"
        #             f"User Query: {prompt}"
        #         )

        #         # Only add vehicle details if the query seems to need model-specific info
        #         if is_model_specific:
        #             enhanced_question += f"\nVehicle Details: {vehicle.get('brand', '')} {vehicle.get('model', '')} {vehicle.get('year', '')}"

        #         # Manual embedding and search
        #         query_embedding = embed_text(enhanced_question)
                
        #         # Manual similarity search
        #         docs_and_scores = self.vectorstore.similarity_search_by_vector(
        #             query_embedding,
        #             k=3,
        #             filter={"vehicle_make": vehicle.get("brand")} if vehicle.get("brand") else None
        #         )
                
        #         # Combine text and image context
        #         text_context = "\n---\n".join([doc.page_content for doc in docs_and_scores])
        #         multimodal_context = []
                
        #         for doc in docs_and_scores:
        #             if doc.metadata.get("type") == "image":
        #                 image_id = doc.metadata.get("image_id")
        #                 if image_id in self.image_data_store:
        #                     multimodal_context.append({
        #                         "type": "image_url",
        #                         "image_url": {
        #                             "url": f"data:image/png;base64,{self.image_data_store[image_id]}"
        #                         }
        #                     })
                
        #         return {
        #             **inputs,
        #             "context_2": text_context,
        #             "multimodal_context": multimodal_context
        #         }
        #     except Exception as e:
        #         logger.error(f"Retrieval failed: {e}", exc_info=True)
        #         return {**inputs, "context_2": "Knowledge retrieval failed"}

        def retrieval_chain(inputs: Dict[str, Any]) -> Dict[str, Any]:
            """
            Retrieve relevant information from vector store with proper score handling
            and expose retrieved documents for testing/evaluation.
            """
            try:
                vehicle = inputs.get("vehicle", {})
                prompt = inputs["prompt"]
                chat_history = inputs.get("chat_history", [])

                # Get last 4 messages for context
                history_context = "\n".join(
                [str(msg.content) for msg in chat_history[-4:] if hasattr(msg, 'content') and msg.content is not None]
                )

                prompt = str(inputs["prompt"])  # ensure prompt is string

                enhanced_question = f"Conversation Context:\n{history_context}\n\nUser Query: {prompt}"
                query_embedding = embed_text(enhanced_question)


                # --- FAISS similarity search with scores ---
                # docs_and_scores = self.vectorstore.similarity_search_with_score(
                #     # query_embedding,
                #     enhanced_question,
                #     k=3,
                #     filter={"vehicle_make": vehicle.get("brand")} if vehicle.get("brand") else None
                # )

                docs_and_scores = self.vectorstore.similarity_search_with_score_by_vector(
                    query_embedding,  # Pass the computed embedding here
                    k=3,
                    filter={"vehicle_make": vehicle.get("brand")} if vehicle.get("brand") else None
                )
                # Debug: raw docs_and_scores
                print("\n=== Raw docs_and_scores ===")
                print(docs_and_scores)
                print("===========================\n")

                # Normalize docs_and_scores to list of (Document, score)
                normalized = []
                for item in docs_and_scores:
                    if isinstance(item, tuple) and len(item) == 2:
                        doc, score = item
                    elif hasattr(item, "page_content"):
                        doc = item
                        score = None
                    else:
                        logger.warning(f"Unexpected item format in docs_and_scores: {item}")
                        continue
                    normalized.append((doc, score))

                # Debug: print retrieved docs and scores
                print("\n=== Retrieval Debug ===")
                print(f"Query: {prompt}")
                print("Retrieved documents and scores:")
                for idx, (doc, score) in enumerate(normalized):
                    doc_id = doc.metadata.get("source", "unknown")
                    print(f"{idx+1}. doc_id: {doc_id}, score: {score}")
                print("======================\n")

                # Extract docs list
                docs = [doc for doc, _ in normalized]

                # Build text context
                text_context = "\n---\n".join([doc.page_content for doc in docs])

                # Build multimodal context (for images)
                multimodal_context = []
                for doc, _ in normalized:
                    if doc.metadata.get("type") == "image":
                        image_id = doc.metadata.get("image_id")
                        if image_id in self.image_data_store:
                            multimodal_context.append({
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{self.image_data_store[image_id]}"
                                }
                            })

                # Build retrieved_context for evaluation
                retrieved_context = [
                    {
                        "doc_id": doc.metadata.get("source", "unknown"),
                        "score": round(score, 3) if isinstance(score, (int, float)) else None
                    }
                    for doc, score in normalized
                ]

                # Return complete response
                return {
                    **inputs,
                    "context_2": text_context,
                    "multimodal_context": multimodal_context,
                    "retrieved_context": retrieved_context
                }

            except Exception as e:
                logger.error(f"Retrieval failed: {e}", exc_info=True)
                return {
                    **inputs,
                    "context_2": "Knowledge retrieval failed",
                    "retrieved_context": []
                }

        def diagnostic_chain(inputs: Dict[str, Any]) -> Dict[str, Any]:
            """Generate diagnostic response using the LLM"""
            try:
                vehicle = inputs.get("vehicle", {})
                vehicle_info = {
                    "make": vehicle.get("brand", "Unknown"),
                    "model": vehicle.get("model", "Unknown"),
                    "year": vehicle.get("year", "Unknown"),
                    "fuel_type": vehicle.get("fuel_type", "Unknown"),
                    "engine_type": vehicle.get("engine_type", "Unknown")
                }
                
                # Convert ChatMessage objects to dict for the LLM
                chat_history_dicts = []
                for msg in inputs.get("chat_history", []):
                    if hasattr(msg, 'model_dump'):
                        chat_history_dicts.append(msg.model_dump())
                    else:
                        chat_history_dicts.append(msg)
                enhanced_system_prompt = f"""You are a master automotive technician using the "Process of Elimination".
                
                VEHICLE: {vehicle_info['make']} {vehicle_info['model']} ({vehicle_info['year']})

                INSTRUCTIONS:
                Analyze the symptoms and provided context. Return your answer in a strict, structured format offering 2-3 distinct solutions sorted by likelihood.
                
                REQUIRED OUTPUT FORMAT:
                
                **1. Most Likely Solution (High Confidence)**
                *   **Why:** Brief explanation of why this is the probable cause.
                *   **Action:** Step-by-step instructions on what to check or fix first.
                
                **2. Secondary Solution (If step 1 fails)**
                *   **Why:** Alternative cause if the first fix doesn't work.
                *   **Action:** Next diagnostic steps.
                
                **3. Professional Check (if applicable)**
                *   **When to stop:** Critical safety warning or when to see a mechanic.

                RULES:
                - Be direct and actionable.
                - Do NOT write a generic introductory paragraph. Start immediately with "1. Most Likely Solution".
                - Use clear bullet points.
                - If the issue is simple, you may only provide 1 or 2 solutions.
                - SAFETY FIRST: If the issue is dangerous (brakes/fuel), put the Safety Warning first.

                Current User Query: "{inputs['prompt']}"
                """


                llm_input = {
                    # "system_prompt": self._get_vehicle_system_prompt(vehicle_info),
                    "system_prompt": enhanced_system_prompt,
                    "input": inputs["prompt"],
                    "context": f"""
                    Image Analysis:
                    {inputs.get('context_1', 'No image analysis available')}
                    
                    Knowledge Base Context:
                    {inputs.get('context_2', 'No knowledge base context available')}
                    
                    Multimodal Context:
                    {inputs.get('multimodal_context', 'No additional context')}
                    """,
                    "chat_history": chat_history_dicts,
                    "is_simple_response": False
                }
                
                response = self.diagnostic_agent.invoke(llm_input)
                return {**inputs, "diagnosis_output": response}
            except Exception as e:
                logger.error(f"Diagnostic failed: {e}", exc_info=True)
                return {**inputs, "diagnosis_output": "Diagnostic service unavailable"}
        
        return (
            RunnablePassthrough()
            | RunnableLambda(image_analysis_chain)
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
    # ==========Old Process Message Method=======
    # async def process_message(
    #     self,
    #     session: ChatSession,
    #     user_input: str,
    #     image_url: Optional[str] = None,
    #     vehicle: Optional[VehicleModel] = None
    # ) -> Dict[str, Any]:
    #     """
    #     Process a user message through the complete chain
        
    #     Args:
    #         session: Current chat session
    #         user_input: User's message text
    #         image_url: Optional image URL/path
    #         vehicle: Optional vehicle information
            
    #     Returns:
    #         Dictionary containing:
    #         - response: Generated diagnosis/response
    #         - updated_session: Updated chat session
    #     """
    #     try:
    #         if image_url:
    #             session.image_history.append(image_url)
            
    #         if vehicle:
    #             session.vehicle_info = vehicle

    #         # Prepare chain input
    #         inputs = {
    #             "prompt": user_input,
    #             "image_url": image_url,
    #             "vehicle": vehicle.model_dump() if vehicle else {},
    #             "chat_history": session.chat_history
    #         }
            
    #         # Process through chain
    #         result = await self.chain.ainvoke(inputs)
            
    #         # Handle response
    #         diagnosis = result.get("diagnosis_output", "")
            
    #         # Generate title if first message
    #         if len(session.chat_history) <= 2 and not session.chat_title:
    #             session.chat_title = await self.generate_chat_title(user_input)
                
    #         return {
    #             "response": diagnosis,
    #             "updated_session": session
    #         }
    #     except Exception as e:
    #         logger.error(f"Message processing failed: {e}", exc_info=True)
    #         raise
    
    
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
            processing_path = self._determine_processing_path(intent, english_text)
            
            # 3. Prepare Inputs for the Brain (Step 2)
            # IMPORTANT: We feed the BRAIN the ENGLISH text. 
            # This guarantees the RAG chain finds English documents.
            chain_inputs = {
                "prompt": english_text,  
                "image_url": image_url,
                "vehicle": vehicle.model_dump() if vehicle else {},
                "chat_history": session.chat_history,
                "intent": intent 
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
            final_response = await self.sandwich.translate_output(
                english_response, 
                target_language=target_lang
            )
            
            # 6. Title Generation (using English text for better titles)
            if len(session.chat_history) <= 2 and not session.chat_title:
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