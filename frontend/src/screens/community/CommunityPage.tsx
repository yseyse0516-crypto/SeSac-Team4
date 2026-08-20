import { useState } from "react";
import {
  createPost,
  deletePost,
  getPosts,
  updatePost,
  type CommunityPost,
  type CongestionRating,
} from "../../utils/communityPosts";
import { CouponBanner } from "../../components/common/CouponBanner";
import "./CommunityPage.css";

// 회의록: "자유게시판 + 경로 혼잡도 리뷰/후기 복합적으로" — congestionRating이 있으면 경로 리뷰,
// 없으면 그냥 자유게시판 글로 취급한다. CRUD(작성/조회/수정/삭제) 전부 localStorage로 흉내낸 샌드박스 목업.

const RATING_LABEL: Record<CongestionRating, { label: string; color: string }> = {
  calm: { label: "여유", color: "var(--level-calm)" },
  normal: { label: "보통", color: "var(--level-normal)" },
  busy: { label: "혼잡", color: "var(--level-busy)" },
  packed: { label: "매우 혼잡", color: "var(--level-packed)" },
};

interface CommunityPageProps {
  defaultAuthor: string;
}

interface DraftState {
  id?: string;
  author: string;
  title: string;
  content: string;
  congestionRating: CongestionRating | "";
}

function emptyDraft(author: string): DraftState {
  return { author, title: "", content: "", congestionRating: "" };
}

export function CommunityPage({ defaultAuthor }: CommunityPageProps) {
  const [posts, setPosts] = useState<CommunityPost[]>(getPosts());
  const [draft, setDraft] = useState<DraftState | null>(null);

  function refresh() {
    setPosts(getPosts());
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!draft || !draft.title.trim() || !draft.content.trim()) return;

    const payload = {
      author: draft.author.trim() || "익명",
      title: draft.title.trim(),
      content: draft.content.trim(),
      congestionRating: draft.congestionRating || undefined,
    };

    if (draft.id) {
      updatePost(draft.id, payload);
    } else {
      createPost(payload);
    }
    setDraft(null);
    refresh();
  }

  function handleDelete(id: string) {
    if (!confirm("이 글을 삭제할까요?")) return;
    deletePost(id);
    refresh();
  }

  return (
    <div className="community-page">
      <CouponBanner />

      <div className="community-page__header">
        <h1 className="community-page__title">커뮤니티</h1>
        {!draft && (
          <button
            type="button"
            className="community-page__write-btn"
            onClick={() => setDraft(emptyDraft(defaultAuthor))}
          >
            글쓰기
          </button>
        )}
      </div>

      {draft && (
        <form className="community-page__form" onSubmit={handleSubmit}>
          <input
            value={draft.author}
            onChange={(e) => setDraft({ ...draft, author: e.target.value })}
            placeholder="작성자"
          />
          <input
            value={draft.title}
            onChange={(e) => setDraft({ ...draft, title: e.target.value })}
            placeholder="제목"
          />
          <textarea
            value={draft.content}
            onChange={(e) => setDraft({ ...draft, content: e.target.value })}
            placeholder="자유롭게 글을 쓰거나, 특정 경로/시간대의 혼잡도 후기를 남겨보세요."
          />
          <select
            value={draft.congestionRating}
            onChange={(e) => setDraft({ ...draft, congestionRating: e.target.value as CongestionRating | "" })}
          >
            <option value="">일반 글 (혼잡도 리뷰 아님)</option>
            <option value="calm">경로 리뷰 · 여유</option>
            <option value="normal">경로 리뷰 · 보통</option>
            <option value="busy">경로 리뷰 · 혼잡</option>
            <option value="packed">경로 리뷰 · 매우 혼잡</option>
          </select>
          <div className="community-page__form-actions">
            <button type="button" onClick={() => setDraft(null)}>
              취소
            </button>
            <button type="submit">{draft.id ? "수정 완료" : "등록"}</button>
          </div>
        </form>
      )}

      {posts.length === 0 && !draft && <p className="community-page__empty">아직 글이 없어요.</p>}

      {posts.map((post) => (
        <div key={post.id} className="community-page__post">
          <div className="community-page__post-header">
            <span className="community-page__post-title">{post.title}</span>
            {post.congestionRating && (
              <span
                className="community-page__badge"
                style={{ background: RATING_LABEL[post.congestionRating].color }}
              >
                {RATING_LABEL[post.congestionRating].label}
              </span>
            )}
          </div>
          <div className="community-page__post-meta">
            {post.author} · {new Date(post.createdAt).toLocaleString("ko-KR")}
          </div>
          <div className="community-page__post-content">{post.content}</div>
          <div className="community-page__post-actions">
            <button
              type="button"
              onClick={() =>
                setDraft({
                  id: post.id,
                  author: post.author,
                  title: post.title,
                  content: post.content,
                  congestionRating: post.congestionRating ?? "",
                })
              }
            >
              수정
            </button>
            <button type="button" onClick={() => handleDelete(post.id)}>
              삭제
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
