from fastapi import Depends, HTTPException, Request

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
