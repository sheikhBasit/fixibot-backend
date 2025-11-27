from fastapi import Request, HTTPException
# from services.intent_classifier import IntentClassifier

def get_diagnostic_agent(request: Request):
    agent = getattr(request.app.state, "diagnostic_agent", None)
    if not agent:
        raise HTTPException(status_code=500, detail="Diagnostic agent not initialized")
    return agent

def get_image_analyzer(request: Request):
    analyzer = getattr(request.app.state, "image_analyzer", None)
    if not analyzer:
        raise HTTPException(status_code=500, detail="Image analyzer not initialized")
    return analyzer

def get_vectorstore(request: Request):
    vectorstore = getattr(request.app.state, "vectorstore", None)
    image_data_store = getattr(request.app.state, "image_data_store", None)
    if not vectorstore:
        raise HTTPException(status_code=500, detail="Vectorstore not initialized")
    return vectorstore, image_data_store

# def get_intent_classifier(request: Request):
#     classifier = getattr(request.app.state, "intent_classifier", None)
#     if not classifier:
#         raise HTTPException(status_code=500, detail="Intent classifier not initialized")
#     return classifier


# services/dependencies.py (Partial Update)
from services.intent_classifier import SandwichProcessor
from config import settings

def get_sandwich_processor(request: Request):
    """Dependency to get the Sandwich Processor (Translation/Intent) from app state"""
    # This retrieves the instance initialized in main.py
    processor = getattr(request.app.state, "sandwich_processor", None)
    if not processor:
        raise HTTPException(status_code=500, detail="Sandwich Processor not initialized")
    return processor