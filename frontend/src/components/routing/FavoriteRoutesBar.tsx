import { useState } from "react";
import type { FavoriteRoute } from "../../constants/favoriteRoutes";
import "./FavoriteRoutesBar.css";

interface FavoriteRoutesBarProps {
  favorites: FavoriteRoute[];
  onPick: (route: FavoriteRoute) => void;
  onAdd: (originName: string, destinationName: string) => void;
  onRemove: (id: string) => void;
}

// "전체" 탭 전용 즐겨찾기 바 — 장소 하나가 아니라 자주 다니는 출발→도착 경로 쌍을 보여준다.
export function FavoriteRoutesBar({ favorites, onPick, onAdd, onRemove }: FavoriteRoutesBarProps) {
  const [editing, setEditing] = useState(false);
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");

  function handleAdd() {
    if (!origin.trim() || !destination.trim()) return;
    onAdd(origin.trim(), destination.trim());
    setOrigin("");
    setDestination("");
  }

  return (
    <div className="favorite-routes-bar">
      <span>즐겨찾기</span>
      {favorites.map((route) =>
        editing ? (
          <span key={route.id} className="favorite-routes-bar__item-editable">
            {route.originName} → {route.destinationName}
            <button
              type="button"
              className="favorite-routes-bar__remove"
              onClick={() => onRemove(route.id)}
              aria-label={`${route.originName} → ${route.destinationName} 즐겨찾기 삭제`}
            >
              ✕
            </button>
          </span>
        ) : (
          <button key={route.id} type="button" onClick={() => onPick(route)}>
            {route.originName} → {route.destinationName}
          </button>
        )
      )}

      {editing && (
        <span className="favorite-routes-bar__add">
          <input value={origin} onChange={(e) => setOrigin(e.target.value)} placeholder="출발지" />
          <span className="favorite-routes-bar__arrow">→</span>
          <input value={destination} onChange={(e) => setDestination(e.target.value)} placeholder="도착지" />
          <button type="button" onClick={handleAdd}>
            추가
          </button>
        </span>
      )}

      <button type="button" className="favorite-routes-bar__edit-toggle" onClick={() => setEditing((v) => !v)}>
        {editing ? "완료" : "편집"}
      </button>
    </div>
  );
}
