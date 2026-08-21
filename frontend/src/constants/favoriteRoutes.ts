// "전체" 탭 전용 즐겨찾기 — 장소 하나가 아니라 자주 이용하는 출발→도착 경로 쌍을 저장한다.
// (지하철/자전거 탭은 여전히 favoriteStops.ts의 장소 단위 즐겨찾기를 쓴다.)

export interface FavoriteRoute {
  id: string;
  originName: string;
  destinationName: string;
}

export const FAVORITE_ROUTES: FavoriteRoute[] = [
  { id: "euljiro-myeongdong", originName: "을지로입구역", destinationName: "명동역" },
  { id: "gangnam-yeoksam", originName: "강남역", destinationName: "역삼역" },
  { id: "hongik-sinchon", originName: "홍대입구역", destinationName: "신촌역" },
];
