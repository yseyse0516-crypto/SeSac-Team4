// ⚠️ 샌드박스 데모 전용 — 브라우저 localStorage에만 저장, 서버로 전송하지 않는다.
// 네이버지도/카카오지하철처럼 출발지·도착지 입력창에 포커스하면 최근 검색어가 드롭다운으로 뜨는 걸 흉내낸다.
// 보기모드(지도/지하철/따릉이)별로 검색 대상이 달라서, 카테고리별로 별도 목록을 둔다.

export type SearchCategory = "map" | "subway" | "bike";

const STORAGE_KEY_PREFIX = "bium_sandbox_recent_searches_";
const MAX_ITEMS = 8;

const SEED_BY_CATEGORY: Record<SearchCategory, string[]> = {
  subway: ["강남역", "홍대입구역", "잠실역", "신도림역"],
  bike: ["금천구청역 3번출구", "철산역 1번출구", "독산역 앞", "독산사거리"],
  map: ["레미안위브아파트", "독산사거리", "강남구청"],
};

function storageKey(category: SearchCategory) {
  return `${STORAGE_KEY_PREFIX}${category}`;
}

export function getRecentSearches(category: SearchCategory): string[] {
  try {
    const raw = localStorage.getItem(storageKey(category));
    return raw ? JSON.parse(raw) : SEED_BY_CATEGORY[category];
  } catch {
    return SEED_BY_CATEGORY[category];
  }
}

// 지도에서 좌표로 찍은 값("📍 지도에서 선택 ...")이나 "현재 위치"는 검색어 기록으로 의미가 없어서 제외.
export function addRecentSearch(category: SearchCategory, value: string): string[] {
  const trimmed = value.trim();
  if (!trimmed || trimmed.startsWith("📍") || trimmed === "현재 위치") {
    return getRecentSearches(category);
  }
  const next = [trimmed, ...getRecentSearches(category).filter((v) => v !== trimmed)].slice(0, MAX_ITEMS);
  localStorage.setItem(storageKey(category), JSON.stringify(next));
  return next;
}
