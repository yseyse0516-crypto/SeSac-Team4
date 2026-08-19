// docs/api-contracts/system.md 에서 정의한 GET /api/system/version 응답 형태.

export interface VersionInfo {
  server_version: string;
  server_name: string;
  server_ip: string;
  client_ip: string;
  x_forwarded_for: string | null;
}

export async function fetchVersionInfo(): Promise<VersionInfo> {
  const res = await fetch("/api/system/version");
  if (!res.ok) {
    throw new Error(`version fetch failed: ${res.status}`);
  }
  return res.json();
}
