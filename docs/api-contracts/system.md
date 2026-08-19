# system API 계약

공용 화면 하단 배너(Front/API 버전, 서버 IP, 서버명 노출용) — CLAUDE.md §12.

## GET /api/system/version

인증 불필요. 요청 바디 없음.

### 응답 200

```json
{
  "server_version": "1.0.0",
  "server_name": "ip-172-16-21-238",
  "server_ip": "172.16.21.238",
  "client_ip": "211.171.73.130",
  "x_forwarded_for": "211.171.73.130, 172.16.21.238"
}
```

| 필드 | 설명 |
|---|---|
| `server_version` | 환경변수 `SERVER_VERSION` (없으면 `0.1.0` 기본값) |
| `server_name` | 환경변수 `SERVER_NAME` (없으면 `socket.gethostname()` fallback) |
| `server_ip` | 환경변수 `SERVER_IP` (없으면 `socket.gethostbyname()` fallback) |
| `client_ip` | FastAPI가 본 요청 소켓의 IP (`request.client.host`) |
| `x_forwarded_for` | `X-Forwarded-For` 요청 헤더 원본, 없으면 `null` |

> 로컬 개발 중 프론트(Vite)가 `/api`를 백엔드로 프록시하는 구성에서는 `client_ip`가 폰의 실제 IP가 아니라 Vite 서버(PC 자신, `127.0.0.1`)로 보인다. 실제 클라이언트 IP는 배포 후 리버스 프록시(ALB 등)가 `X-Forwarded-For`를 붙여줄 때 의미가 생긴다.

Front 버전은 이 API와 무관하게 프론트가 `frontend/package.json`의 `version` 필드를 빌드 시점에 주입해 자체적으로 표시한다.
