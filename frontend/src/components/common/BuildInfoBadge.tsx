import { useEffect, useState } from "react";
import { fetchVersionInfo, type VersionInfo } from "../../api/system";
import "./BuildInfoBadge.css";

// vite.config.ts의 define에서 frontend/package.json의 version을 빌드 시점에 주입.
declare const __APP_VERSION__: string;

// 회의록 반영: 상/하단에 항상 떠 있던 바 대신, 아이콘 눌러야 열리는 사이드바로 이동 (CLAUDE.md §12는 그대로 만족).
export function InfoSidebar() {
  const [open, setOpen] = useState(false);
  const [info, setInfo] = useState<VersionInfo | null>(null);

  useEffect(() => {
    if (!open) return;
    fetchVersionInfo()
      .then(setInfo)
      .catch(() => setInfo(null));
  }, [open]);

  const items = [
    { label: "Front version", value: __APP_VERSION__ },
    { label: "Server version", value: info?.server_version },
    { label: "서버명", value: info?.server_name },
    { label: "서버 IP", value: info?.server_ip },
    { label: "클라이언트 IP", value: info?.client_ip },
    { label: "X-Forwarded-For", value: info?.x_forwarded_for ?? "-" },
  ];

  return (
    <>
      <button
        type="button"
        className="info-sidebar-toggle"
        onClick={() => setOpen(true)}
        aria-label="버전/서버 정보 보기"
      >
        ℹ️
      </button>

      {open && (
        <>
          <div className="info-sidebar__overlay" onClick={() => setOpen(false)} />
          <div className="info-sidebar__panel">
            <h2 className="info-sidebar__title">버전 / 서버 정보</h2>
            {items.map((item) => (
              <div key={item.label} className="info-sidebar__item">
                <span className="info-sidebar__label">{item.label}</span>
                <span className="info-sidebar__value">{item.value ?? "불러오는 중..."}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </>
  );
}
