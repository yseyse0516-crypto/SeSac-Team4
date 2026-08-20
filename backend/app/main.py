from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.db import pool
from app.routers import auth, bike, board, coupon, favorites, result, search, system


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

# include_router 순서 고정: A(search/auth/board/favorites) 먼저, B 나중.
# A의 4개 라우터는 자체적으로 전체 경로("/api/v1/...")를 prefix로 갖고 있어서
# 여기서 또 prefix="/api/v1"을 붙이면 경로가 두 번 겹친다(실제로 겹쳐서 발견,
# 2026-08-20 통합 중 확인) — B의 라우터만 prefix가 없어서 여기서 붙여준다.
app.include_router(search.router)
app.include_router(auth.router)
app.include_router(board.router)
app.include_router(favorites.router)

app.include_router(system.router, prefix="/api/v1")
app.include_router(result.router, prefix="/api/v1")
app.include_router(bike.router, prefix="/api/v1")
app.include_router(coupon.router, prefix="/api/v1")
