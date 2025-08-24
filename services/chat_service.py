from fastapi import Request
from langchain_core.runnables import (
    RunnableSerializable,
    RunnablePassthrough,
    RunnableLambda,
)
from typing import Dict, Any, Optional, List
import logging
from models.chat import ChatSession  # Updated to use ChatSession instead of ChatState
from models.vehicle import VehicleModel
from config import settings
from services.dependencies import get_diagnostic_agent, get_image_analyzer, get_vectorstore
from datetime import datetime

logger = logging.getLogger(__name__)

class ChatService:
    def __init__(self, request: Request):
        self.vectorstore, self.image_data_store = get_vectorstore(request)
        self.diagnostic_agent = get_diagnostic_agent(request)
        self.image_analyzer = get_image_analyzer(request)
        self.chain = self._create_processing_chain()
        
    def _create_processing_chain(self) -> RunnableSerializable[Dict[str, Any], Dict[str, Any]]:
        """Create the complete processing chain with error handling"""
        def image_analysis_chain(inputs: Dict[str, Any]) -> Dict[str, Any]:
            """Process images using the image analyzer"""
            try:
                if not inputs.get("image_url"):
                    return {"context_1": "No image provided", **inputs}
                
                vehicle_info = inputs.get("vehicle", {})
                user_question = inputs.get("prompt", "Analyze this vehicle image")
                
                analysis = self.image_analyzer.analyze(
                    inputs["image_url"],
                    prompt=user_question,
                    vehicle_info=vehicle_info
                )
                return {"context_1": analysis, **inputs}
            except Exception as e:
                logger.error(f"Image analysis failed: {e}", exc_info=True)
                return {"context_1": "Image analysis failed", **inputs}

        def retrieval_chain(inputs: Dict[str, Any]) -> Dict[str, Any]:
            """Retrieve relevant information from vector store"""
            try:
                vehicle = inputs.get("vehicle", {})
                prompt = inputs["prompt"]
                chat_history = inputs.get("chat_history", [])

                # Get last 2 user messages for context
                history_context = "\n".join(
                    [msg["content"] for msg in chat_history[-4:] if msg["role"] == "user"]
                )

                enhanced_question = (
                    f"Conversation Context:\n{history_context}\n\n"
                    f"Vehicle: {vehicle.get('brand', 'Unknown')} {vehicle.get('model', 'Unknown')} {vehicle.get('year', 'Unknown')}\n"
                    f"Current Problem: {prompt}"
                )

                retriever = self.vectorstore.as_retriever(
                    search_kwargs={
                        "k": 3,
                        "filter": {"vehicle_make": vehicle.get("brand")} if vehicle.get("brand") else None
                    }
                )
                docs = retriever.invoke(enhanced_question)
                
                # Combine text and image context
                text_context = "\n---\n".join([doc.page_content for doc in docs])
                multimodal_context = []
                
                for doc in docs:
                    if doc.metadata.get("type") == "image":
                        image_id = doc.metadata.get("image_id")
                        if image_id in self.image_data_store:
                            multimodal_context.append({
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{self.image_data_store[image_id]}"
                                }
                            })
                
                return {
                    **inputs,
                    "context_2": text_context,
                    "multimodal_context": multimodal_context
                }
            except Exception as e:
                logger.error(f"Retrieval failed: {e}", exc_info=True)
                return {**inputs, "context_2": "Knowledge retrieval failed"}

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
                
                llm_input = {
                    "system_prompt": self._get_vehicle_system_prompt(vehicle_info),
                    "input": inputs["prompt"],
                    "context": f"""
                    Image Analysis:
                    {inputs.get('context_1', 'No image analysis available')}
                    
                    Knowledge Base Context:
                    {inputs.get('context_2', 'No knowledge base context available')}
                    
                    Multimodal Context:
                    {inputs.get('multimodal_context', 'No additional context')}
                    """,
                    "chat_history": inputs.get("chat_history", [])
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
1. Be professional but friendly
2. Ask clarifying questions when needed
3. Provide step-by-step solutions when possible
4. Reference vehicle-specific information
5. Maintain conversation context
6. For complex issues, recommend professional help"""

    async def process_message(
        self,
        session: ChatSession,
        user_input: str,
        image_url: Optional[str] = None,
        vehicle: Optional[VehicleModel] = None
    ) -> Dict[str, Any]:
        """
        Process a user message through the complete chain
        
        Args:
            session: Current chat session
            user_input: User's message text
            image_url: Optional image URL/path
            vehicle: Optional vehicle information
            
        Returns:
            Dictionary containing:
            - response: Generated diagnosis/response
            - updated_session: Updated chat session
        """
        try:
            # Add user message to history
            session.chat_history.append({
                "role": "user",
                "content": user_input,
                "timestamp": datetime.now()
            })
            
            if image_url:
                session.image_history.append(image_url)
            
            if vehicle:
                session.vehicle_info = vehicle

            # Prepare chain input
            inputs = {
                "prompt": user_input,
                "image_url": image_url,
                "vehicle": vehicle.model_dump() if vehicle else {},
                "chat_history": session.chat_history
            }
            
            # Process through chain
            result = await self.chain.ainvoke(inputs)
            
            # Handle response
            diagnosis = result.get("diagnosis_output", "")
            if diagnosis:
                session.chat_history.append({
                    "role": "assistant",
                    "content": diagnosis,
                    "timestamp": datetime.now()
                })
                
            # Generate title if first message
            if len(session.chat_history) <= 2 and not session.chat_title:
                session.chat_title = await self.generate_chat_title(user_input)
                
            return {
                "response": diagnosis,
                "updated_session": session
            }
        except Exception as e:
            logger.error(f"Message processing failed: {e}", exc_info=True)
            raise
    
    async def generate_chat_title(self, first_message: str) -> str:
        """Generate a summary title for the chat based on the first message"""
        try:
            prompt = f"""
            Create a very short (3-5 word) title summarizing this vehicle issue:
            "{first_message}"
            
            Respond ONLY with the title text, no quotes or other formatting.
            Example outputs:
            - Engine knocking sound
            - Brake system issue
            - Electrical problem
            - Transmission trouble
            """
            
            response = await self.diagnostic_agent.ainvoke({
                "system_prompt": "You are a vehicle expert that creates concise, descriptive chat titles.",
                "input": prompt,
                "chat_history": []
            })
            
            return response.strip('"').strip("'").strip() or "Vehicle Consultation"
        except Exception as e:
            logger.error(f"Title generation failed: {e}")
            return "Vehicle Consultation"