// RouteMap과 LocationPickerMap이 공유하는 카카오맵 SDK 로더.
// npm 패키지가 아니라 <script> 태그로 로드하는 방식이라 타입은 any로 최소화.
declare global {
  interface Window {
    kakao: any;
  }
}

export const KAKAO_MAP_KEY = import.meta.env.VITE_KAKAO_MAP_KEY;

let kakaoLoadPromise: Promise<void> | null = null;

export function loadKakaoMaps(appKey: string): Promise<void> {
  if (!kakaoLoadPromise) {
    kakaoLoadPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = `https://dapi.kakao.com/v2/maps/sdk.js?autoload=false&appkey=${appKey}`;
      script.onload = () => window.kakao.maps.load(() => resolve());
      script.onerror = () => reject(new Error("카카오맵 SDK 로드 실패"));
      document.head.appendChild(script);
    });
  }
  return kakaoLoadPromise;
}
