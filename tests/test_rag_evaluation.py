"""
RAG Evaluation System for AutoAssist
Connects to the REAL ChatService to evaluate performance.
Bypasses the "Sandwich" translation layers to test the Core Logic (RAG + Reasoning) directly.
"""

import asyncio
import json
import time
import sys
import logging
import pickle
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd
from dataclasses import dataclass
from dotenv import load_dotenv

# --- 1. LOAD ENV VARS (Critical for Groq API) ---
load_dotenv() 

# --- 2. PATH SETUP ---
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent 
sys.path.append(str(project_root))

# --- APP IMPORTS ---
try:
    from fastapi import Request
    from services.chat_service import ChatService
    from models.chat import ChatSession
    from models.vehicle import VehicleModel
    # Import specific embedding function
    from services.multimodal_embeddings import embed_text
    # Import Agent Creators
    from services.diagnostic_agent import create_diagnostic_agent
    from services.intent_classifier import SandwichProcessor
    from services.image_analyzer import ImageAnalyzer
except ImportError as e:
    print(f"❌ Import Error: {e}")
    sys.exit(1)

# --- ML/VECTOR IMPORTS ---
from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings

# --- METRIC LIBRARIES ---
import numpy as np
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
from rouge_score import rouge_scorer

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RAG_Eval")

# --- GLOBAL CHECK FOR BERTSCORE ---
try:
    from bert_score import score as bert_score
    BERTSCORE_AVAILABLE = True
except ImportError:
    BERTSCORE_AVAILABLE = False
    print("⚠️  bert-score library not found. Semantic similarity will be skipped.")

@dataclass
class EvaluationData:
    """Data structure for a single evaluation instance"""
    query_id: str
    query_text: str
    relevant_doc_ids: List[str] # Ground Truth: List of Doc IDs (source names)
    reference_text: str         # Ground Truth: The ideal answer
    
    # Fields to be filled by the AI during testing
    retrieved_doc_ids: List[str] = None
    similarity_scores: List[float] = None
    generated_text: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    
    def __post_init__(self):
        if self.retrieved_doc_ids is None: self.retrieved_doc_ids = []
        if self.similarity_scores is None: self.similarity_scores = []

# --- MOCKING CLASSES ---
class MockAppState:
    """Simulates FastAPI app.state to hold ALL dependencies"""
    def __init__(self, vectorstore, image_store, diagnostic_agent, image_analyzer, sandwich_processor):
        self.vectorstore = vectorstore
        self.image_data_store = image_store
        self.diagnostic_agent = diagnostic_agent
        self.image_analyzer = image_analyzer
        self.sandwich_processor = sandwich_processor

class MockApp:
    def __init__(self, state):
        self.state = state

class FunctionalEmbeddings(Embeddings):
    """Wrapper to make your project's embed_text function compatible with LangChain"""
    def __init__(self, embed_func):
        self.func = embed_func
        
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        # Handle numpy array return type
        return [self.func(t).tolist() for t in texts] 
        
    def embed_query(self, text: str) -> List[float]:
        return self.func(text).tolist()

