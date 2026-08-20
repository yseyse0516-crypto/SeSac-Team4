// backend/app/schemas/system.py(2026-08-20, zer0 브랜치) 기준 GET /api/v1/system/meta 응답 형태.

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export interface VersionInfo {
  front_version: string;
  server_version: string;
  server_name: string;
  server_ip: string;
  client_ip: string;
  x_forwarded_for: string | null;
}

export async function fetchVersionInfo(): Promise<VersionInfo> {
  const res = await fetch(`${API_BASE_URL}/api/v1/system/meta`);
  if (!res.ok) {
    throw new Error(`version fetch failed: ${res.status}`);
  }
  return res.json();
}
