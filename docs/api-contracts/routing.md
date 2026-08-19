# API 계약: 경로 추천 (`routing` 모듈)

> 이 문서는 프론트엔드(윤상은)와 백엔드(정종우·김창영)가 실제 구현 전에 먼저 합의하는 "약속 문서"다.
> 백엔드 구현이 끝나기 전에도 프론트는 이 형태에 맞춘 가짜 데이터(mock)로 화면을 먼저 만들 수 있다.
> 형태가 바뀌면 이 문서를 먼저 고치고, 그다음 코드를 고친다. (문서 → 코드 순서를 지킨다)
>
> **2026-08-19 갱신**: `backend.md`(정종우, 최종본)의 §4/§5 계약을 기준으로 필드명을 camelCase → **snake_case**로 다시 맞췄다.
> `backend.md`가 backend 관련 최신 소스오브트루스이므로, 이 문서와 다르면 `backend.md`를 따른다.

## 1. 엔드포인트

```
POST /api/v1/routes/search
```

> ⚠️ Base URL이 `/api/v1`인 것은 `backend.md` §5에 명시돼 있으나, 이 문서의 이전 버전(2026-08-18 초안)에는
> prefix 없이 적혀 있었다. 실제 구현 시 꼭 `/api/v1`을 붙여서 확인할 것.

## 2. 요청 (프론트 → 백엔드)

```json
{
  "origin": { "lat": 37.4979, "lng": 127.0276 },
  "destination": { "lat": 37.5665, "lng": 126.9780 },
  "departAt": "2026-08-18T08:30:00+09:00"
}
```

| 필드 | 타입 | 설명 |
|---|---|---|
| `origin.lat` / `origin.lng` | number | 출발지 위도/경도 |
| `destination.lat` / `destination.lng` | number | 도착지 위도/경도 |
| `departAt` | string (ISO 8601, timezone 포함) | 기준 출발 시각 |

> ⚠️ **미확정**: `backend.md`는 DB 컬럼명(`origin_lat`/`origin_lng`/`dest_lat`/`dest_lng`/`requested_at`)만 알려주고
> 실제 request body의 필드명은 명시하지 않았다. 위 형태는 프론트 제안값 — A(정종우)/B(김창영)와 확정 필요.

## 3. 응답 (백엔드 → 프론트)

```json
{
  "routes": [
    {
      "id": 1,
      "path_type": "recommended",
      "is_recommended": true,
      "total_time_min": 38,
      "congestion_score": 0.41,
      "minute_improvement_ratio": 3.2,
      "segments": [
        {
          "mode": "walk",
          "duration_min": 5,
          "start": { "lat": 37.4979, "lng": 127.0276 },
          "end": { "lat": 37.5100, "lng": 127.0100 }
        },
        {
          "mode": "subway",
          "station_id": 1021,
          "duration_min": 28,
          "start": { "lat": 37.5100, "lng": 127.0100 },
          "end": { "lat": 37.5665, "lng": 126.9780 }
        }
      ]
    }
  ]
}
```

| 필드 | 타입 | 설명 |
|---|---|---|
| `id` | number | 이 경로 후보의 고유 id (`route_candidate.id`, 화면에서 목록 key로 사용) |
| `path_type` | string | 경로 종류 구분값(예: `recommended`/`fastest`) — **enum이 backend.md에 명시돼 있지 않음, 확인 필요** |
| `is_recommended` | boolean | 추천 배지 표시 여부 |
| `total_time_min` | number | 총 소요시간(분) |
| `congestion_score` | number | 0~1 정규화 혼잡 점수, **0에 가까울수록 쾌적** (backend.md §7.1 Q1 공식 기준) |
| `minute_improvement_ratio` | number | 분당개선 지표 = 재차인원 감소량 ÷ 추가 소요시간. 낮으면 "많이 돌아가는데 안 편해지는" 경로 |
| `segments` | object[] | 구간별 이동 정보. 지도 렌더링을 위해 `start`/`end` 좌표를 항상 포함 (backend.md §5에서 확정) |
| `segments[].mode` | `"walk"` \| `"subway"` \| `"bus"` \| `"bike"` | 소문자 — backend.md §5 예시 기준 |
| `segments[].station_id` / `stop_id` | number? | 지하철/버스 구간에서만 존재 |
| `segments[].duration_min` | number | 이 구간 소요시간(분) |
| `segments[].start` / `end` | `{lat, lng}` | 이 구간의 시작/끝 좌표 |

> ⚠️ **미확정**: 최상위 응답을 감싸는 키가 `routes`인지 다른 이름(`candidates` 등)인지 backend.md에 명시된 적이 없다.
> `save_candidates(request_id, candidates)`의 파라미터명이 `candidates`인 것은 백엔드 내부 함수 인자명이라 그대로
> 응답 키와 같다고 보장되지 않는다 — A/B 확인 필요. 확정 전까지 프론트는 `routes`로 가정.

## 4. 확정되지 않은 부분 (백엔드팀과 계속 맞춰야 함)

- 요청 body의 정확한 필드명 (§2 참고)
- 최상위 응답 래핑 키 이름 (§3 참고)
- `path_type` enum 전체 값 목록
- `congestion_score`가 경로 단위로만 있는지, `segments[]` 각 항목에도 있는지
- 따릉이(`bike`) 후보가 포함될 때 대여소 실시간 재고가 0이면 이 응답에서 빼는지, 아니면 "재고없음" 플래그로 표시하는지
- 에러 응답 형태(예: ODsay 실패, 좌표가 서울 밖인 경우) — `backend.md` §5에 코드만 정의(`400 INVALID_INPUT`/`404 NO_CANDIDATE`/`429 ODSAY_QUOTA_EXCEEDED`/`502 UPSTREAM_ERROR`), 본문 형태는 미정. 우선 프론트는 `routes: []`로만 가정하고 진행

## 5. 변경 이력

| 날짜 | 변경 내용 | 작성자 |
|---|---|---|
| 2026-08-18 | 최초 초안 (프론트 작업 시작을 위한 draft, camelCase) | 윤상은 |
| 2026-08-19 | `backend.md`(정종우 최종본) 기준 snake_case로 필드 재정의, `/api/v1` prefix 반영, 미확정 항목 정리 | 윤상은 |
