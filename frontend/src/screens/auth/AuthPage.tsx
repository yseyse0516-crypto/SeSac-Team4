import { useState } from "react";
import "./AuthPage.css";

// ⚠️ 실험용(ui-sandbox) 화면. 실제 백엔드 계정 생성/인증(POST /api/v1/auth/register, /login) 없이
// localStorage에 계정 목록을 흉내내는 프론트 전용 mock이다. 로그인 화면이 기본이고, 계정이 없으면
// 하단 "회원가입" 링크로 넘어가 가입한 뒤 "로그인으로 돌아가기"로 다시 로그인하는 흐름.

interface Account {
  username: string;
  password: string;
  nickname: string;
}

const ACCOUNTS_KEY = "tangtang_sandbox_accounts";

// 닉네임: 한글로 8자 미만. 비밀번호: 영어+숫자를 모두 포함해서 8~20자(그 외 문자 불가).
const NICKNAME_PATTERN = /^[가-힣]{1,7}$/;
const PASSWORD_PATTERN = /^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,20}$/;

function loadAccounts(): Account[] {
  try {
    const raw = localStorage.getItem(ACCOUNTS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveAccounts(accounts: Account[]): void {
  localStorage.setItem(ACCOUNTS_KEY, JSON.stringify(accounts));
}

type AuthMode = "login" | "signup";

interface AuthPageProps {
  onLoggedIn: (nickname: string) => void;
  reason?: "community" | "account";
}

const REASON_SUBTITLE: Record<"login" | "signup", Record<"community" | "account", string>> = {
  login: {
    community: "커뮤니티는 로그인해야 이용할 수 있어요.",
    account: "계정 정보를 보려면 로그인해 주세요.",
  },
  signup: {
    community: "가입하고 로그인해서 커뮤니티를 이용해보세요.",
    account: "가입하고 로그인해서 계정을 만들어보세요.",
  },
};

export function AuthPage({ onLoggedIn, reason = "community" }: AuthPageProps) {
  const [mode, setMode] = useState<AuthMode>("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [nickname, setNickname] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  function switchMode(next: AuthMode) {
    setMode(next);
    setPassword("");
    setNickname("");
    setError(null);
    setNotice(null);
  }

  function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    const account = loadAccounts().find((a) => a.username === username.trim());
    if (!account || account.password !== password) {
      setError("아이디 또는 비밀번호가 올바르지 않습니다.");
      return;
    }
    setError(null);
    onLoggedIn(account.nickname);
  }

  function handleSignup(e: React.FormEvent) {
    e.preventDefault();
    if (!username.trim() || !password || !nickname.trim()) {
      setError("모든 항목을 입력해 주세요.");
      return;
    }
    if (!NICKNAME_PATTERN.test(nickname.trim())) {
      setError("닉네임은 한글로 8자 미만이어야 합니다.");
      return;
    }
    if (!PASSWORD_PATTERN.test(password)) {
      setError("비밀번호는 영어+숫자를 모두 포함해 8~20자여야 합니다.");
      return;
    }
    const accounts = loadAccounts();
    if (accounts.some((a) => a.username === username.trim())) {
      setError("이미 사용 중인 아이디입니다.");
      return;
    }
    saveAccounts([...accounts, { username: username.trim(), password, nickname: nickname.trim() }]);

    setMode("login");
    setPassword("");
    setNickname("");
    setError(null);
    setNotice("회원가입이 완료됐어요. 로그인해 주세요.");
  }

  return (
    <div className="auth-page">
      <div className="auth-page__card">
        <h1 className="auth-page__title">텅텅 {mode === "login" ? "로그인" : "회원가입"}</h1>
        <p className="auth-page__subtitle">{REASON_SUBTITLE[mode][reason]}</p>

        {notice && <p className="auth-page__notice">{notice}</p>}

        {mode === "login" ? (
          <form onSubmit={handleLogin}>
            <label className="auth-page__field">
              <span>아이디</span>
              <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="아이디" />
            </label>

            <label className="auth-page__field">
              <span>비밀번호</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="비밀번호"
              />
            </label>

            {error && <p className="auth-page__error">{error}</p>}

            <button type="submit" className="auth-page__submit">
              로그인
            </button>

            <button type="button" className="auth-page__link" onClick={() => switchMode("signup")}>
              회원가입
            </button>
          </form>
        ) : (
          <form onSubmit={handleSignup}>
            <label className="auth-page__field">
              <span>아이디</span>
              <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="아이디" />
            </label>

            <label className="auth-page__field">
              <span>닉네임</span>
              <input
                value={nickname}
                onChange={(e) => setNickname(e.target.value)}
                placeholder="한글 8자 미만"
                maxLength={7}
              />
            </label>

            <label className="auth-page__field">
              <span>비밀번호</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="영어+숫자 조합 8~20자"
                maxLength={20}
              />
            </label>

            {error && <p className="auth-page__error">{error}</p>}

            <button type="submit" className="auth-page__submit">
              가입하기
            </button>

            <button type="button" className="auth-page__link" onClick={() => switchMode("login")}>
              로그인으로 돌아가기
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
