import { useEffect, useState } from "react";
import { createClient } from "@supabase/supabase-js";

// Both values come from src/ui/.env. Only VITE_-prefixed variables reach the
// browser, which is the point: the publishable key is meant to be public, and
// nothing without the prefix (like the secret key) can leak into this bundle.
const url = import.meta.env.VITE_SUPABASE_URL;
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY;

if (!url || !key) {
  // Fail at load with the fix in the message, not later as a mystery 401.
  throw new Error(
    "Missing VITE_SUPABASE_URL or VITE_SUPABASE_PUBLISHABLE_KEY. Add both to src/ui/.env and restart `npm run dev`."
  );
}

// One client for the whole app. It keeps the session in localStorage and
// refreshes the access token in the background before it expires.
export const supabase = createClient(url, key);

// The current session, kept in sync with sign-in, sign-out and token refresh.
//   undefined → still checking (first render, before localStorage is read)
//   null      → signed out
//   object    → signed in; session.access_token is the bearer token
export function useSession() {
  const [session, setSession] = useState(undefined);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = supabase.auth.onAuthStateChange((_event, next) => setSession(next));
    return () => data.subscription.unsubscribe();
  }, []);

  return session;
}