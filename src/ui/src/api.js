import { supabase } from "./supabase";

// fetch() with the signed-in user's token attached. Use this for every call to
// the FastAPI server — the read endpoints and the uploads alike.
//
// getSession() hands back a fresh token (it refreshes an expired one first), so
// callers never deal with expiry. A 401 means the server rejected the token
// anyway — revoked, or the JWT secret changed — so sign out, which drops the
// app back to the sign-in window instead of showing a broken screen.
export async function authedFetch(path, options = {}) {
  const { data } = await supabase.auth.getSession();
  const headers = new Headers(options.headers);
  if (data.session) {
    headers.set("Authorization", `Bearer ${data.session.access_token}`);
  }

  const res = await fetch(path, { ...options, headers });
  if (res.status === 401) {
    await supabase.auth.signOut();
  }
  return res;
}

// ── session cookie ──────────────────────────────────────────────────────────
// The app proves who it is with the Authorization header above. The browser's
// address bar can't add headers, so it needs a second way in: an httpOnly
// cookie the server sets and the browser then sends by itself. These two calls
// keep that cookie in step with Supabase — set it whenever there's a session
// (sign-in, page load, token refresh), clear it on sign-out. Both are
// fire-and-forget: the app itself never depends on the cookie.

function setSessionCookie(session) {
  return fetch("/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ access_token: session.access_token }),
  }).catch(() => {});
}

function clearSessionCookie() {
  return fetch("/session", { method: "DELETE" }).catch(() => {});
}

// Fires with INITIAL_SESSION (page load), SIGNED_IN, TOKEN_REFRESHED and
// SIGNED_OUT. Registered once, when this module loads.
supabase.auth.onAuthStateChange((event, session) => {
  if (session) setSessionCookie(session);
  else if (event === "SIGNED_OUT") clearSessionCookie();
});