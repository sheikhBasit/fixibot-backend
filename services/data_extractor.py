import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import asyncio
import aiohttp
import pandas as pd
from bert_score import score

# -----------------------------
# Setup logging
# -----------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -----------------------------
# Add project root for imports
# -----------------------------
project_root = Path(__file__).parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

# -----------------------------
# Test queries with ground truth
# -----------------------------
TEST_DATA = [
    {
        "query": "What should I do if my car won't start?",
        "reference_text": "If your car won't start, the most common causes are a dead battery, a faulty starter, or an empty fuel tank. First, check if your headlights and interior lights work; if they are dim or dead, your battery is likely the issue. You can try jump-starting it.",
        "reference_doc_ids": ["doc_battery", "doc_starter"]  # example GT doc IDs
    },
    {
        "query": "How do I check my car's oil level?",
        "reference_text": "To check your oil level, park the car on level ground and wait for the engine to cool down. Pull out the dipstick, wipe it clean with a rag, insert it all the way back in, and then pull it out again. The oil level should be between the 'Full' and 'Add' (or 'F' and 'L') marks.",
        "reference_doc_ids": ["doc_oil_check"]
    },
]

# -----------------------------
# DataExtractor class
# -----------------------------
class DataExtractor:
    def __init__(self, api_url: str = "http://localhost:8000", token: str = None):
        self.api_url = api_url
        self.session_endpoint = f"{api_url}/chat/start"
        self.message_endpoint = f"{api_url}/chat/message"
        self.session_id = None
        self.user_token = token or "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2OGJjNjgwMTI1NGJkYTgwYjJhZTEyMTYiLCJleHAiOjE5MTg3MTMxMzN9.J3qv7wjPF8H6Gr1sYJScGiqQlzRXQIeoKl3WJ3_OpH8"
        self.output_dir = Path("extracted_eval_data")
        self.output_dir.mkdir(exist_ok=True)
        self.test_vehicle = {
            "user_id": "test_user",
            "model": "Corolla",
            "brand": "Toyota",
            "year": 2020,
            "category": "car",
            "fuel_type": "petrol",
            "transmission": "automatic",
            "mileage_km": 50000,
            "registration_number": "ABC-123",
        }

    async def start_chat_session(self):
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.user_token}"}
            async with session.post(self.session_endpoint, headers=headers) as response:
                if response.status == 201:
                    self.session_id = (await response.json()).get("session_id")
                    logger.info(f"Started chat session: {self.session_id}")
                    return True
                return False

    async def query_chat_api(self, item: Dict) -> Dict:
        if not self.session_id:
            if not await self.start_chat_session():
                return None

        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.user_token}"
            }

            # ✅ Ensure vehicle data matches backend VehicleModel
            vehicle_payload = {
                "user_id": "68a1d6288b423aba320b9a8f",          # ✅ required by VehicleModel
                "make": "Toyota",
                "model": "Corolla",
                "year": 2020,
                "category": "car",
                "fuel_type": "petrol",
                "transmission": "automatic",
                "mileage": 50000,
                "registration_number": "ABC-123"
            }


            # ✅ Prepare form data for FastAPI endpoint
            form_data = aiohttp.FormData()
            form_data.add_field("session_id", self.session_id)
            form_data.add_field("message", item["query"])
            form_data.add_field("vehicle_json", json.dumps(vehicle_payload))

            # (Optional) include image if you want to test it
            # form_data.add_field("image", open("test_image.jpg", "rb"), filename="test_image.jpg", content_type="image/jpeg")

            async with session.post(self.message_endpoint, headers=headers, data=form_data) as resp:
                if resp.status == 200:
                    result = await resp.json()

                    retrieved_context = result.get("retrieved_context", [])
                    for r in retrieved_context:
                        r["is_relevant"] = int(r.get("doc_id") in item.get("reference_doc_ids", []))

                    return {
                        "query": item["query"],
                        "generated_text": result.get("response", ""),
                        "reference_text": item["reference_text"],
                        "retrieved_context": retrieved_context,
                        "timestamp": datetime.now().isoformat()
                    }
                else:
                    error_text = await resp.text()
                    logger.error(f"API error {resp.status} for query: {item['query']} — {error_text}")
                    return None

    async def extract_chat_data(self, test_data: List[Dict] = None) -> List[Dict]:
        if test_data is None:
            test_data = TEST_DATA
        semaphore = asyncio.Semaphore(3)
        async def process(item):
            async with semaphore:
                return await self.query_chat_api(item)
        results = await asyncio.gather(*(process(item) for item in test_data))
        chat_data = [r for r in results if r]
        logger.info(f"Extracted {len(chat_data)} responses.")
        return chat_data

    def save_data(self, data: List[Dict]):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        file = self.output_dir / f"chat_eval_data_{ts}.json"
        with open(file, "w") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved data to {file}")
        return file

