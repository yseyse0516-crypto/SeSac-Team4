# API 계약: 경로 추천 (`routing` 모듈)

> 이 문서는 프론트엔드(윤상은)와 백엔드(정종우·김창영)가 실제 구현 전에 먼저 합의하는 "약속 문서"다.
> 백엔드 구현이 끝나기 전에도 프론트는 이 형태에 맞춘 가짜 데이터(mock)로 화면을 먼저 만들 수 있다.
> 형태가 바뀌면 이 문서를 먼저 고치고, 그다음 코드를 고친다. (문서 → 코드 순서를 지킨다)

## 1. 엔드포인트

```
POST /api/routes/search
```

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

## 3. 응답 (백엔드 → 프론트)

```json
{
  "routes": [
    {
      "routeId": "r1",
      "modes": ["SUBWAY"],
      "durationMin": 38,
      "extraMinVsFastest": 4,
      "netOnboardScore": 62,
      "congestionPct": 71,
      "minutePerImprovement": 3.2,
      "path": [
        { "lat": 37.4979, "lng": 127.0276 },
        { "lat": 37.5100, "lng": 127.0100 },
        { "lat": 37.5665, "lng": 126.9780 }
      ],
      "steps": [
        { "mode": "WALK", "label": "출발지 → 강남역", "durationMin": 5 },
        { "mode": "SUBWAY", "label": "2호선 강남 → 시청", "durationMin": 28 },
        { "mode": "WALK", "label": "시청역 → 도착지", "durationMin": 5 }
      ]
    }
  ]
}
```

| 필드 | 타입 | 설명 |
|---|---|---|
| `routeId` | string | 이 경로 후보의 고유 id (화면에서 목록 key로 사용) |
| `modes` | string[] | 이 경로에 쓰인 교통수단(`SUBWAY`/`BUS`/`BIKE`/`WALK`) |
| `durationMin` | number | 총 소요시간(분) |
| `extraMinVsFastest` | number | 가장 빠른 경로보다 몇 분 더 걸리는지 (0이면 최단경로) |
| `netOnboardScore` | number | 재차인원 기반 점수 — 낮을수록 덜 혼잡 (스케일은 배치팀과 추가 확정 필요) |
| `congestionPct` | number | 참고용 %혼잡도(하차 전 기준, 기존 앱이 보여주는 값과 동일 정의) |
| `minutePerImprovement` | number | 분당개선 지표 = 재차인원 감소량 ÷ 추가 소요시간. 이 값이 낮은 경로는 "많이 돌아가는데 안 편해지는" 경로라 필터링 후보 |
| `path` | `{lat, lng}[]` | 지도에 선으로 그릴 좌표 목록 |
| `steps` | `{mode, label, durationMin}[]` | 경로 목록 화면에 "환승 단계"로 보여줄 텍스트 |

## 4. 확정되지 않은 부분 (백엔드팀과 계속 맞춰야 함)

- `netOnboardScore`의 정확한 스케일(0~100인지, 실제 인원수인지) — 김재우님 배치 결과 확정되면 갱신
- 따릉이(`BIKE`) 후보가 포함될 때 대여소 실시간 재고가 0이면 이 응답에서 빼는지, 아니면 "재고없음" 플래그로 표시하는지
- 에러 응답 형태(예: ODsay 실패, 좌표가 서울 밖인 경우) — 아직 미정, 우선 프론트는 `routes: []`로만 가정하고 진행

## 5. 변경 이력

| 날짜 | 변경 내용 | 작성자 |
|---|---|---|
| 2026-08-18 | 최초 초안 (프론트 작업 시작을 위한 draft) | 윤상은 |
