from fastapi import APIRouter
from app.schemas.analysis import TranscriptRequest, BAAnalysisOutput
from app.services.ai_service import analyze_transcript

router = APIRouter()

@router.post("/analyze-transcript", response_model=BAAnalysisOutput)
def analyze(request: TranscriptRequest):

    return analyze_transcript(request.transcript)

    # return {
    #     "project_name": request.project_name,
    #     "analysis": result
    # }
