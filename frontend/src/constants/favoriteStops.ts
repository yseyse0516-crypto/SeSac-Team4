// 목업의 "즐겨찾기" 퀵버튼(강남역, 홍대입구역 등)에 쓰는 고정 목록.
// 지금은 이름 목록만 두고, 실제 좌표는 station 마스터 데이터가 준비되면 채운다.

export interface FavoriteStop {
  id: string;
  name: string;
  lat?: number;
  lng?: number;
}

export const FAVORITE_STOPS: FavoriteStop[] = [
  { id: "gangnam", name: "강남역" },
  { id: "hongik", name: "홍대입구역" },
  { id: "yeouido", name: "여의도역" },
  { id: "pangyo", name: "판교역" },
  { id: "suseo", name: "수서역" },
];
