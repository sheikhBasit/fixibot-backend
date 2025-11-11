import os
import sys
import json
import logging
from datetime import datetime, timedelta
import argparse
from typing import List, Dict
from pathlib import Path
import asyncio
import aiohttp

import pandas as pd
from bert_score import score

# Add the project root to Python path
project_root = Path(__file__).parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- "CORRECT ANSWERS" ARE NOW FILLED IN ---
# These are the "ground truth" reference texts.
TEST_DATA = [
    {
        "query": "What should I do if my car won't start?",
        "reference_text": "If your car won't start, the most common causes are a dead battery, a faulty starter, or an empty fuel tank. First, check if your headlights and interior lights work; if they are dim or dead, your battery is likely the issue. You can try jump-starting it."
    },
    {
        "query": "How do I check my car's oil level?",
        "reference_text": "To check your oil level, park the car on level ground and wait for the engine to cool down. Pull out the dipstick, wipe it clean with a rag, insert it all the way back in, and then pull it out again. The oil level should be between the 'Full' and 'Add' (or 'F' and 'L') marks."
    },
    {
        "query": "What does it mean when my brake pedal feels spongy?",
        "reference_text": "A spongy or 'mushy' brake pedal is a serious safety concern, usually indicating air in the brake lines. This can be caused by a brake fluid leak or a failing master cylinder. The system needs to be inspected and 'bled' to remove the air."
    },
    {
        "query": "My car is making a squealing noise when I brake, what could be wrong?",
        "reference_text": "A high-pitched squealing or squeaking sound when you apply the brakes is almost always the sound of the built-in 'wear indicators' on your brake pads. This is a warning that your brake pads are worn out and need to be replaced soon."
    },
    {
        "query": "What are common causes of engine overheating?",
        "reference_text": "The most common causes for engine overheating are low coolant levels, a faulty thermostat that is stuck closed, a failing water pump, or a leak in the cooling system (like a cracked hose or radiator). You should also check if the radiator fans are working."
    },
    {
        "query": "How often should I rotate my tires?",
        "reference_text": "You should generally rotate your tires every 5,000 to 7,500 miles. This helps ensure they wear evenly and extends their lifespan. Check your owner's manual for the specific recommendation for your vehicle."
    }
]
# --- END OF FILLED-IN ANSWERS ---


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataExtractor:
    def __init__(self, api_url: str = "http://localhost:8000"):
        self.output_dir = Path("extracted_eval_data")
        self.output_dir.mkdir(exist_ok=True)
        self.api_url = api_url
        self.session_endpoint = f"{api_url}/chat/start"
        self.message_endpoint = f"{api_url}/chat/message"
        self.session_id = None
        self.user_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2OGJjNjgwMTI1NGJkYTgwYjJhZTEyMTYiLCJleHAiOjE5MTg3MTMxMzN9.J3qv7wjPF8H6Gr1sYJScGiqQlzRXQIeoKl3WJ3_OpH8"  # Add your test user token here
        
        # Sample vehicle configuration for testing
