import httpx
import asyncio
import time
import json
import logging
from datetime import datetime

# Logging setup to track failures
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LoadTester")

class AutomotiveAISystemTest:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.token = None
        self.session_id = None
        self.client = httpx.AsyncClient(timeout=60.0)

    async def login(self, email, password):
        """Authenticates and retrieves the Bearer token."""
        print(f"🔑 Attempting Login for: {email}")
        # Note: Adjust URL path /token or /login based on your auth implementation
        response = await self.client.post(
            f"{self.base_url}/auth/token", 
            data={"username": email, "password": password}
        )
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.client.headers.update({"Authorization": f"Bearer {self.token}"})
            print("✅ Login Successful")
        else:
            raise Exception(f"Login Failed: {response.text}")

    async def start_session(self):
        """Initializes a new chat session."""
        response = await self.client.post(f"{self.base_url}/chat/start")
        data = response.json()
        self.session_id = data.get("session_id")
        print(f"🚀 Session Started: {self.session_id}")
        return self.session_id

    async def send_message(self, text: str, lang: str = "en", vehicle: dict = None):
        """Sends a message as multipart/form-data to match FastAPI requirements."""
        
        # Payload fields (must all be strings for multipart)
        data = {
            "message": text,
            "session_id": str(self.session_id) if self.session_id else "",
            "language": lang
        }
        
        if vehicle:
            data["vehicle_json"] = json.dumps(vehicle)

        # Force multipart/form-data by passing an empty files dictionary
        # Even though image is Optional, the presence of a File parameter 
        # in the route requires this content type.
        files = {"image": (None, b"")} 

        start_time = time.perf_counter()
        
        response = await self.client.post(
            f"{self.base_url}/chat/message",
            data=data,
            files=files
        )
        
        latency = time.perf_counter() - start_time
        
        # --- LOGGING THE ERROR FOR DEBUGGING ---
        if response.status_code != 200:
            print(f"❌ Server returned {response.status_code}: {response.text}")
            return {"success": False, "error": response.text, "latency": latency}
        
        return {
            "success": True,
            "latency": latency,
            "data": response.json()
        }
async def run_failure_test_scenarios():
    # --- CONFIGURATION ---
    BASE_URL = "http://localhost:8000" # Change to your server URL
    EMAIL = "johndoe13@example.com"
    PASSWORD = "Str0ngP@ssword"
    
    tester = AutomotiveAISystemTest(BASE_URL)
    
    try:
        await tester.login(EMAIL, PASSWORD)
        session_id = await tester.start_session()
        
        # SHARED VEHICLE OBJECT
        yamaha_r15 = {
    "brand": "Yamaha", 
    "model": "YZF-R15", 
    "year": 2022,
    "user_id": str(session_id),  # Added missing field
    "category": "motorcycle"     # Added missing field (e.g., 'bike', 'car', 'motorcycle')
}
        # --- SCENARIO 1: ROMAN URDU / SLANG + RAG RETRIEVAL ---
        # Goal: Can the system translate "thak thak" and find engine knocking data?
        print("\n[Test 1] Testing Roman Urdu Slang & RAG...")
        res1 = await tester.send_message(
    text="Yaar meri bike start nahi ho rahi, engine se 'thak thak' sound aa rahi hai.",
    lang="Urdu",
    vehicle=yamaha_r15
)

        if res1['success']:
            print(f"⏱️ Latency: {res1['latency']:.2f}s")
            print(f"🤖 Response: {res1['data']['response'][:100]}...")
        else:
            print(f"❌ Test 1 Failed! Error: {res1['error']}")
            return # Stop here if the first one fails

        


        # --- SCENARIO 2: HISTORY PERSISTENCE (THE "CONTEXT" TEST) ---
        # Goal: If we don't mention the bike/noise, does it know what we are fixing?
        print("\n[Test 2] Testing Context History Maintenance...")
        res2 = await tester.send_message(
            text="Isko theek karne mein kitna kharcha aayega approximate?",
            lang="Urdu"
        )
        if "Yamaha" in res2['data']['english_response'] or "repair" in res2['data']['english_response']:
            print("✅ History Maintained: System knows the previous context.")
        else:
            print("❌ History Lost: System provided a generic response.")

        # --- SCENARIO 3: CONSTRAINT MATCHING (THE "SHORT RESPONSE" TEST) ---
        # Goal: Force the LLM to follow a structural constraint (3 bullets)
        print("\n[Test 3] Testing Constraint Matching (3 Short Bullets)...")
        res3 = await tester.send_message(
            text="Provide the fix in exactly 3 short bullet points only.",
            lang="English"
        )
        bullet_count = res3['data']['response'].count("•") + res3['data']['response'].count("-") + res3['data']['response'].count("1.")
        print(f"⏱️ Latency (Follow-up): {res3['latency']:.2f}s") # Should be lower than Test 1
        print(f"🤖 Output:\n{res3['data']['response']}")
        
        # --- SCENARIO 4: STRESS TEST (RAPID FIRE) ---
        # Goal: Break the system with rapid requests to trigger 429 or JSON errors
        print("\n[Test 4] Stress Testing (Concurrency)...")
        tasks = [tester.send_message(text="What about tires?", lang="en") for _ in range(3)]
        stress_results = await asyncio.gather(*tasks)
        for i, r in enumerate(stress_results):
            status = "✅" if r['success'] else f"❌ Error: {r['error']}"
            print(f"Request {i+1}: {status}")

    finally:
        await tester.client.aclose()

