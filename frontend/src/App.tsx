import { useState } from "react";
import "./styles/tokens.css";
import { RouteSearchPage } from "./screens/routing/RouteSearchPage";
import { SignupPage } from "./screens/auth/SignupPage";
import { CommunityPage } from "./screens/community/CommunityPage";
import { AccountPage } from "./screens/account/AccountPage";
import { InfoSidebar } from "./components/common/BuildInfoBadge";
import { clearAllSandboxData } from "./utils/sandboxAccount";

// 실험용(ui-sandbox): react-router 없이 화면 전환을 로컬 state로만 처리.
// 닉네임은 화면 표시용 state일 뿐 어디에도 저장하지 않는다 (새로고침하면 초기화).
type Screen = "signup" | "routing" | "community" | "account";

const NAV_ITEMS: { key: Screen; label: string }[] = [
  { key: "routing", label: "경로 찾기" },
  { key: "community", label: "커뮤니티" },
  { key: "account", label: "계정" },
];

function App() {
  const [screen, setScreen] = useState<Screen>("signup");
  const [nickname, setNickname] = useState("익명");

  function handleLogout() {
    setScreen("signup");
  }

  function handleWithdraw() {
    clearAllSandboxData();
    setNickname("익명");
    setScreen("signup");
  }

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)" }}>
      <InfoSidebar />

      {screen !== "signup" && (
        <nav
          style={{
            display: "flex",
            gap: 8,
            padding: "12px 20px",
            borderBottom: "1px solid var(--border)",
            background: "var(--surface)",
          }}
        >
          {NAV_ITEMS.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => setScreen(item.key)}
              style={{
                background: screen === item.key ? "var(--primary)" : "var(--surface-muted)",
                color: screen === item.key ? "white" : "var(--text)",
                border: "none",
                borderRadius: "var(--radius-chip)",
                padding: "8px 16px",
                fontSize: 13,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              {item.label}
            </button>
          ))}
        </nav>
      )}

      {screen === "signup" && (
        <SignupPage
          onSignedUp={(name) => {
            setNickname(name);
            setScreen("routing");
          }}
        />
      )}
      {screen === "routing" && <RouteSearchPage />}
      {screen === "community" && <CommunityPage defaultAuthor={nickname} />}
      {screen === "account" && (
        <AccountPage
          nickname={nickname}
          onChangeNickname={setNickname}
          onLogout={handleLogout}
          onWithdraw={handleWithdraw}
        />
      )}
    </div>
  );
}

export default App;
