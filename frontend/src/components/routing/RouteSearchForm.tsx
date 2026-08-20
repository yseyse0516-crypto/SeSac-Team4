import { useEffect, useState } from "react";
import { FAVORITE_STOPS, type FavoriteStop } from "../../constants/favoriteStops";
import { SearchMap } from "./SearchMap";
import { SubwayLineDiagram } from "./SubwayLineDiagram";
import { addRecentSearch, getRecentSearches, type SearchCategory } from "../../utils/recentSearches";
import type { LatLng, RouteCandidate } from "../../types/routing";
import "./RouteSearchForm.css";

// 출발지/도착지 + 즐겨찾기 + 탐색버튼. 기준시간 입력은 뺐다 — 실행하는 시점의 현재 시간
// 기준으로 바로 조회하면 되는 기능이라 별도 입력이 불필요하다는 판단 (RouteSearchPage에서 처리).
// 실험(ui-sandbox) 버전: 타이핑 대신 지도 탭으로도 좌표를 고를 수 있고, 출발지 기본값은 브라우저
// Geolocation으로 채운다. 실제 BIUM 리포지토리(frontend/)에는 아직 반영 안 함.

export interface RouteSearchValues {
  originText: string;
  destinationText: string;
  originCoords?: LatLng;
  destinationCoords?: LatLng;
}

interface RouteSearchFormProps {
  onSearch: (values: RouteSearchValues) => void;
  searchCategory: SearchCategory;
  routes: RouteCandidate[];
  onlyRecommended: boolean;
  showBikeToggle?: boolean;
}

// Geolocation 실패/미허용 시, 지도 placeholder의 기준점으로 쓸 서울시청 좌표.
const DEFAULT_CENTER: LatLng = { lat: 37.5665, lng: 126.978 };

type ActivePicker = "origin" | "destination" | null;

