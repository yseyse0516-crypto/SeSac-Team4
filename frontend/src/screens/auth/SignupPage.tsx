import { useState } from "react";
import "./SignupPage.css";

// ⚠️ 실험용(ui-sandbox) 화면. BIUM 1차 MVP는 비회원 서비스라 CLAUDE.md상 회원가입 기능이 없다 —
// 실제 백엔드 계정 생성도 없이, 입력만 받고 onSignedUp을 호출하는 프론트 전용 mock이다.

interface SignupPageProps {
  onSignedUp: (nickname: string) => void;
}

export function SignupPage({ onSignedUp }: SignupPageProps) {
  const [nickname, setNickname] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!nickname.trim() || !email.trim() || !password.trim()) {
      setError("모든 항목을 입력해 주세요.");
      return;
    }
    setError(null);
    onSignedUp(nickname.trim());
  }

  return (
    <div className="signup-page">
      <form className="signup-page__card" onSubmit={handleSubmit}>
        <h1 className="signup-page__title">BIUM 시작하기</h1>
        <p className="signup-page__subtitle">가입하고 바로 혼잡회피 경로를 찾아보세요.</p>

        <label className="signup-page__field">
          <span>닉네임</span>
          <input value={nickname} onChange={(e) => setNickname(e.target.value)} placeholder="닉네임" />
        </label>

        <label className="signup-page__field">
          <span>이메일</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
          />
        </label>

        <label className="signup-page__field">
          <span>비밀번호</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="비밀번호"
          />
        </label>

        {error && <p className="signup-page__error">{error}</p>}

        <button type="submit" className="signup-page__submit">
          가입하기
        </button>
      </form>
    </div>
  );
}
