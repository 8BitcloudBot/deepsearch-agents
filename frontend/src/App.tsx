function App() {
  const apiBaseUrl =
    import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

  return (
    <main>
      <h1>Agent Engineering Research Copilot</h1>
      <p>
        Phase <strong>0</strong> — Foundation
      </p>
      <p>
        API: <code>{apiBaseUrl}</code>
      </p>
    </main>
  );
}

export default App;