export function RouteSearchForm({
  onSearch,
  searchCategory,
  routes,
  onlyRecommended,
  showBikeToggle,
}: RouteSearchFormProps) {
  const [originText, setOriginText] = useState("");
  const [destinationText, setDestinationText] = useState("");
  const [originCoords, setOriginCoords] = useState<LatLng | null>(null);
  const [destinationCoords, setDestinationCoords] = useState<LatLng | null>(null);
  const [activePicker, setActivePicker] = useState<ActivePicker>(null);
  const [locating, setLocating] = useState(false);

  // 네이버지도/카카오지하철처럼 출발지·도착지 입력창에 포커스하면 최근 검색어를 드롭다운으로 보여준다.
  // 보기모드(지도/지하철/따릉이)가 바뀌면 검색 대상이 달라서 목록도 같이 바뀐다.
  const [recentSearches, setRecentSearches] = useState<string[]>(getRecentSearches(searchCategory));
  const [suggestField, setSuggestField] = useState<"origin" | "destination" | null>(null);

  useEffect(() => {
    setRecentSearches(getRecentSearches(searchCategory));
  }, [searchCategory]);

  // 출발지 기본값 = 현재 위치. 사용자가 이미 뭔가 입력했으면 덮어쓰지 않는다.
  useEffect(() => {
    if (!navigator.geolocation) return;
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocating(false);
        setOriginCoords((prev) => prev ?? { lat: pos.coords.latitude, lng: pos.coords.longitude });
        setOriginText((prev) => (prev ? prev : "현재 위치"));
      },
      () => setLocating(false),
      { timeout: 5000 }
    );
  }, []);

  // 즐겨찾기도 편집 가능하게 — 이 화면 세션 동안만 유지되는 로컬 state (새로고침하면 초기 목록으로 리셋).
  const [favorites, setFavorites] = useState<FavoriteStop[]>(FAVORITE_STOPS);
  const [newFavoriteName, setNewFavoriteName] = useState("");
  const [editingFavorites, setEditingFavorites] = useState(false);

  function handleAddFavorite() {
    const name = newFavoriteName.trim();
    if (!name) return;
    setFavorites((prev) => [...prev, { id: `custom-${Date.now()}`, name }]);
    setNewFavoriteName("");
  }

  function handleRemoveFavorite(id: string) {
    setFavorites((prev) => prev.filter((stop) => stop.id !== id));
  }

  function handleSwap() {
    setOriginText(destinationText);
    setDestinationText(originText);
    setOriginCoords(destinationCoords);
    setDestinationCoords(originCoords);
  }

  function handleFavoriteClick(name: string) {
    setDestinationText(name);
    setDestinationCoords(null);
  }

  function handlePick(point: LatLng) {
    const label = `📍 지도에서 선택 (${point.lat.toFixed(4)}, ${point.lng.toFixed(4)})`;
    if (activePicker === "origin") {
      setOriginCoords(point);
      setOriginText(label);
    } else if (activePicker === "destination") {
      setDestinationCoords(point);
      setDestinationText(label);
    }
    setActivePicker(null);
  }

  function handleStationPick(field: "origin" | "destination", station: LatLng & { name: string }) {
    if (field === "origin") {
      setOriginCoords(station);
      setOriginText(`${station.name}역`);
    } else {
      setDestinationCoords(station);
      setDestinationText(`${station.name}역`);
    }
    setActivePicker(null);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    addRecentSearch(searchCategory, originText);
    setRecentSearches(addRecentSearch(searchCategory, destinationText));
    onSearch({
      originText,
      destinationText,
      originCoords: originCoords ?? undefined,
      destinationCoords: destinationCoords ?? undefined,
    });
  }

  function handleSuggestionPick(field: "origin" | "destination", value: string) {
    if (field === "origin") {
      setOriginText(value);
      setOriginCoords(null);
    } else {
      setDestinationText(value);
      setDestinationCoords(null);
    }
    setSuggestField(null);
  }

  return (
    <form className="route-search-form" onSubmit={handleSubmit}>
      <div className="route-search-form__row">
        <label className="route-search-form__field">
          <span>출발지 {locating && "(위치 확인 중...)"}</span>
          <div className="route-search-form__field-with-action route-search-form__field-suggest-anchor">
            <input
              value={originText}
              onChange={(e) => {
                setOriginText(e.target.value);
                setOriginCoords(null);
              }}
              onFocus={() => setSuggestField("origin")}
              onBlur={() => setSuggestField((f) => (f === "origin" ? null : f))}
              placeholder="출발지를 입력하세요"
            />
            <button
              type="button"
              className="route-search-form__map-pick"
              onClick={() => setActivePicker(activePicker === "origin" ? null : "origin")}
              aria-label="지도에서 출발지 선택"
            >
              🗺️
            </button>
            {suggestField === "origin" && recentSearches.length > 0 && (
              <ul className="route-search-form__suggest-list">
                {recentSearches.map((value) => (
                  <li key={value}>
                    <button
                      type="button"
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => handleSuggestionPick("origin", value)}
                    >
                      🕐 {value}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
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
          <div className="route-search-form__field-with-action route-search-form__field-suggest-anchor">
            <input
              value={destinationText}
              onChange={(e) => {
                setDestinationText(e.target.value);
                setDestinationCoords(null);
              }}
              onFocus={() => setSuggestField("destination")}
              onBlur={() => setSuggestField((f) => (f === "destination" ? null : f))}
              placeholder="도착지를 입력하세요"
            />
            <button
              type="button"
              className="route-search-form__map-pick"
              onClick={() => setActivePicker(activePicker === "destination" ? null : "destination")}
              aria-label="지도에서 도착지 선택"
            >
              🗺️
            </button>
            {suggestField === "destination" && recentSearches.length > 0 && (
              <ul className="route-search-form__suggest-list">
                {recentSearches.map((value) => (
                  <li key={value}>
                    <button
                      type="button"
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => handleSuggestionPick("destination", value)}
                    >
                      🕐 {value}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </label>
      </div>

      {searchCategory === "subway" ? (
        <SubwayLineDiagram
          activePicker={activePicker}
          onPickStation={handleStationPick}
          routes={routes}
          onlyRecommended={onlyRecommended}
        />
      ) : (
        <SearchMap
          center={
            (activePicker === "origin" ? originCoords : destinationCoords) ?? originCoords ?? DEFAULT_CENTER
          }
          activePicker={activePicker}
          onPick={handlePick}
          routes={routes}
          onlyRecommended={onlyRecommended}
          showBikeToggle={showBikeToggle}
        />
      )}

      <div className="route-search-form__favorites">
        <span>즐겨찾기</span>
        {favorites.map((stop) =>
          editingFavorites ? (
            <span key={stop.id} className="route-search-form__favorite-editable">
              {stop.name}
              <button
                type="button"
                className="route-search-form__favorite-remove"
                onClick={() => handleRemoveFavorite(stop.id)}
                aria-label={`${stop.name} 즐겨찾기 삭제`}
              >
                ✕
              </button>
            </span>
          ) : (
            <button key={stop.id} type="button" onClick={() => handleFavoriteClick(stop.name)}>
              {stop.name}
            </button>
          )
        )}

        {editingFavorites && (
          <span className="route-search-form__favorite-add">
            <input
              value={newFavoriteName}
              onChange={(e) => setNewFavoriteName(e.target.value)}
              placeholder="장소 이름"
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  handleAddFavorite();
                }
              }}
            />
            <button type="button" onClick={handleAddFavorite}>
              추가
            </button>
          </span>
        )}

        <button
          type="button"
          className="route-search-form__favorite-edit-toggle"
          onClick={() => setEditingFavorites((prev) => !prev)}
        >
          {editingFavorites ? "완료" : "편집"}
        </button>
      </div>

      <button type="submit" className="route-search-form__submit">
        탐색
      </button>
    </form>
  );
}
