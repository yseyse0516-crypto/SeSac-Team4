import "./ViewModeToolbar.css";

// 상세 동작(각 모드에서 실제로 뭘 다르게 보여줄지)은 아직 미정 — 지금은 탭 구조만 구현.
export type ViewMode = "map" | "subway" | "bike";

const MODES: { key: ViewMode; label: string; icon: string }[] = [
  { key: "map", label: "전체", icon: "🗺️" },
  { key: "subway", label: "지하철", icon: "🚇" },
  { key: "bike", label: "자전거", icon: "🚲" },
];

interface ViewModeToolbarProps {
  value: ViewMode;
  onChange: (mode: ViewMode) => void;
}

// 출발지/도착지 입력 위, 화면 맨 위에 독립적으로 뜨는 큰 탭 — 아이콘을 키워서 한눈에 구분되게 한다.
export function ViewModeToolbar({ value, onChange }: ViewModeToolbarProps) {
  return (
    <div className="view-mode-toolbar">
      {MODES.map((mode) => (
        <button
          key={mode.key}
          type="button"
          className={
            value === mode.key
              ? "view-mode-toolbar__item view-mode-toolbar__item--active"
              : "view-mode-toolbar__item"
          }
          onClick={() => onChange(mode.key)}
        >
          <span className="view-mode-toolbar__icon">{mode.icon}</span>
          <span>{mode.label}</span>
        </button>
      ))}
    </div>
  );
}
