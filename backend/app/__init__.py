from fastapi import FastAPI


app = FastAPI(
    title="CCTV Integration & Video Analytics Platform",
    version="1.0.0",
    description="Backend API for CCTV integration, video analytics and AI processing.",
)


@app.get("/")
async def root():
    return {
        "message": "CCTV Backend is running"
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy"
    }