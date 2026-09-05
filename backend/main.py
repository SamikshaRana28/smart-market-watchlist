# from contextlib import asynccontextmanager

# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware

# from app.db import Base, engine
# from app.models import MarketSnapshot, Watchlist, WatchlistItem  # noqa: F401
# from app.routes.market import router as market_router
# from app.routes.watchlists import router as watchlists_router


# @asynccontextmanager
# async def lifespan(_app: FastAPI):
#     Base.metadata.create_all(bind=engine)
#     yield


# app = FastAPI(title="Smart Market Watchlist API", lifespan=lifespan)
# app.include_router(market_router)
# app.include_router(watchlists_router)

# # Allow frontend (React dev server) to talk to backend during development
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # tighten this before production
#     allow_credentials=False,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )


# @app.get("/health")
# def health_check():
#     return {"status": "ok", "service": "smart-market-watchlist-backend"}


# @app.get("/")
# def root():
#     return {"message": "Smart Market Watchlist API is running"}


from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import Base, engine
from app.models import MarketSnapshot, Watchlist, WatchlistItem  # noqa: F401
from app.routes.market import router as market_router
from app.routes.watchlists import router as watchlists_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Smart Market Watchlist API", lifespan=lifespan)
app.include_router(market_router)
app.include_router(watchlists_router)

# Allow frontend (React dev server) to talk to backend during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this before production
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "smart-market-watchlist-backend"}


@app.get("/")
def root():
    return {"message": "Smart Market Watchlist API is running"}
