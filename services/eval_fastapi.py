"""
FastAPI Integration for Real-time RAG Evaluation (OPTIONAL)
Only use this if you want real-time logging and API endpoints

SETUP:
1. Copy this file to: services/eval_fastapi.py
2. In app.py, add:
   from services.eval_fastapi import create_evaluation_endpoints
   eval_router = create_evaluation_endpoints(app)
   app.include_router(eval_router)
3. In config.py, add: ENABLE_EVALUATION = False  # Set True for testing
"""

import time
import json
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path
import asyncio
from collections import deque

from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel

# Import your evaluation modules
from services.rag_evaluator import EvaluationData, RAGEvaluator


class EvaluationLogger:
    """Logs evaluation data during chat sessions for later analysis"""
    
    def __init__(self, log_dir: str = "evaluation_logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.session_logs = {}
        self.evaluator = RAGEvaluator()
        
        # In-memory buffer for recent evaluations
        self.recent_evaluations = deque(maxlen=100)
        
    def start_query(self, session_id: str, query_text: str) -> Dict:
        """Record the start of a query"""
        query_data = {
            'query_id': f"{session_id}_{int(time.time() * 1000)}",
            'session_id': session_id,
            'query_text': query_text,
            'start_time': time.time(),
            'timestamp': datetime.now().isoformat()
        }
        
        if session_id not in self.session_logs:
            self.session_logs[session_id] = []
        
        self.session_logs[session_id].append(query_data)
        return query_data
    
    def log_retrieval(self, query_data: Dict, 
                     retrieved_docs: List[str],
                     similarity_scores: List[float],
                     relevant_docs: Optional[List[str]] = None):
        """Log retrieval results"""
        query_data['retrieved_doc_ids'] = retrieved_docs
        query_data['similarity_scores'] = similarity_scores
        
        if relevant_docs:
            query_data['relevant_doc_ids'] = relevant_docs
    
    def log_response(self, query_data: Dict,
                    generated_text: str,
                    reference_text: Optional[str] = None):
        """Log generated response"""
        query_data['generated_text'] = generated_text
        query_data['end_time'] = time.time()
        query_data['latency'] = query_data['end_time'] - query_data['start_time']
        
        if reference_text:
            query_data['reference_text'] = reference_text
        else:
            query_data['reference_text'] = generated_text
        
        # Add to recent evaluations buffer
        self.recent_evaluations.append(query_data)
    
    def save_session_logs(self, session_id: str):
        """Save logs for a specific session"""
        if session_id not in self.session_logs:
            return
        
        log_file = self.log_dir / f"session_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(log_file, 'w') as f:
            json.dump(self.session_logs[session_id], f, indent=2)
        
        print(f"✅ Session logs saved to {log_file}")
    
    def load_evaluation_data(self, log_files: Optional[List[str]] = None) -> List[EvaluationData]:
        """Load evaluation data from log files"""
        if log_files is None:
            log_files = list(self.log_dir.glob("session_*.json"))
        
        eval_data = []
        
        for log_file in log_files:
            with open(log_file, 'r') as f:
                session_data = json.load(f)
            
            for query in session_data:
                # Only include queries with complete data
                if all(k in query for k in ['query_id', 'query_text', 'retrieved_doc_ids',
                                           'generated_text', 'start_time', 'end_time']):
                    eval_data.append(EvaluationData(
                        query_id=query['query_id'],
                        query_text=query['query_text'],
                        retrieved_doc_ids=query['retrieved_doc_ids'],
                        relevant_doc_ids=query.get('relevant_doc_ids', []),
                        similarity_scores=query.get('similarity_scores', []),
                        generated_text=query['generated_text'],
                        reference_text=query.get('reference_text', query['generated_text']),
                        start_time=query['start_time'],
                        end_time=query['end_time'],
                        metadata=query.get('metadata', {})
                    ))
        
        return eval_data
    
    async def evaluate_logged_data(self, 
                                   log_files: Optional[List[str]] = None,
                                   output_path: str = "evaluation_results/rag_eval") -> Dict:
        """Evaluate all logged data and save results"""
        eval_data = self.load_evaluation_data(log_files)
        
        if not eval_data:
            return {"error": "No evaluation data found"}
        
        print(f"📊 Loaded {len(eval_data)} evaluation instances")
        
        # Run evaluation
        results_df = self.evaluator.evaluate(eval_data, k_values=[1, 3, 5])
        
        # Save results
        self.evaluator.save_results(results_df, output_path)
        
        # Return as dictionary
        results_dict = results_df.set_index(['Category', 'Metric'])['Value'].to_dict()
        
        return {
            'num_queries': len(eval_data),
            'evaluation_date': datetime.now().isoformat(),
            'results': results_dict
        }


# FastAPI endpoints
def create_evaluation_endpoints(app):
    """Add evaluation endpoints to your FastAPI app"""
    
    from models.user import UserInDB, UserRole
    from utils.user import get_current_user
    
    eval_router = APIRouter(prefix="/admin/evaluation", tags=["Evaluation"])
    eval_logger = EvaluationLogger()
    
    @eval_router.post("/run")
    async def run_evaluation(
        log_files: Optional[List[str]] = None,
        output_name: str = "latest_eval",
        current_user: UserInDB = Depends(get_current_user)
    ):
        """Run evaluation on logged data"""
        if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        try:
            results = await eval_logger.evaluate_logged_data(
                log_files=log_files,
                output_path=f"evaluation_results/{output_name}"
            )
            return results
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")
    
    @eval_router.get("/recent")
    async def get_recent_evaluations(
        limit: int = 20,
        current_user: UserInDB = Depends(get_current_user)
    ):
        """Get recent evaluation data"""
        if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        recent = list(eval_logger.recent_evaluations)[-limit:]
        return {
            "count": len(recent),
            "evaluations": recent
        }
    
    @eval_router.get("/logs")
    async def list_evaluation_logs(
        current_user: UserInDB = Depends(get_current_user)
    ):
        """List all available evaluation log files"""
        if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        log_files = list(eval_logger.log_dir.glob("session_*.json"))
        return {
            "count": len(log_files),
            "log_files": [str(f.name) for f in log_files]
        }
    
    @eval_router.delete("/logs/{log_file}")
    async def delete_evaluation_log(
        log_file: str,
        current_user: UserInDB = Depends(get_current_user)
    ):
        """Delete a specific evaluation log"""
        if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        log_path = eval_logger.log_dir / log_file
        
        if not log_path.exists():
            raise HTTPException(status_code=404, detail="Log file not found")
        
        log_path.unlink()
        return {"message": f"Log file {log_file} deleted successfully"}
    
    return eval_router


# Usage in app.py:
# eval_router = create_evaluation_endpoints(app)
# app.include_router(eval_router)