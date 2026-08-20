// RouteMap과 LocationPickerMap이 공유하는 카카오맵 SDK 로더.
// npm 패키지가 아니라 <script> 태그로 로드하는 방식이라 타입은 any로 최소화.
declare global {
  interface Window {
    kakao: any;
  }
}

export const KAKAO_MAP_KEY = import.meta.env.VITE_KAKAO_MAP_KEY;

let kakaoLoadPromise: Promise<void> | null = null;

// 스크립트 자체는 정상 로드됐는데 maps.load()의 콜백이 안 불리는 경우(JS 키에 등록한
// 도메인과 실제 접속 도메인이 다를 때 카카오 SDK가 콘솔에만 에러를 남기고 콜백을 아예
// 안 부르는 게 대표적 원인) 타임아웃 없이는 무한 로딩(빈 화면)에 빠진다 — 명시적으로
// 실패 처리해서 "지도를 불러오지 못했습니다" 화면으로 넘어가게 한다.
const LOAD_TIMEOUT_MS = 8000;

export function loadKakaoMaps(appKey: string): Promise<void> {
  if (kakaoLoadPromise) return kakaoLoadPromise;

  const promise = new Promise<void>((resolve, reject) => {
    const timer = setTimeout(() => {
      fail(
        new Error(
          "카카오맵 SDK 로드 타임아웃 — 앱 키에 등록한 도메인과 현재 접속 도메인이 일치하는지 확인하세요."
        )
      );
    }, LOAD_TIMEOUT_MS);

    // 실패한 로드는 캐싱하지 않는다 — 키/도메인을 고친 뒤 재시도하면 다시 로드를 시도해야 하므로.
    function fail(err: Error) {
      clearTimeout(timer);
      kakaoLoadPromise = null;
      reject(err);
    }

    const script = document.createElement("script");
    // libraries=services — 좌표를 주소로 바꾸는 Geocoder(역지오코딩)에 필요.
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?autoload=false&appkey=${appKey}&libraries=services`;
    script.onload = () =>
      window.kakao.maps.load(() => {
        clearTimeout(timer);
        resolve();
      });
    script.onerror = () => fail(new Error("카카오맵 SDK 로드 실패"));
    document.head.appendChild(script);
  });

  kakaoLoadPromise = promise;
  return promise;
}
