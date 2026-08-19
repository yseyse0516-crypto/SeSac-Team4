import { useState } from "react";
import { FAVORITE_STOPS } from "../../constants/favoriteStops";
import "./RouteSearchForm.css";

// 목업의 "경로탐색" 입력 영역과 동일한 필드: 출발지/도착지/기준시간 + 즐겨찾기 + 탐색버튼.
// 아직 지도 좌표 변환(geocoding)은 없어서, 우선 텍스트 값만 부모 화면으로 넘긴다.
// 나중에 좌표 변환 기능이 생기면 이 컴포넌트는 그대로 두고, 부모 화면에서 좌표로 바꿔 fetchRoutes에 넘기면 된다.

export interface RouteSearchValues {
  originText: string;
  destinationText: string;
  departAt: string; // "HH:mm" 형태
}

interface RouteSearchFormProps {
  onSearch: (values: RouteSearchValues) => void;
}

// 출퇴근 시간대를 매번 직접 스크롤/타이핑하지 않도록, 자주 쓰는 시간대를 원탭으로 채워주는 프리셋.
// ui-ux-guide.md §2 — 기존 <input type="time">의 값을 세팅하는 단축키 역할만 하고, 별도 데이터는 추가하지 않는다.
const TIME_PRESETS = [
  { label: "오전 8시 출근", value: "08:00" },
  { label: "오후 6시 퇴근", value: "18:00" },
];

export function RouteSearchForm({ onSearch }: RouteSearchFormProps) {
  const [originText, setOriginText] = useState("");
  const [destinationText, setDestinationText] = useState("");
  const [departAt, setDepartAt] = useState("08:00");

  function handleSwap() {
    setOriginText(destinationText);
    setDestinationText(originText);
  }

  function handleFavoriteClick(name: string) {
    setDestinationText(name);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSearch({ originText, destinationText, departAt });
  }

  return (
    <form className="route-search-form" onSubmit={handleSubmit}>
      <div className="route-search-form__row">
        <label className="route-search-form__field">
          <span>출발지</span>
          <input
            value={originText}
            onChange={(e) => setOriginText(e.target.value)}
            placeholder="출발지를 입력하세요"
          />
        </label>

        <button
          type="button"
          className="route-search-form__swap"
          onClick={handleSwap}
          aria-label="출발지와 도착지 바꾸기"
        >
          ⇄
        </button>

        <label className="route-search-form__field">
          <span>도착지</span>
          <input
            value={destinationText}
            onChange={(e) => setDestinationText(e.target.value)}
            placeholder="도착지를 입력하세요"
          />
        </label>

        <label className="route-search-form__field route-search-form__field--time">
          <span>기준시간</span>
          <input
            type="time"
            value={departAt}
            onChange={(e) => setDepartAt(e.target.value)}
          />
        </label>
      </div>

      <div className="route-search-form__time-presets">
        {TIME_PRESETS.map((preset) => (
          <button
            key={preset.value}
            type="button"
            className={
              departAt === preset.value
                ? "route-search-form__preset route-search-form__preset--active"
                : "route-search-form__preset"
            }
            onClick={() => setDepartAt(preset.value)}
          >
            {preset.label}
          </button>
        ))}
      </div>

      <div className="route-search-form__favorites">
        <span>즐겨찾기</span>
        {FAVORITE_STOPS.map((stop) => (
          <button
            key={stop.id}
            type="button"
            onClick={() => handleFavoriteClick(stop.name)}
          >
            {stop.name}
          </button>
        ))}
      </div>

      <button type="submit" className="route-search-form__submit">
        탐색
      </button>
    </form>
  );
}
