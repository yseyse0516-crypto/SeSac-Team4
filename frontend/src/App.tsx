import { useState } from "react";
import "./styles/tokens.css";
import { RouteSearchPage } from "./screens/routing/RouteSearchPage";
import { AuthPage } from "./screens/auth/AuthPage";
import { CommunityPage } from "./screens/community/CommunityPage";
import { AccountPage } from "./screens/account/AccountPage";
import { InfoSidebar } from "./components/common/BuildInfoBadge";
import { clearAllSandboxData } from "./utils/sandboxAccount";

// 실험용(ui-sandbox): react-router 없이 화면 전환을 로컬 state로만 처리.
// 닉네임은 화면 표시용 state일 뿐 어디에도 저장하지 않는다 (새로고침하면 초기화).
type Screen = "auth" | "routing" | "community" | "account";

const NAV_ITEMS: { key: Screen; label: string }[] = [
  { key: "routing", label: "경로 찾기" },
  { key: "community", label: "커뮤니티" },
  { key: "account", label: "계정" },
];

// 로그인이 필요한 화면 (그 외 화면은 비회원도 그대로 이용 가능).
const AUTH_REQUIRED_SCREENS: Screen[] = ["community", "account"];

function App() {
  const [screen, setScreen] = useState<Screen>("routing");
  const [nickname, setNickname] = useState("익명");
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  // 로그인이 필요해서 auth 화면으로 보냈을 때, 로그인 성공 후 원래 가려던 화면으로 되돌아가기 위한 값.
  const [pendingScreen, setPendingScreen] = useState<Screen>("community");

  function handleNavClick(target: Screen) {
    if (AUTH_REQUIRED_SCREENS.includes(target) && !isLoggedIn) {
      setPendingScreen(target);
      setScreen("auth");
      return;
    }
    setScreen(target);
  }

  function handleLogout() {
    setIsLoggedIn(false);
    setNickname("익명");
    setScreen("routing");
  }

  function handleWithdraw() {
    clearAllSandboxData();
    setIsLoggedIn(false);
    setNickname("익명");
    setScreen("routing");
  }

  // 로그인 없이 community/account 화면에 직접 들어온 경우를 대비한 방어적 가드.
  const effectiveScreen: Screen =
    AUTH_REQUIRED_SCREENS.includes(screen) && !isLoggedIn ? "auth" : screen;

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)" }}>
      <InfoSidebar />

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
            onClick={() => handleNavClick(item.key)}
            style={{
              background: effectiveScreen === item.key ? "var(--primary)" : "var(--surface-muted)",
              color: effectiveScreen === item.key ? "white" : "var(--text)",
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

      {effectiveScreen === "auth" && (
        <AuthPage
          reason={pendingScreen === "account" ? "account" : "community"}
          onLoggedIn={(name) => {
            setNickname(name);
            setIsLoggedIn(true);
            setScreen(pendingScreen);
          }}
        />
      )}
      {effectiveScreen === "routing" && <RouteSearchPage />}
      {effectiveScreen === "community" && <CommunityPage defaultAuthor={nickname} />}
      {effectiveScreen === "account" && (
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