if __name__ == "__main__":
    asyncio.run(run_failure_test_scenarios())
# # """
# # Test Tavily Connection
# # ----------------------
# # Checks if the API key is valid and can fetch data from the web.
# # """
# # import os
# # from dotenv import load_dotenv
# # from langchain_community.tools.tavily_search import TavilySearchResults

# # # Load environment variables
# # load_dotenv()

# # def test_connection():
# #     print("🌍 Testing Tavily API Connection...")
    
# #     api_key = os.getenv("TAVILY_API_KEY")
# #     if not api_key:
# #         print("❌ CRITICAL: TAVILY_API_KEY is missing from .env file!")
# #         return

# #     try:
# #         # Initialize Tool
# #         tool = TavilySearchResults(max_results=1)
        
# #         # Run a query that definitely requires the internet
# #         query = "Who won the 2024 Formula 1 Championship?"
# #         print(f"🔎 Searching for: '{query}'...")
        
# #         results = tool.invoke({"query": query})
        
# #         if results and isinstance(results, list):
# #             print("\n✅ SUCCESS: Web Search Works!")
# #             print("-" * 50)
# #             content = results[0].get('content', 'No content')
# #             url = results[0].get('url', 'No URL')
# #             print(f"Source: {url}")
# #             print(f"Snippet: {content[:150]}...")
# #             print("-" * 50)
# #         else:
# #             print("⚠️ WARNING: Search returned no results (Check your API quota).")

# #     except Exception as e:
# #         print(f"\n❌ FAILURE: Could not connect to Tavily.\nError: {e}")

# # if __name__ == "__main__":
# #     test_connection()

# # """
# # Test RAG Fallback Logic
# # -----------------------
# # Simulates a ChatService with an EMPTY Vector Store.
# # Verifies that the system correctly falls back to Tavily.
# # """
# # import asyncio
# # import os
# # from dotenv import load_dotenv
# # from langchain_community.tools.tavily_search import TavilySearchResults
# # from langchain_core.documents import Document

# # load_dotenv()

# # async def simulate_retrieval_chain():
# #     print("🔧 Initializing Logic Test...")
    
# #     # 1. MOCK: Setup a Tavily Tool (Real)
# #     tavily_tool = TavilySearchResults(max_results=3)
    
# #     # 2. MOCK: Setup a "Vector Store" that returns NOTHING (Simulating failure)
# #     print("📉 Simulating Empty Vector Store...")
# #     vector_results = [] # <--- This is empty!
    
# #     # 3. RUN THE LOGIC (Copied from your ChatService)
# #     query = "latest recalls for 2024 Honda Civic"
# #     final_docs = []
# #     is_web_result = False
    
