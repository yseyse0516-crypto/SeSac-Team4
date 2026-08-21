import type { LatLng } from "../types/routing";

// 좌표를 실제 주소 문자열로 바꾼다(역지오코딩) — 도로명 주소가 있으면 그걸 우선하고,
// 없으면 지번 주소로 폴백한다. 실패하면 null(호출부가 좌표/기본 라벨로 폴백).
// SearchMap(지도 클릭)과 RouteSearchForm(현재 위치 기본값)이 같이 쓴다.
export function reverseGeocode(point: LatLng): Promise<string | null> {
  return new Promise((resolve) => {
    const kakao = window.kakao;
    if (!kakao?.maps?.services) {
      resolve(null);
      return;
    }
    const geocoder = new kakao.maps.services.Geocoder();
    geocoder.coord2Address(point.lng, point.lat, (result: any[], status: string) => {
      if (status !== kakao.maps.services.Status.OK || !result[0]) {
        resolve(null);
        return;
      }
      const address = result[0].road_address?.address_name ?? result[0].address?.address_name ?? null;
      resolve(address);
    });
  });
}
