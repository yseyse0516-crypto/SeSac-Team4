from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.db import pool
from app.routers import bike, coupon, result, system


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool.open()
    yield
    pool.close()


app = FastAPI(title="TangTang API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# include_router 순서 고정: A(search) 먼저, B 나중 — A의 라우터가 준비되면 아래 줄의 주석을 해제한다.
# from app.routers import search
# app.include_router(search.router, prefix="/api/v1")

app.include_router(system.router, prefix="/api/v1")
app.include_router(result.router, prefix="/api/v1")
app.include_router(bike.router, prefix="/api/v1")
app.include_router(coupon.router, prefix="/api/v1")