# #     # Logic Step: If vector results are empty, try Tavily
# #     if not vector_results:
# #         print(f"⚠️ Vector search empty for '{query}'. Triggering Tavily...")
# #         try:
# #             # Run Web Search
# #             web_results = await tavily_tool.ainvoke({"query": query})
            
# #             if isinstance(web_results, list) and len(web_results) > 0:
# #                 web_content = ""
# #                 for res in web_results:
# #                     web_content += f"Source: {res.get('url', 'Web')}\nContent: {res.get('content', '')}\n\n"
                
# #                 # Create Fake Document
# #                 final_docs = [Document(page_content=web_content, metadata={"source": "Google/Tavily"})]
# #                 is_web_result = True
# #                 print("✅ Tavily found results.")
# #             else:
# #                 print("❌ Tavily returned no results.")
                
# #         except Exception as e:
# #             print(f"❌ Tavily search failed: {e}")

# #     # 4. REPORT RESULTS
# #     print("\n" + "="*40)
# #     print("📊 FINAL OUTCOME")
# #     print("="*40)
    
# #     if is_web_result:
# #         print("✅ SYSTEM WORKED: It switched to Web Search.")
# #         print(f"📄 Retrieved Content Length: {len(final_docs[0].page_content)} chars")
# #         print(f"🔗 Source Metadata: {final_docs[0]}")
# #     else:
# #         print("❌ SYSTEM FAILED: It did not switch to Web Search.")

# # if __name__ == "__main__":
# #     asyncio.run(simulate_retrieval_chain())
    
# # with groq
# # """
# # Advanced RAG Evaluation with Rate Limit Handling
# # """
# # import asyncio
# # import json
# # import time
# # import sys
# # import os
# # import random
# # import pandas as pd
# # from pathlib import Path
# # from dataclasses import dataclass
# # from typing import List
# # from dotenv import load_dotenv

# # # --- NLP METRICS ---
# # from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
# # from rouge_score import rouge_scorer
# # try:
# #     from bert_score import score as bert_score
# #     BERTSCORE_AVAILABLE = True
# # except ImportError:
# #     BERTSCORE_AVAILABLE = False
# #     print("⚠️  bert-score library not found. Skipping semantic similarity.")

# # # --- SETUP ---
# # load_dotenv()
# # current_dir = Path(__file__).resolve().parent
# # sys.path.append(str(current_dir))

# # try:
# #     from fastapi import Request
# #     from services.chat_service import ChatService
# #     from services.multimodal_embeddings import embed_text
# #     from services.diagnostic_agent import create_diagnostic_agent
# #     from services.intent_classifier import SandwichProcessor
# #     from services.image_analyzer import ImageAnalyzer
# # except ImportError as e:
# #     print(f"❌ Import Error: {e}")
# #     sys.exit(1)

# # from langchain_community.vectorstores import FAISS
# # from langchain_core.embeddings import Embeddings

# # @dataclass
# # class EvaluationData:
# #     query_id: str
# #     query_text: str
# #     relevant_doc_ids: List[str]
# #     reference_answer: str
# #     retrieved_doc_ids: List[str] = None
# #     generated_text: str = ""
# #     start_time: float = 0.0
# #     end_time: float = 0.0
    
# #     def __post_init__(self):
# #         if self.retrieved_doc_ids is None: self.retrieved_doc_ids = []

# # class MockAppState:
# #     def __init__(self, vectorstore, image_store, diagnostic_agent, image_analyzer, sandwich_processor):
# #         self.vectorstore = vectorstore
# #         self.image_data_store = image_store
# #         self.diagnostic_agent = diagnostic_agent
# #         self.image_analyzer = image_analyzer
# #         self.sandwich_processor = sandwich_processor

# # class MockApp:
# #     def __init__(self, state):
# #         self.state = state

# # class FunctionalEmbeddings(Embeddings):
# #     def __init__(self, embed_func):
# #         self.func = embed_func
# #     def embed_documents(self, texts): return [self.func(t).tolist() for t in texts]
# #     def embed_query(self, text): return self.func(text).tolist()

# # class AdvancedEvaluator:
# #     def __init__(self):
# #         print("🔧 Initializing Evaluation System...")
# #         api_key = os.getenv("GROQ_API_KEY")
# #         if not api_key: sys.exit("❌ GROQ_API_KEY missing.")

