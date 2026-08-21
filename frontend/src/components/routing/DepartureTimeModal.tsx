import { useState } from "react";
import "./DepartureTimeModal.css";

export type DepartureChoice = { mode: "now" } | { mode: "scheduled"; date: Date };

interface DepartureTimeModalProps {
  initial: DepartureChoice;
  onConfirm: (choice: DepartureChoice) => void;
  onClose: () => void;
}

const HOURS = Array.from({ length: 12 }, (_, i) => i + 1);
const MINUTES = Array.from({ length: 60 }, (_, i) => i);

function toParts(date: Date) {
  const hour24 = date.getHours();
  return {
    isToday: date.toDateString() === new Date().toDateString(),
    ampm: hour24 < 12 ? ("AM" as const) : ("PM" as const),
    hour12: hour24 % 12 === 0 ? 12 : hour24 % 12,
    minute: date.getMinutes(),
  };
}

// 참고 화면(카카오맵 "출발 시각 설정" 바텀시트)의 토글 + 시간선택 + 지금출발/확인 구조를 그대로
// 따른 실험용(ui-sandbox) 모달. 실제 날짜/시간 휠 대신 select로 단순화했다.
export function DepartureTimeModal({ initial, onConfirm, onClose }: DepartureTimeModalProps) {
  const initialParts = initial.mode === "scheduled" ? toParts(initial.date) : toParts(new Date());
  const [useCustomTime, setUseCustomTime] = useState(initial.mode === "scheduled");
  const [isToday, setIsToday] = useState(initialParts.isToday);
  const [ampm, setAmpm] = useState<"AM" | "PM">(initialParts.ampm);
  const [hour12, setHour12] = useState(initialParts.hour12);
  const [minute, setMinute] = useState(initialParts.minute);

  function buildDate(): Date {
    const base = new Date();
    if (!isToday) base.setDate(base.getDate() + 1);
    const hour24 = (hour12 % 12) + (ampm === "PM" ? 12 : 0);
    base.setHours(hour24, minute, 0, 0);
    return base;
  }

  function handleConfirm() {
    onConfirm(useCustomTime ? { mode: "scheduled", date: buildDate() } : { mode: "now" });
  }

  return (
    <div className="departure-modal__overlay" onClick={onClose}>
      <div className="departure-modal__sheet" onClick={(e) => e.stopPropagation()}>
        <div className="departure-modal__header">
          <h3>출발 시각 설정</h3>
          <button type="button" className="departure-modal__close" onClick={onClose} aria-label="닫기">
            ✕
          </button>
        </div>

        <div className="departure-modal__toggle-row">
          <div>
            <p className="departure-modal__toggle-title">출발 시각 설정</p>
            <p className="departure-modal__toggle-desc">
              출발 시각을 기준으로 대기 시간과 운행 정보를 고려한 경로로 안내합니다.
            </p>
          </div>
          <button
            type="button"
            className={
              useCustomTime ? "departure-modal__switch departure-modal__switch--on" : "departure-modal__switch"
            }
            onClick={() => setUseCustomTime((v) => !v)}
            role="switch"
            aria-checked={useCustomTime}
            aria-label="출발 시각 설정 사용"
          >
            <span className="departure-modal__switch-knob" />
          </button>
        </div>

        {useCustomTime && (
          <div className="departure-modal__pickers">
            <select
              value={isToday ? "today" : "tomorrow"}
              onChange={(e) => setIsToday(e.target.value === "today")}
              aria-label="출발 날짜"
            >
              <option value="today">오늘</option>
              <option value="tomorrow">내일</option>
            </select>
            <select value={ampm} onChange={(e) => setAmpm(e.target.value as "AM" | "PM")} aria-label="오전/오후">
              <option value="AM">오전</option>
              <option value="PM">오후</option>
            </select>
            <select value={hour12} onChange={(e) => setHour12(Number(e.target.value))} aria-label="시">
              {HOURS.map((h) => (
                <option key={h} value={h}>
                  {h}
                </option>
              ))}
            </select>
            <span className="departure-modal__colon">:</span>
            <select value={minute} onChange={(e) => setMinute(Number(e.target.value))} aria-label="분">
              {MINUTES.map((m) => (
                <option key={m} value={m}>
                  {String(m).padStart(2, "0")}
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="departure-modal__actions">
          <button type="button" className="departure-modal__now" onClick={() => onConfirm({ mode: "now" })}>
            지금 출발
          </button>
          <button type="button" className="departure-modal__confirm" onClick={handleConfirm}>
            확인
          </button>
        </div>
      </div>
    </div>
  );
}
