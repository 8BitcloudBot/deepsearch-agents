import { ConversationWorkspace, LoginScreen } from "./conversation/ConversationWorkspace";
import { useConversationApp } from "./conversation/useConversationApp";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export default function App() {
  const state = useConversationApp(API_BASE_URL);
  if (state.booting) return <main className="login-shell"><p role="status">正在连接研究服务…</p></main>;
  if (!state.user) return <LoginScreen onLogin={state.login} error={state.loginError} />;
  return <ConversationWorkspace state={state} />;
}
