"""⚠️ 임시 개발용 서버 — B(김창영)의 main.py가 올라오면 이 파일은 지운다.

main.py/core/*가 아직 없어서 프론트가 테스트할 실제 서버가 없는 상태를 임시로 메우는
용도다. DB/Redis 없이도 동작한다 (candidate_log_stub이 아무것도 저장하지 않는 no-op,
board_service/favorite_service/auth_service는 프로세스 메모리에 저장 — backend.md §11/§12).
/routes/search, /board/posts, /auth/*, /favorites만 살아있고, 나머지 엔드포인트
(system/meta, bike/docks 등)는 B 담당이라 여기 없다 — 없는 걸 있는 척 가짜로 만들지 않았다.

실행:
    cd backend
    pip install -r requirements.txt
    uvicorn app.dev_server:app --reload --port 8000
"""
from dotenv import load_dotenv

load_dotenv()  # backend/.env (cwd가 backend/일 때 자동으로 찾음)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.auth import router as auth_router
from app.routers.board import router as board_router
from app.routers.favorites import router as favorites_router
from app.routers.search import router as search_router

app = FastAPI(title="TangTang API (dev, 임시)")

# 개발 중 프론트(Vite, 보통 5173 포트)에서 바로 호출할 수 있게 임시로 전체 허용.
# B의 main.py가 완성되면 실제 CORS 정책으로 교체해야 한다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search_router)
app.include_router(board_router)
app.include_router(auth_router)
app.include_router(favorites_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "note": "dev_server 임시 서버 — DB/Redis 연결 없음"}
