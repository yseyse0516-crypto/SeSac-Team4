import { readFileSync } from "fs";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const pkg = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf-8"));

// server.host: true -> 0.0.0.0 바인딩. 같은 Wi-Fi의 안드로이드/아이폰에서
// `npm run dev` 실행 시 터미널에 뜨는 Network URL(http://<PC IP>:5173)로 바로 접속 가능.
// server.proxy: 프론트가 어떤 host(PC의 localhost든, 폰이 접속한 LAN IP든)로 열려도
// /api/* 요청은 Vite 서버 프로세스가 있는 PC 기준으로 localhost:8000(백엔드)에 그대로 전달된다.
export default defineConfig({
  plugins: [react()],
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
