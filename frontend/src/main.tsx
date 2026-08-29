import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
window.addEventListener("error", (e) => {
  const el = document.createElement("pre");
  el.id = "boot-error";
  el.textContent = "BOOT ERROR: " + e.message + "\n" + String(e.error?.stack ?? "").slice(0, 800);
  document.body.appendChild(el);
});
import App from "./App";
import "./app.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
