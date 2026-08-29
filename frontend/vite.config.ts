import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true, // 双栈监听：避免仅 ::1 时 IPv4 客户端（如内嵌浏览器）连不上
    // dev 代理：前端与 API 同源，避免 localhost/127.0.0.1 跨站导致
    // SameSite=Lax 会话 cookie 不随 fetch 发送（审阅实测 401 根因）
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true, ws: true },
    },
  },
});
