import { useEffect, useState } from "react";
import { FAVORITE_STOPS, type FavoriteStop } from "../../constants/favoriteStops";
import { FAVORITE_ROUTES, type FavoriteRoute } from "../../constants/favoriteRoutes";
import { SearchMap } from "./SearchMap";
import { FavoriteRoutesBar } from "./FavoriteRoutesBar";
import { DepartureTimeModal, type DepartureChoice } from "./DepartureTimeModal";
import { SubwayLineDiagram } from "./SubwayLineDiagram";
import { addRecentSearch, getRecentSearches, type SearchCategory } from "../../utils/recentSearches";
import { reverseGeocode } from "../../utils/reverseGeocode";
import { KAKAO_MAP_KEY, loadKakaoMaps } from "../../api/kakaoMapLoader";
import type { LatLng, RouteCandidate } from "../../types/routing";
import "./RouteSearchForm.css";

// 출발지/도착지 입력창에 지명을 타이핑하거나 즐겨찾기를 클릭했을 때(지도 클릭 없이)
// 실제 좌표로 바꿔주는 지오코딩 — 카카오 키워드 장소검색(Places)을 쓴다. 실패하면 null
// (호출부가 "출발지를 다시 선택해 주세요" 에러로 처리하고, 절대 임의 좌표로 조용히 대체하지 않는다).
async function searchPlace(keyword: string): Promise<LatLng | null> {
  if (!KAKAO_MAP_KEY) return null;
  try {
    await loadKakaoMaps(KAKAO_MAP_KEY);
  } catch {
    return null;
  }
  return new Promise((resolve) => {
    const kakao = window.kakao;
    const places = new kakao.maps.services.Places();
    places.keywordSearch(keyword, (result: any[], status: string) => {
      if (status !== kakao.maps.services.Status.OK || !result[0]) {
        resolve(null);
        return;
      }
      resolve({ lat: Number(result[0].y), lng: Number(result[0].x) });
    });
  });
}

// 출발지/도착지 + 즐겨찾기 + 탐색버튼. 기준시간 입력은 뺐다 — 실행하는 시점의 현재 시간
// 기준으로 바로 조회하면 되는 기능이라 별도 입력이 불필요하다는 판단 (RouteSearchPage에서 처리).
// 실험(ui-sandbox) 버전: 타이핑 대신 지도 탭으로도 좌표를 고를 수 있고, 출발지 기본값은 브라우저
// Geolocation으로 채운다. 실제 텅텅 리포지토리(frontend/)에는 아직 반영 안 함.

export interface RouteSearchValues {
  originText: string;
  destinationText: string;
  originCoords?: LatLng;
  destinationCoords?: LatLng;
  departureTime?: string; // ISO 8601. "지금 출발"이면 undefined(백엔드가 현재 시각으로 조회).
}

function formatDepartureLabel(departure: DepartureChoice): string {
  if (departure.mode === "now") return "지금 출발";
  const { date } = departure;
  const isToday = date.toDateString() === new Date().toDateString();
  const dayLabel = isToday ? "오늘" : "내일";
  const hh = String(date.getHours()).padStart(2, "0");
  const mm = String(date.getMinutes()).padStart(2, "0");
  return `${dayLabel} ${hh}:${mm} 출발`;
}

interface RouteSearchFormProps {
  onSearch: (values: RouteSearchValues) => void;
  searchCategory: SearchCategory;
  routes: RouteCandidate[];
  onlyRecommended: boolean;
  // "전체" 탭에서 최단시간/추천 카드를 선택했을 때 지도에 그 경로만 상세히(구간별 색상 + 정류장 라벨) 보여주기 위한 값.
  selectedRoute?: RouteCandidate | null;
}

// Geolocation 실패/미허용 시, 지도 placeholder의 기준점으로 쓸 서울시청 좌표.
const DEFAULT_CENTER: LatLng = { lat: 37.5665, lng: 126.978 };

type ActivePicker = "origin" | "destination" | null;