# #         cache_dir = current_dir / ".vector_cache"
# #         faiss_files = list(cache_dir.glob("**/*.faiss"))
# #         if not faiss_files: sys.exit("❌ No .faiss index found.")
        
# #         target_file = faiss_files[0]
# #         try:
# #             vectorstore = FAISS.load_local(
# #                 str(target_file.parent), 
# #                 embeddings=FunctionalEmbeddings(embed_text),
# #                 allow_dangerous_deserialization=True,
# #                 index_name=target_file.stem
# #             )
# #         except Exception as e:
# #             sys.exit(f"❌ FAISS Load Error: {e}")

# #         try:
# #             diag_agent = create_diagnostic_agent(api_key)
# #             sandwich = SandwichProcessor(api_key)
# #             class MockImg:
# #                 async def analyze(self, *a, **k): return "Mock"
            
# #             mock_state = MockAppState(vectorstore, {}, diag_agent, MockImg(), sandwich)
# #             self.chat_service = ChatService(Request({"type": "http", "app": MockApp(mock_state)}))
# #         except Exception as e:
# #             sys.exit(f"❌ Service Init Error: {e}")
            
# #         self.rouge = rouge_scorer.RougeScorer(['rougeL'], use_stemmer=True)
# #         self.smooth = SmoothingFunction().method1

# #     async def run(self, test_cases):
# #         results = []
# #         print(f"\n🚀 Evaluating {len(test_cases)} Queries (With Rate Limit Protection)...")
        
# #         for i, case in enumerate(test_cases):
# #             print(f"   [{i+1}/{len(test_cases)}] {case.query_text[:50]}...")
            
# #             # --- RETRY LOGIC FOR RATE LIMITS ---
# #             max_retries = 3
# #             success = False
            
# #             case.start_time = time.time()
# #             for attempt in range(max_retries):
# #                 try:
# #                     output = await self.chat_service.chain.ainvoke({
# #                         "prompt": case.query_text, "image_url": None, 
# #                         "vehicle": {}, "chat_history": [], "intent": "technical_question"
# #                     })
# #                     case.generated_text = output.get("diagnosis_output", "NO_OUTPUT")
                    
# #                     raw_docs = output.get("retrieved_context", [])
# #                     case.retrieved_doc_ids = []
# #                     for d in raw_docs:
# #                         src = d.get("doc_id", "unknown")
# #                         pg = d.get("page", "unknown")
# #                         case.retrieved_doc_ids.append(f"{src} | Page: {pg}")
                    
# #                     success = True
# #                     break # Success, exit retry loop
                    
# #                 except Exception as e:
# #                     err_str = str(e)
# #                     if "429" in err_str or "Rate limit" in err_str:
# #                         wait_time = (attempt + 1) * 20 + random.randint(1, 5) # 20s, 40s, 60s
# #                         print(f"     ⚠️ Rate Limit Hit (429). Waiting {wait_time}s...")
# #                         await asyncio.sleep(wait_time)
# #                     else:
# #                         print(f"     ❌ Error: {e}")
# #                         case.generated_text = "ERROR"
# #                         break
            
# #             if not success:
# #                 print("     ❌ Failed after retries.")
            
# #             case.end_time = time.time()
# #             results.append(self._calc_metrics(case))
            
# #             # Be nice to the API between successful calls
# #             await asyncio.sleep(5) 
            
# #         return pd.DataFrame(results)

# #     def _calc_metrics(self, data):
# #         latency = data.end_time - data.start_time
        
# #         # --- Retrieval Metrics ---
# #         gt_source = data.relevant_doc_ids[0]
# #         # Handle "Page: 0" vs "Page: 1"
# #         gt_page_str = data.relevant_doc_ids[1].split(":")[-1].strip() if len(data.relevant_doc_ids) > 1 else None
        
# #         hits = 0
# #         first_hit_rank = 0
        
