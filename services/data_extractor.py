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

# Test queries for evaluation
TEST_QUERIES = [
    "What should I do if my car won't start?",
    "How do I check my car's oil level?",
    "What does it mean when my brake pedal feels spongy?",
    "My car is making a squealing noise when I brake, what could be wrong?",
    "What are common causes of engine overheating?",
    "How often should I rotate my tires?",
    "What should I do if my car battery dies?",
    "Why is my check engine light on?",
    "How do I know if I need new brake pads?",
    "What's causing my steering wheel to shake?"
]

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
        self.test_vehicle = {
            "user_id": "68a1d6288b423aba320b9a8f",  # This matches the user ID from the token
            "model": "Corolla",
            "brand": "Toyota",
            "year": 2020,
            "type": "car",
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

    async def query_chat_api(self, query: str) -> Dict:
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
                logger.info(f"With vehicle: {vehicle_json}")
                async with session.post(self.message_endpoint, headers=headers, data=form_data) as response:
                    response_text = await response.text()
                    logger.info(f"Raw response: {response_text}")
                    
                    if response.status == 200:
                        result = await response.json()
                        # Get the assistant's response
                        response_text = result.get("response", "")
                        if response_text:  # If we have a response
                            return {
                                "query": query,
                                "generated_text": response_text,
                                "reference_text": response_text,  # Use same text as reference for now
                                "retrieved_context": result.get("context", []),
                                "timestamp": datetime.now().isoformat()
                            }
                        else:
                            logger.error("Response doesn't contain enough messages")
                            return None
                    else:
                        logger.error(f"API error {response.status}: {response_text}")
                        return None
            except Exception as e:
                logger.error(f"Error querying API: {e}")
                return None

    async def extract_chat_data(self, queries: List[str] = None) -> List[Dict]:
        """Extract chat data by querying the API with test questions"""
        if queries is None:
            queries = TEST_QUERIES
        
        chat_data = []
        total = len(queries)
        
        logger.info(f"Starting evaluation with {total} queries")
        
        # Process queries in parallel with rate limiting
        semaphore = asyncio.Semaphore(3)  # Limit concurrent requests
        async def process_query(query):
            async with semaphore:
                return await self.query_chat_api(query)
        
        tasks = [process_query(query) for query in queries]
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
        
        # Debug the data
        logger.info("Processing evaluation data:")
        for item in data:
            logger.info(f"Query: {item['query']}")
            logger.info(f"Generated: {item['generated_text'][:100]}...")
            logger.info(f"Reference: {item['reference_text'][:100]}...")
            logger.info("-" * 50)
        
        # Convert data to evaluation format
        eval_data = [
            EvaluationData(
                query_id=str(idx),
                query_text=item["query"],
                retrieved_doc_ids=[],  # No document IDs in our case
                relevant_doc_ids=[],   # No relevant documents in our case
                similarity_scores=[],   # No similarity scores in our case
                generated_text=item["generated_text"],
                reference_text=item["reference_text"],
                start_time=0.0,  # We don't have timing info
                end_time=0.0,    # We don't have timing info
                metadata={"context": item.get("retrieved_context", [])}
            )
            for idx, item in enumerate(data)
            if item["query"] and item["generated_text"] and len(item["generated_text"].strip()) > 0
            for item in data
            if item["query"] and item["generated_text"] and len(item["generated_text"].strip()) > 0
        ]
        
        if not eval_data:
            logger.warning("No valid evaluation data found")
            return
            
        # Run evaluation with BERT score
        evaluator = RAGEvaluator()
        results = evaluator.evaluate(eval_data)
        
        # Add BERT scores
        if len(eval_data) > 0:
            generated_texts = [item["generated_text"] for item in data]
            reference_texts = [item["reference_text"] for item in data]
            P, R, F1 = score(generated_texts, reference_texts, lang="en", verbose=True)
            
            bert_results = pd.DataFrame({
                'Metric': ['BERT-P', 'BERT-R', 'BERT-F1'],
                'Score': [P.mean().item(), R.mean().item(), F1.mean().item()]
            })
            
            results = pd.concat([results, bert_results])
        
        # Save evaluation results
        results_dir = Path("evaluation_results")
        results_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save detailed results
        results_file = results_dir / f"eval_{timestamp}.csv"
        results.to_csv(results_file, index=False)
        
        # Save raw scores for analysis
        raw_scores = pd.DataFrame({
            'query': [item["query"] for item in data],
            'generated': [item["generated_text"] for item in data],
            'reference': [item["reference_text"] for item in data],
            'timestamp': [item["timestamp"] for item in data]
        })
        raw_file = results_dir / f"raw_scores_{timestamp}.csv"
        raw_scores.to_csv(raw_file, index=False)
        
        logger.info(f"Evaluation results saved to {results_file}")
        logger.info(f"Raw scores saved to {raw_file}")
        
    except Exception as e:
        logger.error(f"Error during evaluation: {e}")
        raise

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://localhost:8000", 
                      help="Base URL of the chat API")
    parser.add_argument("--queries-file", type=str,
                      help="Path to JSON file containing test queries")
    parser.add_argument("--evaluate", action="store_true",
                      help="Run evaluation after collecting responses")
    parser.add_argument("--token", type=str,
                      help="User authentication token")
    args = parser.parse_args()

    try:
        # Load custom queries if provided
        queries = None
        if args.queries_file:
            try:
                with open(args.queries_file) as f:
                    queries = json.load(f)
                logger.info(f"Loaded {len(queries)} custom queries")
            except Exception as e:
                logger.error(f"Error loading queries file: {e}")
                return

        # Initialize extractor with API URL
        extractor = DataExtractor(api_url=args.api_url)
        if args.token:
            extractor.user_token = args.token
        
        # Initialize extractor with API URL
        extractor = DataExtractor(api_url=args.api_url)
        
        # Get responses from API
        data = await extractor.extract_chat_data(queries=queries)
        if not data:
            logger.error("No responses received from API")
            return
            
        # Save raw responses
        output_file = extractor.save_data(data)
        
        # Run evaluation if requested
        if args.evaluate:
            await run_evaluation(data)
            
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise
        try:
            from services.rag_evaluator import RAGEvaluator, EvaluationData
            
            # Convert data to evaluation format
            eval_data = [
                EvaluationData(
                    query=item["query"],
                    generated_text=item["generated_text"],
                    reference_text=item["reference_text"],
                    retrieved_context=item["retrieved_context"]
                )
                for item in data
                if item["query"] and item["generated_text"] and item["reference_text"]
            ]
            
            if not eval_data:
                logger.warning("No valid evaluation data found")
                return
                
            # Run evaluation with BERT score
            evaluator = RAGEvaluator()
            results = evaluator.evaluate(eval_data)
            
            # Add BERT scores
            if len(eval_data) > 0:
                generated_texts = [item["generated_text"] for item in data]
                reference_texts = [item["reference_text"] for item in data]
                P, R, F1 = score(generated_texts, reference_texts, lang="en", verbose=True)
                
                bert_results = pd.DataFrame({
                    'Metric': ['BERT-P', 'BERT-R', 'BERT-F1'],
                    'Score': [P.mean().item(), R.mean().item(), F1.mean().item()]
                })
                
                results = pd.concat([results, bert_results])
            
            # Save evaluation results
            results_dir = Path("evaluation_results")
            results_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Save detailed results
            results_file = results_dir / f"eval_{timestamp}.csv"
            results.to_csv(results_file, index=False)
            
            # Save raw scores for analysis
            raw_scores = pd.DataFrame({
                'query': [item["query"] for item in data],
                'generated': [item["generated_text"] for item in data],
                'reference': [item["reference_text"] for item in data],
                'timestamp': [item["timestamp"] for item in data]
            })
            raw_file = results_dir / f"raw_scores_{timestamp}.csv"
            raw_scores.to_csv(raw_file, index=False)
            
            logger.info(f"Evaluation results saved to {results_file}")
            logger.info(f"Raw scores saved to {raw_file}")
            
        except Exception as e:
            logger.error(f"Error during evaluation: {e}")
            raise

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())