export function RouteSearchForm({
  onSearch,
  searchCategory,
  routes,
  onlyRecommended,
  selectedRoute,
}: RouteSearchFormProps) {
  const [originText, setOriginText] = useState("");
  const [destinationText, setDestinationText] = useState("");
  const [originCoords, setOriginCoords] = useState<LatLng | null>(null);
  const [destinationCoords, setDestinationCoords] = useState<LatLng | null>(null);
  const [activePicker, setActivePicker] = useState<ActivePicker>(null);
  const [locating, setLocating] = useState(false);
  const [resolving, setResolving] = useState(false);

  // 회의록: "기준시간 입력 다시 살리기" — 기본은 지금 출발, 필요하면 모달에서 미래 시각 지정.
  const [departure, setDeparture] = useState<DepartureChoice>({ mode: "now" });
  const [showDepartureModal, setShowDepartureModal] = useState(false);

  // 출발지/도착지를 같은 곳으로 입력했을 때(예: 홍대입구역 → 홍대입구역) 검색 대신 팝업으로 알린다.
  const [sameLocationError, setSameLocationError] = useState(false);

  // 네이버지도/카카오지하철처럼 출발지·도착지 입력창에 포커스하면 최근 검색어를 드롭다운으로 보여준다.
  // 보기모드(지도/지하철/따릉이)가 바뀌면 검색 대상이 달라서 목록도 같이 바뀐다.
  const [recentSearches, setRecentSearches] = useState<string[]>(getRecentSearches(searchCategory));
  const [suggestField, setSuggestField] = useState<"origin" | "destination" | null>(null);

  useEffect(() => {
    setRecentSearches(getRecentSearches(searchCategory));
  }, [searchCategory]);

  // 출발지 기본값 = 현재 위치. 사용자가 이미 뭔가 입력했으면 덮어쓰지 않는다.
  // "현재 위치" 텍스트로 먼저 채우고, 역지오코딩이 끝나면 실제 주소로 바꿔준다(그 사이
  // 사용자가 직접 입력/선택했으면 — 즉 텍스트가 더 이상 "현재 위치"가 아니면 — 덮어쓰지 않음).
  useEffect(() => {
    if (!navigator.geolocation) return;
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocating(false);
        const point = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        setOriginCoords((prev) => prev ?? point);
        setOriginText((prev) => (prev ? prev : "현재 위치"));

        // 카카오 SDK는 SearchMap이 별도로(비동기) 로드한다 — geolocation이 그보다 먼저
        // 끝나버리면 window.kakao가 아직 없어서 역지오코딩이 조용히 실패할 수 있으니,
        // 로드가 끝날 때까지 기다렸다가 역지오코딩한다.
        if (!KAKAO_MAP_KEY) return;
        loadKakaoMaps(KAKAO_MAP_KEY)
          .then(() => reverseGeocode(point))
          .then((address) => {
            if (!address) return;
            setOriginText((prev) => (prev === "현재 위치" ? address : prev));
          })
          .catch(() => {});
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

  // "전체" 탭 전용 — 장소 하나가 아니라 자주 이용하는 출발→도착 경로 쌍을 즐겨찾기로 쓴다.
  const [favoriteRoutes, setFavoriteRoutes] = useState<FavoriteRoute[]>(FAVORITE_ROUTES);

  function handleFavoriteRoutePick(route: FavoriteRoute) {
    setOriginText(route.originName);
    setOriginCoords(null);
    setDestinationText(route.destinationName);
    setDestinationCoords(null);
  }

  function handleAddFavoriteRoute(originName: string, destinationName: string) {
    setFavoriteRoutes((prev) => [...prev, { id: `custom-route-${Date.now()}`, originName, destinationName }]);
  }

  function handleRemoveFavoriteRoute(id: string) {
    setFavoriteRoutes((prev) => prev.filter((route) => route.id !== id));
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

  // handlePick은 클릭 한 번에 두 번 불린다: 클릭 즉시(좌표만) 한 번, 역지오코딩이 끝난 뒤
  // (주소 포함) 한 번 더. field는 SearchMap이 클릭 시점에 캡처해서 두 호출 모두에 그대로
  // 넘겨준다 — activePicker(상태)로 유추하면, 첫 호출 처리 중 바로 null로 리셋되거나 그
  // 사이 사용자가 반대 필드를 또 클릭했을 때 잘못된 필드에 주소가 적용되는 버그가 있었다.
  function handlePick(field: "origin" | "destination", point: LatLng, address?: string) {
    const isFirstCall = address === undefined;
    const label = address ?? `📍 지도에서 선택 (${point.lat.toFixed(4)}, ${point.lng.toFixed(4)})`;
    if (field === "origin") {
      setOriginCoords(point);
      setOriginText(label);
    } else if (field === "destination") {
      setDestinationCoords(point);
      setDestinationText(label);
    }
    if (isFirstCall) setActivePicker(null);
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

  function isSameLocation(oText: string, dText: string, oCoords: LatLng | null, dCoords: LatLng | null): boolean {
    if (oText.trim() && oText.trim() === dText.trim()) return true;
    return !!oCoords && !!dCoords && oCoords.lat === dCoords.lat && oCoords.lng === dCoords.lng;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    if (isSameLocation(originText, destinationText, originCoords, destinationCoords)) {
      setSameLocationError(true);
      return;
    }

    // 지도 클릭이나 즐겨찾기로 이미 좌표가 채워져 있으면 그대로 쓰고, 텍스트만 있고 좌표가
    // 없는 경우(직접 타이핑, 즐겨찾기 클릭 등)에만 지오코딩한다.
    let resolvedOrigin = originCoords;
    let resolvedDestination = destinationCoords;

    setResolving(true);
    if (!resolvedOrigin && originText.trim()) {
      resolvedOrigin = await searchPlace(originText.trim());
      if (resolvedOrigin) setOriginCoords(resolvedOrigin);
    }
    if (!resolvedDestination && destinationText.trim()) {
      resolvedDestination = await searchPlace(destinationText.trim());
      if (resolvedDestination) setDestinationCoords(resolvedDestination);
    }
    setResolving(false);

    // 서로 다른 텍스트가 같은 지점으로 지오코딩되는 경우(예: 같은 역을 다른 표기로 입력)도 잡는다.
    if (isSameLocation(originText, destinationText, resolvedOrigin, resolvedDestination)) {
      setSameLocationError(true);
      return;
    }

    addRecentSearch(searchCategory, originText);
    setRecentSearches(addRecentSearch(searchCategory, destinationText));
    onSearch({
      originText,
      destinationText,
      originCoords: resolvedOrigin ?? undefined,
      destinationCoords: resolvedDestination ?? undefined,
      departureTime: departure.mode === "scheduled" ? departure.date.toISOString() : undefined,
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

      <div className="route-search-form__departure-row">
        <button
          type="button"
          className="route-search-form__departure-chip"
          onClick={() => setShowDepartureModal(true)}
        >
          🕐 {formatDepartureLabel(departure)} ⌵
        </button>
      </div>

      {showDepartureModal && (
        <DepartureTimeModal
          initial={departure}
          onClose={() => setShowDepartureModal(false)}
          onConfirm={(choice) => {
            setDeparture(choice);
            setShowDepartureModal(false);
          }}
        />
      )}

      {searchCategory === "subway" ? (
        <SubwayLineDiagram
          key={searchCategory}
          activePicker={activePicker}
          onPickStation={handleStationPick}
          routes={routes}
          onlyRecommended={onlyRecommended}
        />
      ) : (
        // key={searchCategory} — 전체/지하철 탭을 오갈 때마다 지도를 완전히 새로 마운트해서
        // 새로고침한다(자전거 탭은 이제 이 컴포넌트를 안 쓰고 별도의 BikeDockFinder를 쓴다).
        <SearchMap
          key={searchCategory}
          center={
            (activePicker === "origin" ? originCoords : destinationCoords) ?? originCoords ?? DEFAULT_CENTER
          }
          activePicker={activePicker}
          onPick={handlePick}
          routes={routes}
          onlyRecommended={onlyRecommended}
          origin={searchCategory === "map" ? originCoords : undefined}
          destination={searchCategory === "map" ? destinationCoords : undefined}
          selectedRoute={searchCategory === "map" ? selectedRoute : undefined}
        />
      )}

      {searchCategory === "map" ? (
        <FavoriteRoutesBar
          favorites={favoriteRoutes}
          onPick={handleFavoriteRoutePick}
          onAdd={handleAddFavoriteRoute}
          onRemove={handleRemoveFavoriteRoute}
        />
      ) : (
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
      )}

      <button type="submit" className="route-search-form__submit" disabled={resolving}>
        {resolving ? "위치 확인 중..." : "탐색"}
      </button>

      {sameLocationError && (
        <div className="route-search-form__popup-overlay" onClick={() => setSameLocationError(false)}>
          <div
            className="route-search-form__popup-card"
            role="alertdialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
          >
            <p>출발지와 목적지가 같습니다.</p>
            <button type="button" onClick={() => setSameLocationError(false)}>
              확인
            </button>
          </div>
        </div>
      )}
    </form>
  );
}