# #         for rank, doc in enumerate(data.retrieved_doc_ids, 1):
# #             if gt_source in doc:
# #                 if gt_page_str:
# #                     try:
# #                         ret_page = int(doc.split("Page: ")[1])
# #                         # Exact match required now that we fixed metadata
# #                         if ret_page == int(gt_page_str):
# #                             hits += 1
# #                             if first_hit_rank == 0: first_hit_rank = rank
# #                     except: pass
# #                 else:
# #                     hits += 1

# #         k = len(data.retrieved_doc_ids)
# #         ret_prec = hits / k if k > 0 else 0
# #         ret_rec = 1.0 if hits > 0 else 0.0
# #         ret_f1 = (2 * ret_prec * ret_rec) / (ret_prec + ret_rec) if (ret_prec + ret_rec) > 0 else 0.0
# #         mrr = (1.0 / first_hit_rank) if first_hit_rank > 0 else 0.0
        
# #         # --- Generation Metrics ---
# #         ref_tokens = data.reference_answer.lower().split()
# #         gen_tokens = data.generated_text.lower().split()
# #         bleu = sentence_bleu([ref_tokens], gen_tokens, smoothing_function=self.smooth)
# #         rouge_l = self.rouge.score(data.reference_answer, data.generated_text)['rougeL'].fmeasure
        
# #         bert_p, bert_r, bert_f1 = 0.0, 0.0, 0.0
# #         if BERTSCORE_AVAILABLE and len(data.generated_text) > 5 and data.generated_text != "ERROR":
# #             try:
# #                 P, R, F1 = bert_score([data.generated_text], [data.reference_answer], lang="en", verbose=False)
# #                 bert_p, bert_r, bert_f1 = P.mean().item(), R.mean().item(), F1.mean().item()
# #             except: pass

# #         return {
# #             "query": data.query_text,
# #             "latency": round(latency, 3),
# #             "retrieval_precision": round(ret_prec, 3),
# #             "retrieval_recall": round(ret_rec, 3),
# #             "retrieval_f1": round(ret_f1, 3),
# #             "retrieval_mrr": round(mrr, 3),
# #             "bleu_score": round(bleu, 3),
# #             "rouge_l": round(rouge_l, 3),
# #             "bert_precision": round(bert_p, 3),
# #             "bert_recall": round(bert_r, 3),
# #             "bert_f1": round(bert_f1, 3),
# #         }

# # async def main():
# #     json_path = "test_ground_truth.json"
# #     if not Path(json_path).exists():
# #         print(f"❌ {json_path} not found.")
# #         return

# #     with open(json_path, "r") as f:
# #         raw = json.load(f)
    
# #     # Use first 15 for a quick but representative test
# #     test_cases = [EvaluationData(
# #         query_id=x["id"], query_text=x["question"], 
# #         relevant_doc_ids=x["relevant_doc_ids"], reference_answer=x["reference_answer"]
# #     ) for x in raw[:15]]

# #     evaluator = AdvancedEvaluator()
# #     df = await evaluator.run(test_cases)
    
# #     print("\n" + "="*60)
# #     print("🚗🏍️  FINAL METRICS (With Retries)")
# #     print("="*60)
# #     print(f"Recall (Hit Rate): {df['retrieval_recall'].mean():.3f}")
# #     print(f"MRR:               {df['retrieval_mrr'].mean():.3f}")
# #     print(f"BLEU:              {df['bleu_score'].mean():.3f}")
# #     print(f"Semantic F1:       {df['bert_f1'].mean():.3f}")
# #     print("="*60)
# #     df.to_csv("evaluation_results_final.csv", index=False)

# # if __name__ == "__main__":
# #     asyncio.run(main())



# # # Offline FAISS Index Inspection Script
# # """
# # OFFLINE Vector Search Verification (No Reranker)
# # ------------------------------------------------
# # Tests purely the Vector Search accuracy.
# # Expected Result: ~100% Recall (Rank 1-5).
# # """

# # import sys
# # import os
# # import asyncio
# # import json
# # import pandas as pd
# # from pathlib import Path
# # from dotenv import load_dotenv

# # # --- SETUP ---
# # current_dir = Path(__file__).resolve().parent
# # sys.path.append(str(current_dir))
# # load_dotenv()

