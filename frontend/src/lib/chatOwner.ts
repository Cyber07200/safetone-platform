const KEY = "safetone.chatOwner";
let memory: string | null = null;

/** Random per-browser token that owns this browser's chats. The server stores only its HMAC. */
export function chatOwner(): string {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved && /^[A-Za-z0-9_-]{32,128}$/.test(saved)) return saved;
  } catch { /* storage blocked (private mode): fall back to a per-tab token below */ }
  if (!memory) {
    const bytes = crypto.getRandomValues(new Uint8Array(32));
    memory = btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }
  try { localStorage.setItem(KEY, memory); } catch { /* see above: chats then live only in this tab */ }
  return memory;
}
