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