# # try:
# #     from langchain_community.vectorstores import FAISS
# #     # Import your actual embedding function
# #     from services.multimodal_embeddings import embed_text
# # except ImportError as e:
# #     print(f"❌ Import Error: {e}")
# #     sys.exit(1)

# # # Wrapper for serialization (LangChain requirement)
# # from langchain_core.embeddings import Embeddings
# # class FunctionalEmbeddings(Embeddings):
# #     def __init__(self, f): self.f = f
# #     def embed_documents(self, t): return [self.f(x).tolist() for x in t]
# #     def embed_query(self, t): return self.f(t).tolist()

# # async def verify_vector_only():
# #     print("🔧 Initializing Vector-Only Verification...")

# #     # 1. Load Ground Truth
# #     json_path = "test_ground_truth.json"
# #     if not Path(json_path).exists():
# #         print("❌ test_ground_truth.json not found.")
# #         return
# #     with open(json_path, "r") as f:
# #         # Test ALL cases in the file
# #         test_cases = json.load(f) 

# #     # 2. Load Vector Store
# #     cache_dir = current_dir / ".vector_cache"
# #     faiss_files = list(cache_dir.glob("**/*.faiss"))
# #     if not faiss_files:
# #         print("❌ No index found.")
# #         return
# #     target_file = faiss_files[0]
    
# #     vectorstore = FAISS.load_local(
# #         str(target_file.parent), 
# #         embeddings=FunctionalEmbeddings(embed_text),
# #         allow_dangerous_deserialization=True,
# #         index_name=target_file.stem
# #     )
    
# #     print(f"\n🚀 Testing {len(test_cases)} Queries using Pure Vector Search...")
    
# #     results_data = []

# #     for i, case in enumerate(test_cases):
# #         query = case["question"]
# #         gt_page = int(case["relevant_doc_ids"][1].split(":")[1].strip())
        
# #         # --- VECTOR SEARCH ONLY ---
# #         # Handle async/sync embedding
# #         if asyncio.iscoroutinefunction(embed_text):
# #             emb = await embed_text(query)
# #         else:
# #             emb = await asyncio.to_thread(embed_text, query)
        
# #         # We check Top 5 (Standard RAG setting)
# #         vector_docs = vectorstore.similarity_search_with_score_by_vector(emb, k=5)
        
# #         found = False
# #         rank = -1
        
# #         for r, (doc, score) in enumerate(vector_docs, 1):
# #             if doc.metadata.get("page") == gt_page:
# #                 found = True
# #                 rank = r
# #                 break
        
# #         status = "✅ FOUND" if found else "❌ MISSING"
# #         print(f"[{i+1}] {status} | Rank: {rank if found else '>5'} | Query: {query[:30]}...")
        
# #         results_data.append({
# #             "id": case["id"],
# #             "found": found,
# #             "rank": rank
# #         })

# #     # Summary
# #     score = sum(1 for r in results_data if r['found'])
# #     print("\n" + "="*50)
# #     print(f"🏆 Final Vector Recall: {score}/{len(test_cases)} ({score/len(test_cases)*100:.1f}%)")
# #     print("="*50)

# #     # Show failures if any
# #     failures = [r for r in results_data if not r['found']]
# #     if failures:
# #         print("\n❌ Failed Queries:")
# #         print(pd.DataFrame(failures))

# # if __name__ == "__main__":
# #     asyncio.run(verify_vector_only())




# # Advanced RAG Evaluation with Rate Limit Handling
# import sys
# import os
# import asyncio
# import json
# import re
# import pandas as pd
# from pathlib import Path
# from dotenv import load_dotenv

# # --- SETUP ---
# load_dotenv()
# current_dir = Path(__file__).resolve().parent
# sys.path.append(str(current_dir))

# try:
#     from langchain_community.vectorstores import FAISS
#     from services.multimodal_embeddings import embed_text
#     from langchain_core.embeddings import Embeddings
# except ImportError as e:
#     print(f"❌ Import Error: {e}")
#     sys.exit(1)

# class FunctionalEmbeddings(Embeddings):
#     def __init__(self, f): self.f = f
#     def embed_documents(self, t): return [self.f(x).tolist() for x in t]
#     def embed_query(self, t): return self.f(t).tolist()

