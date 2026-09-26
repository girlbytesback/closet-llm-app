import React, { useRef, useState } from "react";
import { authedFetch } from "./api";

// The body of an upload pop-up. Same field, button and message styling as
// SignIn.jsx, so the windows read as one app. Used twice — once per pop-up —
// and `kind` decides which endpoint it hits and what it says:
//   <UploadPanel kind="garment" ... />   → POST /upload-garments
//   <UploadPanel kind="palette" ... />   → POST /upload-palettes
//
// One POST per photo: the API takes a single `file` per request, so picking
// five photos means five requests, sent one after another. Sequential on
// purpose — each one is a Claude call, and firing them all at once would just
// race each other into the daily limit.
//
// onUploaded(lastName) runs once at the end if at least one photo made it in,
// with the filename of the last one that did, so the parent can refetch
// /color-matches and put the new thing on stage.

const KINDS = {
  garment: { route: "/upload-garments", title: "add to your closet" },
  palette: { route: "/upload-palettes", title: "add color inspo" },
};
const ACCEPT = ".jpg,.jpeg,.png"; // keep in sync with img_types in config.py

// FastAPI puts HTTPException text in `detail`. The status codes are the ones
// ingest() raises; anything else falls back to whatever the server said.
function explain(status, detail) {
  if (status === 409) return "you already have a photo with this name";
  if (status === 415) return "only .jpg and .png photos work";
  if (status === 429) return "daily upload limit reached, try again tomorrow";
  if (status === 502) return "couldn't read any colors from this one";
  return typeof detail === "string" ? detail : `upload failed (${status})`;
}

export default function UploadPanel({ kind, mono, onUploaded }) {
  const { route, title } = KINDS[kind];
  const [files, setFiles] = useState([]);        // File objects waiting to go
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [results, setResults] = useState([]);    // [{ name, colors } | { name, error }]
  const inputRef = useRef(null);

  function pick(list) {
    setFiles(Array.from(list));
    setResults([]);
  }

  async function submit(e) {
    e.preventDefault();
    if (!files.length || busy) return;
    setBusy(true);
    setResults([]);

    let anyOk = false;
    let lastOk = null;                 // filename of the last successful upload
    for (const file of files) {
      // multipart/form-data. The key "file" has to match the parameter name in
      // `def upload_garment(file: UploadFile = File(), ...)`. Don't set a
      // Content-Type header: the browser adds it, boundary included.
      const body = new FormData();
      body.append("file", file);

      let result;
      try {
        const res = await authedFetch(route, { method: "POST", body });
        const json = await res.json().catch(() => ({}));
        if (res.ok) {
          anyOk = true;
          lastOk = json.name;
          result = { name: json.name, colors: json.colors };
        } else {
          result = { name: file.name, error: explain(res.status, json.detail) };
        }
      } catch {
        result = { name: file.name, error: "couldn't reach the server" };
      }
      setResults((prev) => [...prev, result]); // show each result as it lands
    }

    setBusy(false);
    setFiles([]);
    if (inputRef.current) inputRef.current.value = ""; // lets you re-pick the same file
    if (anyOk) onUploaded?.(lastOk);
  }

  // ── styles lifted from SignIn.jsx ──
  const label = { fontFamily: mono, fontSize: 8.5, letterSpacing: ".06em", color: "#8a4467" };
  const btn = {
    padding: "7px 0", borderRadius: 11, border: "1px solid #dfa4be",
    background: "linear-gradient(#fffafc,#f7d9e6)", color: "#6b3f52",
    fontFamily: mono, fontSize: 10, letterSpacing: ".06em",
  };

  return (
    <form onSubmit={submit} style={{ display: "grid", gap: 10, padding: 12 }}>
      <style>{`
        .upload-btn:focus-visible{outline:2px solid #e0398a;outline-offset:2px}
        .upload-btn:hover:not(:disabled){background:linear-gradient(#fff2f9,#ffc9e6)}
      `}</style>

      <div style={{ fontFamily: mono, fontSize: 11, letterSpacing: ".05em", color: "#4a2b38" }}>
        {title}
      </div>

      {/* Display only: says "choose photos" until something is picked, then
          shows what was picked. Not clickable — the button below opens the
          file browser. Dropping photos onto it still works. */}
      <div
        className="upload-box"
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); if (!busy) pick(e.dataTransfer.files); }}
        style={{
          display: "grid", placeItems: "center", minHeight: 70, padding: 10,
          boxSizing: "border-box", textAlign: "center", borderRadius: 4,
          border: `1px dashed ${dragging ? "#e0398a" : "#dfa4be"}`,
          background: dragging ? "#fff2f9" : "#fffafc",
        }}
      >
        {files.length ? (
          <span style={{ fontSize: 11, color: "#4a2b38", lineHeight: 1.45 }}>
            {files.length === 1 ? files[0].name : `${files.length} photos picked`}
          </span>
        ) : (
          <span style={label}>choose photos</span>
        )}
      </div>

      {/* the real file input, hidden; the "choose photos" button clicks it */}
      <input ref={inputRef} type="file" accept={ACCEPT} multiple disabled={busy}
        onChange={(e) => pick(e.target.files)} style={{ display: "none" }} />

      <button className="upload-btn" type="button" disabled={busy}
        onClick={() => inputRef.current?.click()} style={{
          ...btn,
          cursor: busy ? "default" : "pointer",
          opacity: busy ? 0.6 : 1,
        }}>
        choose photos
      </button>

      <button className="upload-btn" type="submit" disabled={busy || !files.length} style={{
        ...btn,
        cursor: busy ? "wait" : files.length ? "pointer" : "default",
        opacity: busy || !files.length ? 0.6 : 1,
      }}>
        {busy ? `uploading ${results.length + 1} of ${files.length}…` : "upload"}
      </button>

      {/* one line per photo: its colors if it worked, the reason if it didn't */}
      {results.length > 0 && (
        <div role="status" style={{ display: "grid", gap: 5, maxHeight: 110, overflowY: "auto" }}>
          {results.map((r, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 10, lineHeight: 1.4 }}>
              <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis",
                whiteSpace: "nowrap", color: r.error ? "#a3264f" : "#4a2b38" }}>
                {r.name}{r.error ? `: ${r.error}` : ""}
              </span>
              {r.colors?.map((hex) => (
                <span key={hex} title={hex} style={{ width: 12, height: 12, flex: "none",
                  borderRadius: 2, background: hex, border: "1px solid rgba(0,0,0,.18)" }} />
              ))}
            </div>
          ))}
        </div>
      )}
    </form>
  );
}