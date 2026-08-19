import { useEffect, useState } from "react";
import { fetchVersionInfo, type VersionInfo } from "../../api/system";
import "./BuildInfoBadge.css";

// vite.config.ts의 define에서 frontend/package.json의 version을 빌드 시점에 주입.
declare const __APP_VERSION__: string;

export function VersionTopBar() {
  const [apiVersion, setApiVersion] = useState<string | null>(null);

  useEffect(() => {
    fetchVersionInfo()
      .then((info) => setApiVersion(info.server_version))
      .catch(() => setApiVersion(null));
  }, []);

  return (
    <div className="version-topbar">
      <span className="version-topbar__pill">
        Front {__APP_VERSION__} · API {apiVersion ?? "오프라인"}
      </span>
    </div>
  );
}

export function ServerInfoBar() {
  const [info, setInfo] = useState<VersionInfo | null>(null);

  useEffect(() => {
    fetchVersionInfo()
      .then(setInfo)
      .catch(() => setInfo(null));
  }, []);

  const items = [
    { label: "서버 IP", value: info?.server_ip },
    { label: "서버명", value: info?.server_name },
    { label: "클라이언트 IP", value: info?.client_ip },
    { label: "X-Forwarded-For", value: info?.x_forwarded_for ?? "-" },
  ];

  return (
    <div className="server-info-bar">
      {items.map((item) => (
        <div key={item.label} className="server-info-bar__item">
          <span className="server-info-bar__label">{item.label}</span>
          <span className="server-info-bar__value">{item.value ?? "-"}</span>
        </div>
      ))}
    </div>
  );
}
