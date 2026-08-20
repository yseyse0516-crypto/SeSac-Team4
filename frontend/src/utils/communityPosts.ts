// ⚠️ 샌드박스 데모 전용 — 실제 게시판 CRUD는 backend.md에서 "이번 스프린트 범위 제외"로 합의된 기능이라
// 백엔드 API 없이 localStorage로만 흉내낸다. 실제로 가져가려면 백엔드 팀과 별도 논의 필요.

export type CongestionRating = "calm" | "normal" | "busy" | "packed";

export interface CommunityPost {
  id: string;
  author: string;
  title: string;
  content: string;
  congestionRating?: CongestionRating; // 있으면 "경로 리뷰", 없으면 자유게시판 글
  createdAt: number;
}

const STORAGE_KEY = "bium_sandbox_community_posts";

function readAll(): CommunityPost[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function writeAll(posts: CommunityPost[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(posts));
}

export function getPosts(): CommunityPost[] {
  return readAll().sort((a, b) => b.createdAt - a.createdAt);
}

export function createPost(input: Omit<CommunityPost, "id" | "createdAt">): CommunityPost {
  const post: CommunityPost = { ...input, id: `post-${Date.now()}`, createdAt: Date.now() };
  writeAll([...readAll(), post]);
  return post;
}

export function updatePost(id: string, patch: Partial<Omit<CommunityPost, "id" | "createdAt">>): void {
  writeAll(readAll().map((p) => (p.id === id ? { ...p, ...patch } : p)));
}

export function deletePost(id: string): void {
  writeAll(readAll().filter((p) => p.id !== id));
}
