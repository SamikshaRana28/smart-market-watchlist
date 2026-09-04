from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Smart Market Watchlist API")

# Allow frontend (React dev server) to talk to backend during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this before production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "smart-market-watchlist-backend"}


@app.get("/")
def root():
    return {"message": "Smart Market Watchlist API is running"}
