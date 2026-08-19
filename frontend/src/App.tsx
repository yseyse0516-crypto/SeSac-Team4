import "./styles/tokens.css";
import { RouteSearchPage } from "./screens/routing/RouteSearchPage";
import { VersionTopBar, ServerInfoBar } from "./components/common/BuildInfoBadge";

function App() {
  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)", paddingTop: 44, paddingBottom: 64 }}>
      <VersionTopBar />
      <RouteSearchPage />
      <ServerInfoBar />
    </div>
  );
}

export default App;