# -----------------------------
# Metrics computation
# -----------------------------
def compute_detailed_retrieval(data: List[Dict], k_values=[1,3,5]):
    detailed = []
    for item in data:
        retrieved = item.get("retrieved_context", [])
        if not retrieved:
            # fallback row so "query" column exists
            detailed.append({
                "query": item["query"],
                "retrieved_doc_id": None,
                "score": None,
                "rank": None,
                "is_relevant": 0
            })
        else:
            for rank, r in enumerate(retrieved):
                detailed.append({
                    "query": item["query"],
                    "retrieved_doc_id": r.get("doc_id"),
                    "score": r.get("score"),
                    "rank": rank + 1,
                    "is_relevant": r.get("is_relevant", 0)
                })
    # Ensure columns exist
    df = pd.DataFrame(detailed)
    for col in ["query", "retrieved_doc_id", "score", "rank", "is_relevant"]:
        if col not in df.columns:
            df[col] = None
    return df

def compute_topk_metrics(df: pd.DataFrame, k_values=[1,3,5]):
    results = []
    grouped = df.groupby("query")
    for k in k_values:
        acc = 0
        for q, g in grouped:
            topk = g.sort_values("rank").head(k)
            if topk["is_relevant"].max() > 0:
                acc += 1
        results.append({"Metric": f"Top-{k} Accuracy", "Value": round(acc / len(grouped) if len(grouped) else 0,3)})
    return pd.DataFrame(results)

def compute_response_metrics(data: List[Dict]):
    if not data:
        return pd.DataFrame([{"Metric": "BERTScore_F1", "Value": 0.0}])
    gen_texts = [item["generated_text"] for item in data]
    ref_texts = [item["reference_text"] for item in data]
    P,R,F1 = score(gen_texts, ref_texts, lang="en", verbose=True)
    return pd.DataFrame({
        "Metric": ["BERTScore_P", "BERTScore_R", "BERTScore_F1"],
        "Value": [P.mean().item(), R.mean().item(), F1.mean().item()]
    })

# -----------------------------
# Full evaluation
# -----------------------------
async def run_full_evaluation():
    extractor = DataExtractor()

    data = await extractor.extract_chat_data()
    if not data:
        logger.warning("No chat responses extracted. Skipping evaluation.")
        return

    extractor.save_data(data)

    # Retrieval metrics
    retrieval_df_detailed = compute_detailed_retrieval(data)
    topk_df = compute_topk_metrics(retrieval_df_detailed)

    # Response metrics
    response_df = compute_response_metrics(data)

    # Combine and save
    final_df = pd.concat([topk_df, response_df]).reset_index(drop=True)
    eval_dir = Path("evaluation_results")
    eval_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    file = eval_dir / f"full_eval_{ts}.csv"
    final_df.to_csv(file, index=False)
    logger.info(f"Saved evaluation metrics to {file}")

    # Save detailed retrieval info
    retrieval_file = eval_dir / f"retrieval_detailed_{ts}.csv"
    retrieval_df_detailed.to_csv(retrieval_file, index=False)
    logger.info(f"Saved detailed retrieval info to {retrieval_file}")

    print("\n--- EVALUATION RESULTS ---")
    print(final_df.to_string(index=False))
    print("--------------------------")

# -----------------------------
# Entry point
# -----------------------------
if __name__ == "__main__":
    asyncio.run(run_full_evaluation())
