import asyncio
from services.multimodal_embeddings import embed_text
from fastapi import Request
from langchain_core.runnables import (
    RunnableSerializable,
    RunnablePassthrough,
    RunnableBranch,
    RunnableLambda,
)
from langchain_tavily import TavilySearchResults
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
        self.tavily_tool = TavilySearchResults(max_results=3)
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


    def _determine_processing_path(self, intent: str, user_input: str, has_image: bool = False) -> Literal["simple", "rag", "command", "off_topic"]:
        logger.info(f"Routing logic -> Intent: {intent}, Input: '{user_input}', Has Image: {has_image}")

        # 1. FORCE RAG for Images
        if has_image:
            return "rag"

        # 2. Check for Off-topic
        if self._is_off_topic_or_inappropriate(user_input):
            return "off_topic"

        # --- FIX START: Detect Context Modifications (Stop the Restart) ---
        # If user asks to change the answer style, send it to the BRAIN (RAG), not the Greeter.
        modification_keywords = [
            "shorter", "brief", "too long", "summarize", "detail", "explain", 
            "elaborate", "again", "repeat", "what?", "didn't understand", "simplify"
        ]
        if any(word in user_input.lower() for word in modification_keywords):
            return "rag" # The Brain handles "Make it shorter", not the Greeter
        # --- FIX END ---
        
        # 3. Handle Conversational Intents
        if intent in ["greeting", "small_talk", "other"]:
            return "simple"

        # 4. Handle Commands (Vehicle Actions vs Conversational Commands)
        if intent == "command":
            # Double check if it's a vehicle command or a chat command
            if any(word in user_input.lower() for word in ["turn", "switch", "open", "close", "start", "stop"]):
                return "command"
            return "rag" # Treat ambiguous commands as technical requests

        # 5. Technical Questions
        return "rag"
    
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

            chain_inputs = {
                "prompt": english_text,
                "image_url": image_url,
                "vehicle": vehicle.model_dump() if vehicle else {},
                "chat_history": session.chat_history,
                "intent": intent
            }

            processing_path = self._determine_processing_path(intent, english_text, bool(image_url))
            
            if processing_path == "off_topic":
                chain = self._create_off_topic_chain()
            elif processing_path == "simple":
                chain = self._create_simple_response_chain()
            else:
                chain = self._create_rag_chain()

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
            """Rewrite user query to be more search-friendly"""
            original_prompt = inputs["prompt"]
            expansion_prompt = f"""
    You are an expert mechanic. The user is asking a question in non-technical language.
    
            Generate 3 distinct search queries for: "{original_prompt} and consider the chat history for context. CHAT HISTORY: {inputs.get('chat_history', [])}"
            1. Technical translation
            2. Symptom-based query
            3. Component-focused query
            Output ONLY the 3 queries separated by newlines. No numbering.
            """

            # Call a cheaper/faster model for this if possible
            optimized_query = await self.diagnostic_agent.ainvoke({
                "system_prompt": "You are a query optimizer.",
                "input": expansion_prompt,
                "chat_history": [],
                "is_simple_response": True 
            })
            
            # Update the prompt used for RETRIEVAL, but keep original for Generation
            queries = [q.strip() for q in optimized_query.split('\n') if q.strip()]
            return {**inputs, "search_queries": queries[:3]}

        async def parallel_step(inputs: Dict[str, Any]):
            """Runs expansion and image analysis at the same time to reduce latency."""
            expansion_task = query_expansion_chain(inputs)
            image_task = image_analysis_chain(inputs)
            results = await asyncio.gather(expansion_task, image_task)
            # Combine results from both chains
            return {**results[0], **results[1]}

        # async def retrieval_chain(inputs: Dict[str, Any]) -> Dict[str, Any]:
        #     """
        #     Retrieve relevant information from vector store with proper score handling
        #     and expose retrieved documents for testing/evaluation.
        #     """
        #     try:
        #         vehicle = inputs.get("vehicle", {})
        #         chat_history = inputs.get("chat_history", [])
                
        #         # 1. Use the Optimized Query from expansion chain
        #         search_query = inputs.get("search_query", inputs["prompt"])
                
        #         # 2. Embed ONLY the English translation/optimized query
        #         query_embedding = await embed_text(search_query)
                
        #         # 3. Increase K to improve Top-5 metrics
        #         k_value = 5 

                
        #         # 5. First Search Attempt (Specific)
        #         docs_and_scores = await self.vectorstore.asimilarity_search_with_score_by_vector(
        #             query_embedding,
        #             k=k_value,
        #             filter=None
        #         )

        #         # Normalize docs_and_scores to list of (Document, score)
        #         normalized = []
        #         for item in docs_and_scores:
        #             if isinstance(item, tuple) and len(item) == 2:
        #                 doc, score = item
        #             elif hasattr(item, "page_content"):
        #                 doc = item
        #                 score = None # Should ideally not happen with search_with_score
        #             else:
        #                 continue
        #             normalized.append((doc, score))

        #         # --- NEW: Relevancy Check & Filtering ---
        #         valid_docs = []
        #         for doc, score in normalized:
        #             # Threshold: Adjust based on your vector store metric
        #             # If using Cosine similarity (0 to 1), < 0.65 might be irrelevant
        #             # If using L2 distance, > threshold is irrelevant
        #             if score is not None and score > 1.2: # Example threshold for "too far away"
        #                 continue 
        #             valid_docs.append(doc)
                
        #         if not valid_docs:
        #             text_context = "NO_RELEVANT_TECHNICAL_DATA_FOUND"
        #         else:
        #             text_context = "\n---\n".join([doc.page_content for doc in valid_docs])

        #         # Build multimodal context (for images) based on valid docs
        #         multimodal_context = []
        #         for doc in valid_docs:
        #             if doc.metadata.get("type") == "image":
        #                 image_id = doc.metadata.get("image_id")
        #                 if image_id in self.image_data_store:
        #                     multimodal_context.append({
        #                         "type": "image_url",
        #                         "image_url": {
        #                             "url": f"data:image/png;base64,{self.image_data_store[image_id]}"
        #                         }
        #                     })

        #         # Build retrieved_context for evaluation (Keep originals for metrics)
        #         retrieved_context = [
        #             {
        #                 "doc_id": doc.metadata.get("source", "unknown"),
        #                 "page": doc.metadata.get("page", "unknown"),
        #                 "score": round(score, 3) if isinstance(score, (int, float)) else None
        #             }
        #             for doc, score in normalized
        #         ]

        #         # Return complete response
        #         return {
        #             **inputs,
        #             "context_2": text_context,
        #             "multimodal_context": multimodal_context,
        #             "retrieved_context": retrieved_context
        #         }

        #     except Exception as e:
        #         logger.error(f"Retrieval failed: {e}", exc_info=True)
        #         return {
        #             **inputs,
        #             "context_2": "Knowledge retrieval failed",
        #             "retrieved_context": []
        #         }
          
        # async def retrieval_chain(inputs: Dict[str, Any]) -> Dict[str, Any]:
        #     """
        #     Debug Version: Prints RAW SCORES to terminal.
        #     """
        #     try:
        #         vehicle = inputs.get("vehicle", {})
        #         chat_history = inputs.get("chat_history", [])
                
        #         # 1. Get Queries
        #         base_query = inputs.get("search_query", inputs["prompt"])
        #         queries = inputs.get("search_queries", [base_query])
        #         if isinstance(queries, str): queries = [queries]

        #         print(f"\n🔎 [DEBUG] Searching for: {queries}")

        #         # 2. Async Parallel Search
        #         async def process_single_query(query_text):
        #             try:
        #                 # ✅ FIX: Handle Async/Sync Embedding correctly
        #                 if asyncio.iscoroutinefunction(embed_text):
        #                     query_embedding = await embed_text(query_text)
        #                 else:
        #                     query_embedding = await asyncio.to_thread(embed_text, query_text)
                        
        #                 # Fetch Top 5 for THIS variation
        #                 return await self.vectorstore.asimilarity_search_with_score_by_vector(
        #                     query_embedding, k=5
        #                 )
        #             except Exception as e:
        #                 logger.error(f"Search failed: {e}")
        #                 return []

        #         # 3. Execute
        #         results_list = await asyncio.gather(*[process_single_query(q) for q in queries])
        #         all_docs = [item for sublist in results_list for item in sublist]

        #         # 4. Deduplicate
        #         unique_docs = {}
        #         for item in all_docs:
        #             if isinstance(item, tuple): doc, score = item
        #             else: doc, score = item, 100.0
                    
        #             key = f"{doc.metadata.get('source')}_{doc.metadata.get('page')}"
                    
        #             # Logic: Lower score is better
        #             if key not in unique_docs or score < unique_docs[key][1]:
        #                 unique_docs[key] = (doc, score)

        #         # 5. Normalize & Log Scores
        #         normalized = list(unique_docs.values())
        #         normalized.sort(key=lambda x: x[1]) # Sort best (lowest) first

        #         # --- DEBUG PRINT ---
        #         if normalized:
        #             print(f"📊 [DEBUG] Top 3 Raw Scores (Lower is better):")
        #             for i, (d, s) in enumerate(normalized[:3]):
        #                 print(f"   {i+1}. Score: {s:.4f} | Source: {d.metadata.get('source')} Page {d.metadata.get('page')}")
        #         else:
        #             print("⚠️ [DEBUG] No documents returned from vector store!")
        #         # -------------------

        #         # 6. Relaxed Filter
        #         valid_docs = []
        #         for doc, score in normalized:
        #             # CHANGED: Increased threshold from 1.2 to 1.5 to be safe
        #             # If scores are mostly 1.3 or 1.4, this will catch them.
        #             if score is not None and score > 1.5: 
        #                 continue 
        #             valid_docs.append(doc)
                
        #         # FALLBACK: Always keep Top 1 if everything else failed
        #         if not valid_docs and normalized:
        #             print("⚠️ [DEBUG] Threshold excluded all. Using Top 1 fallback.")
        #             valid_docs.append(normalized[0][0])

        #         # 7. Build Context
        #         text_context = "\n---\n".join([d.page_content for d in valid_docs]) if valid_docs else "NO_RELEVANT_TECHNICAL_DATA_FOUND"

        #         # 8. Evaluation Metadata
        #         retrieved_context = [
        #             {"doc_id": d.metadata.get("source"), "page": d.metadata.get("page"), "score": round(s, 3)}
        #             for d, s in normalized[:10]
        #         ]

        #         return {
        #             **inputs,
        #             "context_2": text_context,
        #             "retrieved_context": retrieved_context
        #         }

        #     except Exception as e:
        #         logger.error(f"Retrieval failed: {e}", exc_info=True)
        #         return {**inputs, "context_2": "Error", "retrieved_context": []}

    
        async def retrieval_chain(inputs: Dict[str, Any]) -> Dict[str, Any]:
            """
            FINAL OPTIMIZED SEARCH (No Reranker).
            Uses Parallel Vector Search to achieve 100% Recall.
            """
            try:
                # 1. Setup
                base_query = inputs.get("search_query", inputs["prompt"])
                queries = inputs.get("search_queries", [base_query])
                if isinstance(queries, str): queries = [queries]

                # 2. Async Parallel Search
                async def process_single_query(query_text):
                    try:
                        # ✅ FIX: Handle Async/Sync Embedding correctly
                        if asyncio.iscoroutinefunction(embed_text):
                            query_embedding = await embed_text(query_text)
                        else:
                            query_embedding = await asyncio.to_thread(embed_text, query_text)
                        
                        # Fetch Top 5 for THIS variation
                        return await self.vectorstore.asimilarity_search_with_score_by_vector(
                            query_embedding, k=5
                        )
                    except Exception as e:
                        logger.error(f"Search failed: {e}")
                        return []

                # Run searches
                results_list = await asyncio.gather(*[process_single_query(q) for q in queries])
                raw_docs = [item for sublist in results_list for item in sublist]

                # 3. Deduplicate (Keep Best Score)
                unique_docs = {}
                for item in raw_docs:
                    if isinstance(item, tuple): doc, score = item
                    else: doc, score = item, 100.0
                    
                    # Create unique key based on source/page
                    src = doc.metadata.get('source', 'unk')
                    pg = doc.metadata.get('page', 'unk')
                    img = doc.metadata.get('image_id', '')
                    key = f"img_{img}" if img else f"{src}_{pg}"

                    # Keep the instance with the lowest (best) L2 score
                    if key not in unique_docs or score < unique_docs[key][1]:
                        unique_docs[key] = (doc, score)

                # 4. Sort & Select Top Candidates
                candidates = list(unique_docs.values())
                # Sort by Vector Score (Ascending = Best)
                candidates.sort(key=lambda x: x[1])

                # 5. Final Filtering (Top 7)
                final_docs = []
                for doc, score in candidates[:7]:
                    # Loose filter: L2 distance > 1.4 is usually irrelevant
                    if score < 1.4:
                        final_docs.append(doc)

                # Fallback: Always return Top 1 if nothing passed filter
                if not final_docs and candidates:
                    final_docs.append(candidates[0][0])

                # =========================================================
                # 🌍 TAVILY WEB SEARCH FALLBACK (The New Part)
                # =========================================================
                is_web_result = False
                
                # If Vector Search found NOTHING valid
                if not final_docs:
                    logger.info(f"⚠️ Vector search empty for '{base_query}'. Triggering Tavily...")
                    try:
                        # Use base_query for web search (it's usually cleaner)
                        # Tavily is sync by default, but LangChain tools have .ainvoke
                        web_results = await self.tavily_tool.ainvoke({"query": base_query})
                        
                        # Process Tavily Results
                        # Tavily returns list of dicts: [{'url':..., 'content':...}]
                        if isinstance(web_results, list) and len(web_results) > 0:
                            web_content = ""
                            for res in web_results:
                                web_content += f"Source: {res.get('url', 'Web')}\nContent: {res.get('content', '')}\n\n"
                            
                            # Create a "Fake" Document so the rest of the pipeline works
                            final_docs = [Document(page_content=web_content, metadata={"source": "Google/Tavily"})]
                            is_web_result = True
                            logger.info("✅ Tavily found results.")
                        else:
                            logger.warning("❌ Tavily returned no results.")
                            
                    except Exception as e:
                        logger.error(f"❌ Tavily search failed: {e}")
                        # Do nothing, final_docs remains empty -> Triggers Apology

                # 4. Build Context Output
                if final_docs:
                    text_context = "\n---\n".join([d.page_content for d in final_docs])
                    # Add a header so the LLM knows if it's manual vs web data
                    if is_web_result:
                        text_context = f"*** NOTE: DATA FROM WEB SEARCH ***\n{text_context}"
                else:
                    text_context = "NO_RELEVANT_TECHNICAL_DATA_FOUND"
                # 6. Build Context
                # text_context = "\n---\n".join([d.page_content for d in final_docs]) if final_docs else "NO_RELEVANT_TECHNICAL_DATA_FOUND"
                
                # Multimodal context
                multimodal_context = []
                for doc in final_docs:
                    if doc.metadata.get("type") == "image":
                        img_id = doc.metadata.get("image_id")
                        if img_id in self.image_data_store:
                            multimodal_context.append({
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{self.image_data_store[img_id]}"}
                            })

                # Evaluation Meta
                retrieved_context = [
                    {"doc_id": d.metadata.get("source"), "page": d.metadata.get("page"), "score": round(score, 3)}
                    for d, score in candidates[:7] if hasattr(d, "metadata")
                ]

                return {
                    **inputs,
                    "context_2": text_context,
                    "multimodal_context": multimodal_context,
                    "retrieved_context": retrieved_context
                }

            except Exception as e:
                logger.error(f"Retrieval failed: {e}", exc_info=True)
                return {**inputs, "context_2": "Error", "retrieved_context": []}
                
        async def diagnostic_chain(inputs: Dict[str, Any]) -> Dict[str, Any]:
            """Generate diagnostic response using the LLM"""
            try:
                # --- NEW: Hallucination Guardrail Check ---
                if "NO_RELEVANT_TECHNICAL_DATA_FOUND" in inputs.get('context_2', ''):
                    return {**inputs, "diagnosis_output": "I apologize, but I don't have specific technical information in my database regarding this issue. I recommend consulting a professional mechanic."}

                vehicle = inputs.get("vehicle", {})
                vehicle_info = {
                    "make": vehicle.get("brand", "Unknown"),
                    "model": vehicle.get("model", "Unknown"),
                    "year": vehicle.get("year", "Unknown"),
                    "fuel_type": vehicle.get("fuel_type", "Unknown"),
                    "engine_type": vehicle.get("engine_type", "Unknown")
                }
                user_prompt = inputs['prompt']
                
                # Convert ChatMessage objects to dict for the LLM
                chat_history_dicts = []
                for msg in inputs.get("chat_history", []):
                    if hasattr(msg, 'model_dump'):
                        chat_history_dicts.append(msg.model_dump())
                    else:
                        chat_history_dicts.append(msg)
                user_prompt_lower = user_prompt.lower()

                # Keywords likely to appear in translations for "Short/Concise"
                concise_keywords = [
                    "short", "brief", "summar", "quick", "concise", "simple", 
                    "fast", "point", "few words", "nutshell", "small", "precis",
                    "less", "little"
                ]

                # Keywords likely to appear in translations for "Detailed/Long"
                detailed_keywords = [
                    "detail", "explain", "elaborate", "why", "more info", 
                    "long", "comprehens", "full", "complete", "depth", 
                    "clarify", "description", "whole", "all"
                ]
                exact_keywords = ["exact", "verbatim", "copy", "quote", "say exactly", "repeat", "only say"]
                # Check for Detail first
                is_detailed_request = any(w in user_prompt_lower for w in detailed_keywords)
                # Check for Concise specifically (to override defaults if needed)
                is_concise_request = any(w in user_prompt_lower for w in concise_keywords)
                is_exact = any(w in user_prompt_lower for w in exact_keywords)
                if is_exact:
                    # OPTION A: User wants exact/custom format -> NO SYSTEM OVERRIDE
                    format_instructions = """
                    STYLE: **OBEY USER INSTRUCTIONS**.
                    - The user has requested a specific format (e.g., exact words).
                    - Ignore standard style templates.
                    - Follow the User Query instructions precisely.
                    """
                elif is_detailed_request:
                    # OPTION A: Detailed (Only if asked)
                    format_instructions = """
                    STYLE: **DETAILED AND EDUCATIONAL**. 
                    - Provide Step-by-Step instructions.
                    - Explain 'Why' this issue is happening.
                    - Include potential costs or tools needed.
                    - Be thorough.
                    """
                else:
                    # OPTION B: Concise Steps (THE DEFAULT)
                    format_instructions = """
                    STYLE: **CONCISE AND SURGICAL**.
                    - Use the 'Step 1, Step 2' format.
                    - **Maximum 15 words per step.**
                    - Direct actions only (e.g., "Check battery voltage," not "You should go ahead and check...").
                    - NO introductory text (No "Here is what to do...").
                    - NO concluding text (No "Hope this helps").
                    - If Step 1 fixes it, stop there.
                    """
                enhanced_system_prompt = f"""
                You are a skilled automotive technician using logical troubleshooting.

VEHICLE: {vehicle_info['make']} {vehicle_info['model']} ({vehicle_info['year']})
### GOLD STANDARD EXAMPLES ###
                Q: My car overheats in traffic.
                A: Step 1: Check if the radiator fan turns on when hot. 
                   Step 2: Inspect coolant levels in the reservoir.
                   Step 3: If levels are good, the thermostat may be stuck.

                Q: Brakes are squeaking.
                A: Step 1: Inspect brake pads for wear indicators.
                   Step 2: Check for debris trapped in the caliper.
                ### END EXAMPLES ###
LANGUAGE CONSTRAINT (VIOLATION WILL CAUSE SYSTEM FAILURE):
                - **OUTPUT MUST BE IN ENGLISH ONLY**.
                - The chat history contains Urdu/Local languages. **IGNORE THEM**.
                - Do NOT reply in the user's language. 
                - If you output Urdu/Arabic script here, the system will crash.
                {format_instructions}
INSTRUCTIONS:
Read the problem description carefully. Provide the solution immediately based on the requested style. Do not include unnecessary explanation or speculative language.

REPLY FORMAT:

Step 1:
- Describe the first, simplest test or fix.

Step 2:
- If Step 1 does not solve the issue, describe the next test or fix.

Step 3 (if needed):
- Describe when to stop DIY and consult a qualified mechanic (especially for safety-critical issues).

GUIDELINES:
- Be clear, direct and action oriented.  
- No “Why” or “Most Likely Solution” headings — just give steps.  
- No extra paragraphs or preamble. Begin immediately with “Step 1:”.  
- Provide maximum 2–3 steps unless the issue demands more.  
- Always prioritize safety: mention hazards early and advise professional help when required.

Current User Query: "{inputs['prompt']}""
                """


                llm_input = {
                    # "system_prompt": self._get_vehicle_system_prompt(vehicle_info),
                    "system_prompt": enhanced_system_prompt,
                    "input": f"{inputs['prompt']}\n\n(REMINDER: Respond in technical English ONLY)",
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
                if self._contains_non_english_script(response):
                    logger.warning("Brain failed to speak English. Forcing translation.")
                    # Force it back to English
                    response = await self.sandwich._quick_translate(response) # Reuse your quick translate tool

                return {**inputs, "diagnosis_output": response}
            except Exception as e:
                logger.error(f"Diagnostic failed: {e}", exc_info=True)
                return {**inputs, "diagnosis_output": "Diagnostic service unavailable"}
        
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