# NEW (Fixed)
        self.test_vehicle = {
            "user_id": "68a1d6288b423aba320b9a8f",
            "model": "Corolla",
            "brand": "Toyota",
            "year": 2020,
            "category": "car",  # <-- RENAMED THIS FIELD
            "fuel_type": "petrol",
            "transmission": "automatic",
            "mileage_km": 50000,
            "registration_number": "ABC-123",
            "is_primary": True,
            "is_active": True
        }
    async def start_chat_session(self) -> bool:
        """Start a new chat session"""
        async with aiohttp.ClientSession() as session:
            try:
                headers = {"Authorization": f"Bearer {self.user_token}"}
                async with session.post(self.session_endpoint, headers=headers) as response:
                    if response.status == 201:
                        result = await response.json()
                        self.session_id = result.get("session_id")
                        logger.info(f"Started chat session: {self.session_id}")
                        return True
                    else:
                        logger.error(f"Failed to start session: {response.status}")
                        return False
            except Exception as e:
                logger.error(f"Error starting chat session: {e}")
                return False

    async def query_chat_api(self, query: str, reference_text: str) -> Dict:
        """Send a query to the chat API and get response"""
        if not self.session_id:
            if not await self.start_chat_session():
                return None

        async with aiohttp.ClientSession() as session:
            try:
                headers = {"Authorization": f"Bearer {self.user_token}"}
                form_data = aiohttp.FormData()
                form_data.add_field("session_id", self.session_id)
                form_data.add_field("message", query)
                
                # Add vehicle information
                vehicle_json = json.dumps(self.test_vehicle)
                form_data.add_field("vehicle_json", vehicle_json)
                
                logger.info(f"Sending query: {query}")
                
                async with session.post(self.message_endpoint, headers=headers, data=form_data) as response:
                    response_text_raw = await response.text()
                    
                    if response.status == 200:
                        result = await response.json()
                        response_text = result.get("response", "") # Get the assistant's response
                        
                        if response_text:
                            return {
                                "query": query,
                                "generated_text": response_text,
                                "reference_text": reference_text,  # <-- This is the "ground truth"
                                "retrieved_context": result.get("context", []),
                                "timestamp": datetime.now().isoformat()
                            }
                        else:
                            logger.error("Response JSON doesn't contain 'response' key")
                            return None
                    else:
                        logger.error(f"API error {response.status}: {response_text_raw}")
                        return None
            except Exception as e:
                logger.error(f"Error querying API: {e}")
                return None

    async def extract_chat_data(self, test_data: List[Dict] = None) -> List[Dict]:
        """Extract chat data by querying the API with test questions"""
        if test_data is None:
            test_data = TEST_DATA
        
        chat_data = []
        total = len(test_data)
        
        logger.info(f"Starting evaluation with {total} queries")
        
        # Process queries in parallel with rate limiting
        semaphore = asyncio.Semaphore(3)  # Limit concurrent requests
        async def process_query(item):
            async with semaphore:
                query = item["query"]
                reference = item["reference_text"]
                return await self.query_chat_api(query, reference)
        
        tasks = [process_query(item) for item in test_data]
        results = await asyncio.gather(*tasks)
        
        # Filter out None results and add to chat_data
        chat_data = [r for r in results if r is not None]
        
        logger.info(f"Completed {len(chat_data)} successful queries out of {total}")
        return chat_data

    def save_data(self, data: List[Dict]):
        """Save extracted data to JSON file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = self.output_dir / f"chat_eval_data_{timestamp}.json"
        
        with open(output_file, "w") as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.info(f"Saved {len(data)} records to {output_file}")
        return output_file

async def run_evaluation(data: List[Dict]):
    """Run evaluation on the extracted data"""
    try:
        from services.rag_evaluator import RAGEvaluator, EvaluationData
        
        logger.info("Processing data for evaluation...")
        
        # Convert data to evaluation format
        eval_data = [
            EvaluationData(
                query_id=str(idx),
                query_text=item["query"],
                retrieved_doc_ids=[],  # We don't have this from the API response
                relevant_doc_ids=[],   # We don't have this
                similarity_scores=[],  # We don't have this
                generated_text=item["generated_text"],
                reference_text=item["reference_text"],
                start_time=0.0,  # We don't have timing info from this script
                end_time=1.0,    # We don't have timing info
                metadata={"context": item.get("retrieved_context", [])}
            )
            for idx, item in enumerate(data)
            if item.get("query") and item.get("generated_text") and item.get("reference_text")
        ]
        
        if not eval_data:
            logger.warning("No valid evaluation data found (missing query, generated_text, or reference_text).")
            return

        logger.info(f"Running evaluation on {len(eval_data)} items.")
            
        # Run evaluation with BERT score
        evaluator = RAGEvaluator()
        # Set calculate_bertscore to False to skip it, as it's slow
        results = evaluator.evaluate(eval_data, calculate_bertscore=False) 
        
        # Add BERT scores
        if len(eval_data) > 0:
            logger.info("Calculating BERTScore (this can be slow)...")
            generated_texts = [item.generated_text for item in eval_data]
            reference_texts = [item.reference_text for item in eval_data]
            P, R, F1 = score(generated_texts, reference_texts, lang="en", verbose=True)
            
            bert_results = pd.DataFrame({
                'Category': 'Response', 'Metric': 'BERTScore_P', 'Value': [P.mean().item()]
            })
            bert_results = pd.concat([bert_results, pd.DataFrame({
                'Category': 'Response', 'Metric': 'BERTScore_R', 'Value': [R.mean().item()]
            })])
            bert_results = pd.concat([bert_results, pd.DataFrame({
                'Category': 'Response', 'Metric': 'BERTScore_F1', 'Value': [F1.mean().item()]
            })])
            
            results = pd.concat([results, bert_results]).reset_index(drop=True)
        
        # Save evaluation results
        results_dir = Path("evaluation_results")
        results_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        results_file = results_dir / f"eval_{timestamp}.csv"
        results.to_csv(results_file, index=False)
        logger.info(f"Evaluation results saved to {results_file}")
        
        # Save raw scores for analysis
        raw_scores = pd.DataFrame(data)
        raw_file = results_dir / f"raw_scores_{timestamp}.csv"
        raw_scores.to_csv(raw_file, index=False)
        logger.info(f"Raw scores for manual review saved to {raw_file}")
        
        print("\n--- EVALUATION RESULTS ---")
        print(results.to_string(index=False))
        print("--------------------------\n")
        
    except ImportError:
        logger.error("Could not import RAGEvaluator. Make sure 'services.rag_evaluator' is accessible.")
    except Exception as e:
        logger.error(f"Error during evaluation: {e}")
        raise

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://localhost:8000", 
                      help="Base URL of the chat API")
    parser.add_argument("--queries-file", type=str,
                      help="Path to JSON file containing test queries (e.g., [{'query': '...', 'reference_text': '...'}])")
    parser.add_argument("--evaluate", action="store_true",
                      help="Run evaluation after collecting responses")
    parser.add_argument("--token", type=str,
                      help="User authentication token")
    args = parser.parse_args()

    try:
        # Load custom queries if provided
        test_data = None
        if args.queries_file:
            try:
                with open(args.queries_file) as f:
                    test_data = json.load(f)
                logger.info(f"Loaded {len(test_data)} custom queries")
            except Exception as e:
                logger.error(f"Error loading queries file: {e}")
                return

        # Initialize extractor with API URL
        extractor = DataExtractor(api_url=args.api_url)
        if args.token:
            extractor.user_token = args.token
        
        # Get responses from API
        data = await extractor.extract_chat_data(test_data=test_data)
        if not data:
            logger.error("No responses received from API")
            return
            
        # Save raw responses
        extractor.save_data(data)
        
        # Run evaluation if requested
        if args.evaluate:
            await run_evaluation(data)
        else:
            logger.info("Data extraction complete. Run with --evaluate to get scores.")
            
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())