# def rrf_score(results_list, k=60):
#     rrf_map = {} 
#     for result_set in results_list:
#         for rank, (doc, l2_score) in enumerate(result_set, 1):
#             if l2_score > 1.5: continue 
            
#             src = doc.metadata.get("source", "unk")
#             pg = doc.metadata.get("page", -1)
#             key = f"{src}_{pg}"
            
#             if key not in rrf_map:
#                 rrf_map[key] = [doc, 0.0]
#             rrf_map[key][1] += 1.0 / (k + rank)
    
#     return sorted(rrf_map.values(), key=lambda x: x[1], reverse=True)

# async def verify_sorting_performance():
#     print("🔧 Initializing Sorting Comparison Verification...")
    
#     json_path = current_dir / "test_ground_truth.json"
#     with open(json_path, "r") as f:
#         test_cases = json.load(f)

#     cache_dir = current_dir / ".vector_cache"
#     faiss_files = list(cache_dir.glob("*.faiss"))
#     index_name = faiss_files[0].stem
#     print(f"📂 Loading index: {index_name}")

#     vectorstore = FAISS.load_local(
#         str(cache_dir), 
#         embeddings=FunctionalEmbeddings(embed_text),
#         allow_dangerous_deserialization=True,
#         index_name=index_name
#     )

#     comparison_results = []
#     print(f"🚀 Benchmarking {len(test_cases)} queries...")

#     for i, case in enumerate(test_cases):
#         query = case["question"]
        
#         # --- FIX: Target the "Page: X" string specifically ---
#         # We look for the item in the list that contains the word 'Page'
#         gt_page = -1
#         for identifier in case["relevant_doc_ids"]:
#             if "Page" in identifier:
#                 numbers = re.findall(r'\d+', identifier)
#                 if numbers:
#                     gt_page = int(numbers[0])
#                     break
        
#         if gt_page == -1:
#             print(f"⚠️ Warning: Could not find page for Query {i+1}. Skipping...")
#             continue
        
#         # Simulate Multi-Query
#         queries = [query, f"technical repair for {query}"] 
        
#         raw_results_list = []
#         for q in queries:
#             emb = await embed_text(q) if asyncio.iscoroutinefunction(embed_text) else await asyncio.to_thread(embed_text, q)
#             res = await vectorstore.asimilarity_search_with_score_by_vector(emb, k=10)
#             raw_results_list.append(res)

#         # Strategy 1: Old L2 Sorting
#         flat_l2 = [item for sublist in raw_results_list for item in sublist]
#         l2_sorted = sorted(flat_l2, key=lambda x: x[1])[:5]
        
#         # Strategy 2: New RRF Sorting
#         rrf_results = rrf_score(raw_results_list)[:5]

#         l2_rank = next((r for r, (d, s) in enumerate(l2_sorted, 1) if int(d.metadata.get("page", -1)) == gt_page), 0)
#         rrf_rank = next((r for r, val in enumerate(rrf_results, 1) if int(val[0].metadata.get("page", -1)) == gt_page), 0)

#         comparison_results.append({
#             "l2_hit": 1 if l2_rank > 0 else 0,
#             "l2_mrr": 1/l2_rank if l2_rank > 0 else 0,
#             "rrf_hit": 1 if rrf_rank > 0 else 0,
#             "rrf_mrr": 1/rrf_rank if rrf_rank > 0 else 0
#         })

#     df = pd.DataFrame(comparison_results)
#     print("\n" + "="*55)
#     print(f"{'METRIC':<20} | {'OLD (L2)':<12} | {'NEW (RRF)':<12}")
#     print("-" * 55)
#     print(f"{'Recall @ 5':<20} | {df['l2_hit'].mean():.3f}       | {df['rrf_hit'].mean():.3f}")
#     print(f"{'Mean Reciprocal Rank':<20} | {df['l2_mrr'].mean():.3f}       | {df['rrf_mrr'].mean():.3f}")
#     print("="*55)

# if __name__ == "__main__":
#     asyncio.run(verify_hybrid_metrics() if 'verify_hybrid_metrics' in globals() else verify_sorting_performance())