class RealSystemEvaluator:
    def __init__(self):
        print("🔧 Initializing Real Chat Service for Evaluation...")
        
        # Check API Key
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            print("  ❌ CRITICAL: GROQ_API_KEY not found in environment variables.")
            sys.exit(1)

        # --- 1. LOCATE CACHE DIRECTORY ---
        potential_paths = [
            project_root / ".vector_cache",
            project_root / "src" / ".vector_cache",
            Path(".vector_cache")
        ]
        
        cache_dir = None
        for p in potential_paths:
            if p.exists():
                cache_dir = p
                print(f"  📂 Found cache directory at: {cache_dir}")
                break
        
        if not cache_dir:
            print(f"  ❌ CRITICAL: Could not find .vector_cache directory.")
            sys.exit(1)

        # --- 2. FIND FAISS INDEX ---
        db_path = None
        index_name = "index"
        
        # Look for any file ending in .faiss
        faiss_files = list(cache_dir.glob("*.faiss"))
        if not faiss_files:
            # Check subdirectories if flat structure fails
            faiss_files = list(cache_dir.glob("*/*.faiss"))
            
        if not faiss_files:
            print(f"  ❌ CRITICAL: Found cache folder {cache_dir} but NO .faiss files inside.")
            sys.exit(1)
            
        target_file = faiss_files[0]
        db_path = target_file.parent
        index_name = target_file.stem # Filename without extension
        
        print(f"  🔹 Found Index File: {target_file.name}")

        try:
            # --- 3. LOAD RESOURCES ---
            embedding_wrapper = FunctionalEmbeddings(embed_text)
            
            vectorstore = FAISS.load_local(
                str(db_path), 
                embeddings=embedding_wrapper,
                allow_dangerous_deserialization=True,
                index_name=index_name
            )
            print("  ✅ Vectorstore loaded successfully.")
            
            image_store = {}
            # Try to match the index name pattern for images (e.g. name_images.pkl)
            image_files = list(db_path.glob("*_images.pkl"))
            if image_files:
                image_pkl_path = image_files[0]
                with open(image_pkl_path, "rb") as f:
                    image_store = pickle.load(f)
                print(f"  ✅ Image store loaded ({len(image_store)} images).")
            else:
                # Fallback check for generic image_data.pkl
                if (db_path / "image_data.pkl").exists():
                     with open(db_path / "image_data.pkl", "rb") as f:
                        image_store = pickle.load(f)
                     print(f"  ✅ Image store loaded (generic).")
                else:
                    print("  ⚠️ Warning: No image data pickle found.")

        except Exception as e:
            print(f"\n❌ ERROR LOADING FAISS: {e}")
            sys.exit(1)

        # --- 4. INITIALIZE AGENTS ---
        print("  🔹 Initializing AI Agents...")
        try:
            diagnostic_agent = create_diagnostic_agent(api_key)
            sandwich_processor = SandwichProcessor(api_key)
            
            # Simple mock for ImageAnalyzer if real one fails (we are testing text RAG)
            try:
                image_analyzer = ImageAnalyzer(api_key)
            except:
                class MockImageAnalyzer:
                    async def analyze(self, *args, **kwargs): return "Mock Image Analysis"
                image_analyzer = MockImageAnalyzer()
                
        except Exception as e:
            print(f"  ❌ Failed to create agents: {e}")
            sys.exit(1)

        # --- 5. MOCK REQUEST SETUP ---
        # Inject ALL dependencies into the mock state
        mock_state = MockAppState(
            vectorstore=vectorstore, 
            image_store=image_store,
            diagnostic_agent=diagnostic_agent,
            image_analyzer=image_analyzer,
            sandwich_processor=sandwich_processor
        )
        
        mock_app = MockApp(mock_state)
        self.mock_request = Request({"type": "http", "app": mock_app})
        
        try:
            self.chat_service = ChatService(self.mock_request)
            print("  ✅ ChatService instantiated successfully.")
        except Exception as e:
            print(f"  ❌ Failed to initialize ChatService: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
        
        self.rouge_scorer = rouge_scorer.RougeScorer(['rougeL'], use_stemmer=True)
        self.smoothing = SmoothingFunction().method1

    async def run_evaluation(self, test_cases: List[EvaluationData]) -> pd.DataFrame:
        results = []
        print(f"\n🚀 Starting Evaluation of {len(test_cases)} Test Cases...")
        
        for case in test_cases:
            print(f"  Processing Query: {case.query_text[:40]}...")
            
            chain_inputs = {
                "prompt": case.query_text,
                "image_url": None, 
                "vehicle": {},     
                "chat_history": [],
                "intent": "technical_question"
            }
            
            case.start_time = time.time()
            
            try:
                output = await self.chat_service.chain.ainvoke(chain_inputs)
                case.end_time = time.time()
                
                case.generated_text = output.get("diagnosis_output", "")
                
                retrieved_meta = output.get("retrieved_context", [])
                
                # --- UPDATED METADATA EXTRACTION FOR PAGE PRECISION ---
                case.retrieved_doc_ids = []
                case.similarity_scores = []
                
                if not retrieved_meta and "context_2" in output:
                    # Fallback for error cases
                    if output["context_2"] and output["context_2"] != "No knowledge base context available":
                         case.retrieved_doc_ids = ["(Content Retrieved)"]
                else:
                    for item in retrieved_meta:
                        source = str(item.get("doc_id", ""))
                        page = str(item.get("page", ""))
                        
                        # Create a composite ID: "Source | Page: X"
                        # This allows strict matching against ground truth format
                        if page and page != "unknown":
                            doc_identifier = f"{source} | Page: {page}"
                        else:
                            doc_identifier = source
                            
                        case.retrieved_doc_ids.append(doc_identifier)
                        
                        # Score handling
                        score_val = item.get("score")
                        if score_val is None:
                            case.similarity_scores.append(0.0)
                        else:
                            case.similarity_scores.append(float(score_val))
                # -------------------------------------------------------
                
            except Exception as e:
                logger.error(f"Error processing case {case.query_id}: {e}")
                case.generated_text = "ERROR"
                case.end_time = time.time()

            metrics = self._calculate_row_metrics(case)
            results.append(metrics)
            
        return pd.DataFrame(results)
    def _calculate_row_metrics(self, data: EvaluationData) -> Dict:
        """Calculates scores with Page-Level Precision"""
        
        latency = data.end_time - data.start_time
        
        # Ground Truth Parsing
        # JSON Format: ["Source", "Page: X"]
        gt_source = data.relevant_doc_ids[0]
        gt_page = data.relevant_doc_ids[1] if len(data.relevant_doc_ids) > 1 else None

        # --- RETRIEVAL METRICS ---
        
        def check_match(retrieved_id_str):
            # retrieved_id_str format: "Source | Page: X" or just "Source"
            
            # 1. Check Source
            if gt_source not in retrieved_id_str:
                return False
                
            # 2. Check Page (If GT specifies a page)
            if gt_page:
                # Extract page number from GT "Page: 3" -> "3"
                gt_num = gt_page.split(":")[-1].strip()
                
                # Check if that number exists in the retrieved string (Simple check)
                # e.g. "Page: 3" inside "Source | Page: 3"
                if f"Page: {gt_num}" in retrieved_id_str:
                    return True
                    
                # Allow +/- 1 page drift (Chunking overlap fix)
                try:
                    # Extract retrieved page number
                    if "Page: " in retrieved_id_str:
                        ret_num_str = retrieved_id_str.split("Page: ")[1].strip()
                        ret_num = int(ret_num_str)
                        target = int(gt_num)
                        if abs(ret_num - target) <= 1:
                            return True
                except:
                    pass
                    
                return False
            
            return True
        # Top-K Calculation
        top_1 = 1 if len(data.retrieved_doc_ids) > 0 and check_match(data.retrieved_doc_ids[0]) else 0
        
        top_3 = 0
        for doc in data.retrieved_doc_ids[:3]:
            if check_match(doc):
                top_3 = 1
                break
                
        top_5 = 0
        for doc in data.retrieved_doc_ids[:5]:
            if check_match(doc):
                top_5 = 1
                break

        # Context Recall (Did we find the specific page ANYWHERE?)
        recall = 0
        for doc in data.retrieved_doc_ids:
            if check_match(doc):
                recall = 1
                break

        # --- GENERATION METRICS ---
        
        ref_tokens = [data.reference_text.lower().split()]
        gen_tokens = data.generated_text.lower().split()
        bleu = sentence_bleu(ref_tokens, gen_tokens, smoothing_function=self.smoothing)
        
        rouge = self.rouge_scorer.score(data.reference_text, data.generated_text)
        rouge_f1 = rouge['rougeL'].fmeasure
        
        bert_f1 = 0.0
        if BERTSCORE_AVAILABLE:
            try:
                P, R, F1 = bert_score([data.generated_text], [data.reference_text], lang="en", verbose=False)
                bert_f1 = F1.mean().item()
            except Exception:
                pass

        return {
            "Query_ID": data.query_id,
            "Query": data.query_text,
            "Generated_Answer": data.generated_text[:100] + "...", 
            
            "Latency_Seconds": round(latency, 3),
            
            # Now "Top-1" means "Correct Page"
            "Top_1_Page_Accuracy": top_1,
            "Top_3_Page_Accuracy": top_3,
            "Top_5_Page_Accuracy": top_5,
            
            "Page_Recall": round(recall, 3),
            
            "BLEU_Score": round(bleu, 3),
            "ROUGE_L_F1": round(rouge_f1, 3),
            "BERTScore_F1": round(bert_f1, 3)
        }    
# --- DATA LOADER ---
class TestDataLoader:
    @staticmethod
    def create_template(filename="test_ground_truth.json"):
        template = [
            {
                "id": "q1",
                "question": "What should I do if my engine overheats?",
                "reference_answer": "Pull over safely and turn off the engine immediately.",
                "relevant_doc_ids": ["Vehicle_Breakdown_Queries"] 
            }
        ]
        with open(filename, "w") as f:
            json.dump(template, f, indent=2)
        print(f"✅ Created template: {filename}")

    @staticmethod
    def load_data(filename="test_ground_truth.json") -> List[EvaluationData]:
        if not Path(filename).exists():
            print("⚠️ File not found. Creating template...")
            TestDataLoader.create_template(filename)
            return []
            
        with open(filename, "r") as f:
            raw_data = json.load(f)
            
        return [
            EvaluationData(
                query_id=item["id"],
                query_text=item["question"],
                relevant_doc_ids=item.get("relevant_doc_ids", []),
                reference_text=item["reference_answer"]
            ) for item in raw_data
        ]

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=str, default="test_ground_truth.json", help="JSON file with test cases")
    parser.add_argument("--create-template", action="store_true", help="Generate the JSON template file")
    args = parser.parse_args()

    if args.create_template:
        TestDataLoader.create_template(args.file)
    else:
        test_cases = TestDataLoader.load_data(args.file)
        
        if not test_cases:
            print("❌ No test cases found. Please fill 'test_ground_truth.json'")
        else:
            evaluator = RealSystemEvaluator()
            results_df = asyncio.run(evaluator.run_evaluation(test_cases))
            
            print("\n" + "="*50)
            print("EVALUATION RESULTS SUMMARY (Page-Level Precision)")
            print("="*50)
            print(f"Average Latency: {results_df['Latency_Seconds'].mean():.2f}s")
            print(f"Top-1 Page Accuracy: {results_df['Top_1_Page_Accuracy'].mean()*100:.1f}%")
            print(f"Top-3 Page Accuracy: {results_df['Top_3_Page_Accuracy'].mean()*100:.1f}%")
            print(f"Top-5 Page Accuracy: {results_df['Top_5_Page_Accuracy'].mean()*100:.1f}%")
            print(f"Page Recall: {results_df['Page_Recall'].mean():.3f}")
            print(f"Semantic Similarity (BERTScore): {results_df['BERTScore_F1'].mean():.3f}")
            print("-" * 50)
            output_file = "evaluation_results_real.csv"
            results_df.to_csv(output_file, index=False)
            print(f"✅ Detailed results saved to {output_file}")