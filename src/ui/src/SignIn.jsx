import React, { useState } from "react";
import { supabase } from "./supabase";

// The sign-in window. Drawn as one more window on the same dotted desktop, so
// signing in feels like part of the app rather than a detour to a login page.
// WALLPAPER and MONO are passed in from closetLLM.jsx so the look can't drift.
export default function SignIn({ wallpaper, mono }) {
  const [mode, setMode] = useState("in");        // "in" = sign in, "up" = create account
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");    // second copy of the password, create-account only
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null);  // { kind: "error" | "info", text }

  const creating = mode === "up";

  async function submit(e) {
    e.preventDefault();                          // a real form, so Enter submits and password managers work

    // Caught here, before anything is sent to Supabase.
    if (creating && password !== confirm) {
      setMessage({ kind: "error", text: "passwords must match" });
      return;
    }

    setBusy(true);
    setMessage(null);

    const { data, error } = creating
      ? await supabase.auth.signUp({ email, password })
      : await supabase.auth.signInWithPassword({ email, password });

    setBusy(false);
    if (error) {
      setMessage({ kind: "error", text: error.message });
      return;
    }
    // Success with a session: onAuthStateChange flips the app over on its own.
    // Sign-up without one means email confirmation is switched on in Supabase.
    if (creating && !data.session) {
      setMessage({ kind: "info", text: "Account created. Check your email for the confirmation link, then sign in." });
      setMode("in");
      setConfirm("");
    }
  }

  const field = {
    width: "100%", boxSizing: "border-box", padding: "7px 9px",
    border: "1px solid #dfa4be", borderRadius: 4, background: "#fffafc",
    fontFamily: "Verdana, Geneva, sans-serif", fontSize: 12, color: "#4a2b38",
  };
  const label = { display: "grid", gap: 4, fontFamily: mono, fontSize: 8.5, letterSpacing: ".06em", color: "#8a4467" };

  return (
    <div style={{
      width: "100%", height: "100%", display: "grid", placeItems: "center",
      padding: 16, boxSizing: "border-box", ...wallpaper,
      fontFamily: "Verdana, Geneva, sans-serif",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Silkscreen:wght@400;700&display=swap');
        .signin-field:focus{outline:2px solid #e0398a;outline-offset:1px}
        .signin-btn:focus-visible,.signin-link:focus-visible{outline:2px solid #e0398a;outline-offset:2px}
        .signin-btn:hover:not(:disabled){background:linear-gradient(#fff2f9,#ffc9e6)}
      `}</style>

      <div style={{
        width: "100%", maxWidth: 320, borderRadius: 8,
        background: "linear-gradient(#fdeaf1,#f9d6e3)", border: "1px solid #d99cb8",
        boxShadow: "0 14px 34px rgba(150,90,120,.26)",
      }}>
        {/* title bar — same stripes and traffic lights as the main window */}
        <div style={{
          height: 30, display: "flex", alignItems: "center", gap: 7, padding: "0 10px",
          borderRadius: "7px 7px 0 0", borderBottom: "1px solid #dfa4be",
          background: "repeating-linear-gradient(#fff4f8,#fff4f8 1px,#f7dbe7 1px,#f7dbe7 2px)",
        }}>
          <span style={{ width: 12, height: 12, borderRadius: "50%", background: "radial-gradient(circle at 34% 30%,#ffb0a6,#e0574a)", border: "1px solid #b7473c" }} />
          <span style={{ width: 12, height: 12, borderRadius: "50%", background: "radial-gradient(circle at 34% 30%,#ffe08a,#e0a92f)", border: "1px solid #b98d25" }} />
          <span style={{ width: 12, height: 12, borderRadius: "50%", background: "radial-gradient(circle at 34% 30%,#b9f39a,#5fbd45)", border: "1px solid #4d9a38" }} />
          <span style={{ margin: "0 auto", fontSize: 12, fontWeight: 700, color: "#4a2b38" }}>♥ closet LLM ♥</span>
          <span style={{ width: 42 }} />
        </div>

        <form onSubmit={submit} style={{ display: "grid", gap: 12, padding: 18 }}>
          <div style={{ fontFamily: mono, fontSize: 13, letterSpacing: ".05em", color: "#4a2b38" }}>
            {creating ? "make your digital closet today!" : "open your digital closet"}
          </div>

          <label style={label}>
            email
            <input className="signin-field" style={field} type="email" autoComplete="email"
              required value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>

          <label style={label}>
            password
            <input className="signin-field" style={field} type="password"
              autoComplete={creating ? "new-password" : "current-password"}
              required minLength={6} value={password} onChange={(e) => setPassword(e.target.value)} />
          </label>

          {creating && (
            <label style={label}>
              confirm password
              <input className="signin-field" style={field} type="password" autoComplete="new-password"
                required value={confirm} onChange={(e) => setConfirm(e.target.value)} />
            </label>
          )}

          {message && (
            <div role={message.kind === "error" ? "alert" : "status"} style={{
              fontSize: 11, lineHeight: 1.5,
              color: message.kind === "error" ? "#a3264f" : "#6b3f52",
            }}>{message.text}</div>
          )}

          <button className="signin-btn" type="submit" disabled={busy} style={{
            padding: "8px 0", borderRadius: 11, border: "1px solid #dfa4be",
            background: "linear-gradient(#fffafc,#f7d9e6)", color: "#6b3f52",
            fontFamily: mono, fontSize: 10, letterSpacing: ".06em",
            cursor: busy ? "wait" : "pointer", opacity: busy ? 0.6 : 1,
          }}>
            {busy ? "one sec…" : creating ? "create account" : "sign in"}
          </button>

          <button className="signin-link" type="button"
            onClick={() => { setMode(creating ? "in" : "up"); setMessage(null); setConfirm(""); }}
            style={{ background: "none", border: "none", padding: 0, cursor: "pointer",
              fontFamily: mono, fontSize: 9, letterSpacing: ".06em",
              color: "#c0468f", textDecoration: "underline", justifySelf: "center" }}>
            {creating ? "I already have an account" : "New here? Create an account"}
          </button>
        </form>
      </div>
    </div>
  );
}