import { useState } from "react";
import "./AccountPage.css";

// ⚠️ 실험용(ui-sandbox) 화면. CLAUDE.md 1차 MVP는 비회원 서비스라 실제 계정 시스템은 없다 —
// AuthPage와 마찬가지로 화면 전환용 프론트 mock이고, 서버에 저장되는 계정 정보는 없다.

interface AccountPageProps {
  nickname: string;
  onChangeNickname: (name: string) => void;
  onLogout: () => void;
  onWithdraw: () => void;
}

export function AccountPage({ nickname, onChangeNickname, onLogout, onWithdraw }: AccountPageProps) {
  const [editing, setEditing] = useState(false);
  const [draftName, setDraftName] = useState(nickname);
  // 네이티브 confirm()은 일부 임베디드 브라우저(웹뷰)에서 닫힌 뒤 포커스/키보드 입력이
  // 깨지는 경우가 있어서, 자체 확인 모달로 대체했다.
  const [confirmingWithdraw, setConfirmingWithdraw] = useState(false);

  function handleSaveNickname() {
    const trimmed = draftName.trim();
    if (trimmed) onChangeNickname(trimmed);
    setEditing(false);
  }

  return (
    <div className="account-page">
      <div className="account-page__card">
        <div className="account-page__nickname-row">
          <span className="account-page__nickname">{nickname}</span>
          {!editing && (
            <button type="button" className="account-page__edit-btn" onClick={() => setEditing(true)}>
              닉네임 변경
            </button>
          )}
        </div>
        <span className="account-page__sub">비회원 데모 계정 (이 브라우저에만 임시 저장됨)</span>

        {editing && (
          <div className="account-page__nickname-edit">
            <input value={draftName} onChange={(e) => setDraftName(e.target.value)} autoFocus />
            <button type="button" onClick={handleSaveNickname}>
              저장
            </button>
          </div>
        )}
      </div>

      <button type="button" className="account-page__action-btn account-page__logout" onClick={onLogout}>
        로그아웃
      </button>
      <button
        type="button"
        className="account-page__action-btn account-page__withdraw"
        onClick={() => setConfirmingWithdraw(true)}
      >
        회원탈퇴
      </button>

      {confirmingWithdraw && (
        <div className="account-page__confirm-overlay" onClick={() => setConfirmingWithdraw(false)}>
          <div className="account-page__confirm-card" onClick={(e) => e.stopPropagation()}>
            <p className="account-page__confirm-message">
              정말 회원을 탈퇴하시겠어요? 이 브라우저에 저장된 커뮤니티 글/쿠폰/검색 기록이 모두 삭제됩니다.
            </p>
            <div className="account-page__confirm-actions">
              <button type="button" onClick={() => setConfirmingWithdraw(false)}>
                취소
              </button>
              <button
                type="button"
                className="account-page__confirm-danger"
                onClick={() => {
                  setConfirmingWithdraw(false);
                  onWithdraw();
                }}
              >
                탈퇴
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
