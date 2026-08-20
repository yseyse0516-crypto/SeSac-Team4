import { useEffect, useRef, useState } from "react";
import type { LatLng } from "../../types/routing";
import { KAKAO_MAP_KEY, loadKakaoMaps } from "../../api/kakaoMapLoader";
import "./LocationPickerMap.css";

interface LocationPickerMapProps {
  center: LatLng;
  onPick: (point: LatLng) => void;
}

// 카카오맵 키가 있으면 실제 지도에서 탭한 좌표를 그대로 쓰고,
// 없으면(지금 상태) 클릭 위치를 center 기준 좌표로 근사 변환하는 격자 placeholder를 보여준다.
// 실험용 fallback이라 실제 거리 축척과는 무관하다 — 키가 들어오면 이 분기는 자연히 안 쓰이게 된다.
export function LocationPickerMap({ center, onPick }: LocationPickerMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [pin, setPin] = useState<{ x: number; y: number } | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!KAKAO_MAP_KEY || !containerRef.current) return;

    let cancelled = false;
    loadKakaoMaps(KAKAO_MAP_KEY).then(() => {
      if (cancelled || !containerRef.current) return;
      const kakao = window.kakao;
      const map = new kakao.maps.Map(containerRef.current, {
        center: new kakao.maps.LatLng(center.lat, center.lng),
        level: 5,
      });
      let marker: any = null;
      kakao.maps.event.addListener(map, "click", (mouseEvent: any) => {
        const latlng = mouseEvent.latLng;
        if (marker) marker.setMap(null);
        marker = new kakao.maps.Marker({ map, position: latlng });
        onPick({ lat: latlng.getLat(), lng: latlng.getLng() });
      });
      setReady(true);
    });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (KAKAO_MAP_KEY) {
    return (
      <div className="location-picker-map">
        <span className="location-picker-map__hint">지도를 탭해서 위치를 지정하세요</span>
        <div ref={containerRef} style={{ width: "100%", height: "100%" }} />
        {!ready && <div className="location-picker-map__fallback" />}
      </div>
    );
  }

  function handleFallbackClick(e: React.MouseEvent<HTMLDivElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setPin({ x, y });

    // 박스 중앙을 center 좌표로 보고, 클릭 위치의 상대 오프셋을 위경도 근사값으로 변환.
    const dx = (x - rect.width / 2) / rect.width;
    const dy = (y - rect.height / 2) / rect.height;
    onPick({ lat: center.lat - dy * 0.02, lng: center.lng + dx * 0.02 });
  }

  return (
    <div className="location-picker-map">
      <span className="location-picker-map__hint">
        카카오맵 키 설정 전 임시 시뮬레이션 — 클릭해서 위치 지정
      </span>
      <div className="location-picker-map__fallback" onClick={handleFallbackClick}>
        {pin && (
          <span className="location-picker-map__pin" style={{ left: pin.x, top: pin.y }}>
            📍
          </span>
        )}
      </div>
    </div>
  );
}
