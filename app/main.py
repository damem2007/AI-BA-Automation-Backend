import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.analyze import router as analyze_router


load_dotenv()


def get_allowed_origins():
    # Enterprise deployments should provide exact app origins through environment config.
    origins = os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,https://ai-ba-automation-frontend-o8tozqfzm-damem2007s-projects.vercel.appLOWED_ORIGINS=",
    )
    return [origin.strip() for origin in origins.split(",") if origin.strip()]


# Alembic owns schema creation; importing the API should not require DB access.
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    # Credentials stay disabled unless auth moves to browser-managed cookies.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze_router)

@app.get("/")

def root():
    return {"message": "BA Artifact Automation API Running"}
