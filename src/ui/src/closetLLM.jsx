import React, { useState, useEffect } from "react";
import { supabase, useSession } from "./supabase";
import { authedFetch } from "./api";
import SignIn from "./SignIn";
import UploadPanel from "./UploadPanel";

import heartButton from "./assets/icon-heart-button.png";
import flowerButton from "./assets/icon-flower-button.png";
import starButton from "./assets/icon-star-button.png";

// Desktop wallpaper: cream, with black dots on a staggered lattice. Measured off
// the reference photo (cream #f6f3e0, ~5px dots, one every 34px on the diagonal)
// and redrawn in CSS rather than tiled from the file. The photo is 736×414 and
// the lattice repeats every 68px, which divides evenly into neither side — so
// tiling it would seam, and stretching it to fill a screen would smudge 5px dots.
// Two radial-gradient layers offset by half a cell give the same pattern, crisp
// at any size. Spread it with `...WALLPAPER`; it's several properties, not one.
const WALLPAPER = {
  backgroundColor: "#f6f3e0",
  backgroundImage:
    "radial-gradient(#191816 2.6px, transparent 2.7px), radial-gradient(#191816 2.6px, transparent 2.7px)",
  backgroundSize: "68px 68px",
  // the reference photo's own offsets, so no dot is sliced in half at the edges
  backgroundPosition: "10px 1px, 44px 35px",
};

// Font used for the little pixel-style labels.
const MONO = "Silkscreen, monospace";

// A palette is labelled by its own filename with the extension dropped:
// "sage_palette.jpeg" → "sage_palette". Every palette arrives by upload now, so
// nothing about it can be known ahead of time — the name the user gave the file
// is the only name there is. (This replaces the old NAMES table.)
const stem = (file) => file.replace(/\.[^.]+$/, "");

// ── Layout geometry ─────────────────────────────────────────────────────────
// Every size here is an ideal, not a promise: each one gets measured against the
// live viewport below, so the same desktop works on a phone and on a 27" monitor.
const MENU_BAR = 26;                 // the top bar owns this strip; windows start under it
const GUTTER = 16;                   // breathing room between a window and the screen edge
const MAIN_W = 600, MAIN_H = 800;    // the main window at full size
const MAIN_MIN = 280;                // it stops shrinking here; below this the screen wins
// A pop-up as measured, before PROFILE_SCALE. 190 is the upload pop-ups' height
// with no results listed yet (title bar + heading + drop zone + button). Only
// used to park and clamp the windows, so it's an estimate, not a hard size.
const POPUP_W = 312, POPUP_H = 190;
const PROFILE_SCALE = 1.3;           // how much bigger the pop-ups draw than they measure
// Under this window width, a 150px sidebar leaves the stage too cramped to show
// a garment grid — so the palette list flips from a left column to a top strip.
const NARROW = 460;
// Clear space the desktop icons need to the right of the main window.
const ICON_COL = 200;
// Both desktop icons draw in the same square box, so their labels line up even
// though the heart is wider than it is tall and the flower is round.
const ICON_SIZE = 72;

const clamp = (n, lo, hi) => Math.min(Math.max(n, lo), Math.max(lo, hi));

// One resize listener for the whole app. Every responsive decision below reads
// from this, so no component has to register its own.
function useViewport() {
  const [vp, setVp] = useState(() => ({ w: window.innerWidth, h: window.innerHeight }));
  useEffect(() => {
    const onResize = () => setVp({ w: window.innerWidth, h: window.innerHeight });
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  return vp;
}

// The main window shrinks to fit a small screen but never grows past its design
// size — a huge monitor shouldn't mean one absurdly large Finder window.
const mainSize = (vp) => ({
  w: clamp(vp.w - GUTTER * 2, MAIN_MIN, MAIN_W),
  h: clamp(vp.h - MENU_BAR - GUTTER * 2, 240, MAIN_H),
});

// Dead centre of the usable area (everything below the menu bar). Where the main
// window opens on a first visit, and where it stays until you drag it.
const centre = (vp, size) => ({
  x: Math.max(0, (vp.w - size.w) / 2),
  y: MENU_BAR + Math.max(0, (vp.h - MENU_BAR - size.h) / 2),
});

// Keeps a window fully on screen. The desktop clips overflow, so without this a
// drag — or someone shrinking their browser — could strand a window off-canvas
// with no title bar left to grab it by.
const onScreen = (at, size, vp) => ({
  x: clamp(at.x, 0, vp.w - size.w),
  y: clamp(at.y, MENU_BAR, vp.h - size.h),
});

// Shown while the closet is loading, or if the API can't be reached. Borrows the
// same dotted wallpaper + pixel font as the desktop so the wait doesn't look broken.
function StatusScreen({ text }) {
  return (
    <div style={{
      width: "100%", height: "100%", display: "grid", placeItems: "center",
      ...WALLPAPER,
      fontFamily: MONO, fontSize: 12, letterSpacing: ".08em", color: "#9a5b7c",
    }}>
      {text}
    </div>
  );
}

// Stands in for the matches document if the API answers 404. The current API
// never does (an empty closet is a 200 with empty sections), so this only fires
// against a server that predates that change — harmless to keep.
const EMPTY_CLOSET = { garments: {}, palettes: {}, meta: {} };

const hitCount = (pal) => pal.groups.reduce((n, g) => n + g.hits.length, 0);

// The empty-state buttons. Same look wherever they appear.
const emptyBtn = {
  fontFamily: MONO, fontSize: 9, letterSpacing: ".08em", color: "#7a3557", cursor: "pointer",
  padding: "6px 12px", borderRadius: 5, border: "1px solid #d3699f",
  background: "linear-gradient(#ffe6f4,#ffd0e9)",
};

// A small colored square + its hex code (each palette has two main colors).
function Swatch({ hex }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span style={{ width: 16, height: 16, borderRadius: 3, background: hex, border: "1px solid rgba(0,0,0,.15)" }} />
      <span style={{ fontFamily: MONO, fontSize: 8, color: "#943d6c", letterSpacing: ".04em" }}>{hex}</span>
    </div>
  );
}

// One garment thumbnail. `src` is the signed bucket link the API minted; if it's
// missing or fails to load (a link that expired, a bucket object that never got
// written), draw a swatch in the colour the garment was read as instead of a
// broken-image icon, so the piece is still visible. `caption` is whatever the
// caller wants under it: the match score in the palette view, the hex code in
// the closet grid.
function Garment({ name, src, hex, size, caption }) {
  const [broken, setBroken] = useState(false);
  // a fresh fetch mints fresh links, so a new src gets a fresh chance to load
  useEffect(() => setBroken(false), [src]);
  const tip = `${name} · ${caption}`;
  return (
    <div style={{ display: "grid", justifyItems: "center", gap: 3 }}>
      {broken || !src ? (
        <div title={tip} style={{
          width: size, height: size, borderRadius: 4, border: "1px solid #e79cc4",
          background: hex ?? "#f0d0e0", display: "grid", placeItems: "center", overflow: "hidden",
          fontFamily: MONO, fontSize: 6, color: "#fff", textAlign: "center", padding: 2, boxSizing: "border-box",
        }}>{name}</div>
      ) : (
        <img
          src={src}
          alt={name}
          title={tip}
          draggable={false}
          onError={() => setBroken(true)}
          style={{ width: size, height: size, objectFit: "cover", borderRadius: 4, border: "1px solid #e79cc4", background: "#fff", display: "block" }}
        />
      )}
      <span style={{ fontFamily: MONO, fontSize: 7, color: "#c0468f" }}>{caption}</span>
    </div>
  );
}

// Everything that matched one of the palette's colors: the swatch, then the
// garments themselves. The number under each garment is the color distance —
// lower is closer, and the list already reads best-first.
function MatchRow({ group, size }) {
  return (
    <div style={{ display: "grid", gap: 5, justifyItems: "start" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <Swatch hex={group.hex} />
        <span style={{ fontFamily: MONO, fontSize: 7, color: "#b07b9a" }}>
          {group.hits.length ? `${group.hits.length} MATCH${group.hits.length > 1 ? "ES" : ""}` : "NO MATCH"}
        </span>
      </div>
      {group.hits.length > 0 && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {group.hits.map((hit) => (
            <Garment key={hit.garment} name={hit.garment} src={hit.src} hex={hit.hex} size={size} caption={hit.score.toFixed(1)} />
          ))}
        </div>
      )}
    </div>
  );
}

// The body of the "my clothing" pop-up: every garment in the closet, matched or
// not, with the colour it was read as underneath. It reads data.garments straight
// off the matches document — the API lists the whole closet there, not just the
// pieces that scored — so no second fetch is needed.
function ClosetGrid({ garments, onUpload }) {
  const pieces = Object.entries(garments); // [[name, { colors, src }], …]
  if (pieces.length === 0) {
    return (
      <div style={{ display: "grid", justifyItems: "center", gap: 10, padding: 14, textAlign: "center" }}>
        <div style={{ fontFamily: MONO, fontSize: 9.5, letterSpacing: ".06em", color: "#6d3352" }}>NOTHING IN HERE YET</div>
        <div style={{ fontSize: 11, color: "#7a4a63", lineHeight: 1.5, maxWidth: 220 }}>
          Upload some clothing and it shows up here.
        </div>
        <button onClick={onUpload} style={emptyBtn}>UPLOAD CLOTHING</button>
      </div>
    );
  }
  return (
    <div style={{ display: "grid", gap: 8, padding: 10 }}>
      <div style={{ fontFamily: MONO, fontSize: 8.5, letterSpacing: ".08em", color: "#6d3352" }}>
        {`YOUR CLOSET · ${pieces.length} PIECE${pieces.length > 1 ? "S" : ""}`}
      </div>
      <div className="closet" style={{
        display: "grid", gridTemplateColumns: "repeat(auto-fill, 56px)", justifyContent: "center",
        gap: 8, maxHeight: 236, overflowY: "auto", paddingBottom: 2,
      }}>
        {pieces.map(([name, garment]) => (
          <Garment key={name} name={name} src={garment.src} hex={garment.colors[0]} size={56} caption={garment.colors[0]} />
        ))}
      </div>
    </div>
  );
}

export default function ClosetLLM() {
  // ── Who's signed in ──
  // undefined while the saved session is being read, null when signed out,
  // an object when signed in. Everything below waits on this.
  const session = useSession();

  // ── Data: fetched from the API once someone is signed in ──
  const [data, setData] = useState(null);   // the matches document, once it arrives
  const [error, setError] = useState(null); // a message if the fetch failed
  // Bumped after a successful upload. It's in the effect's deps below, so a new
  // number means "fetch /color-matches again" and the new photos show up.
  const [reloadKey, setReloadKey] = useState(0);
  const reload = () => setReloadKey((k) => k + 1);

  useEffect(() => {
    // Signed out (or still checking): drop whatever the last user was looking at,
    // so a sign-out followed by a different sign-in never flashes the old closet.
    if (!session) {
      setData(null);
      setError(null);
      return;
    }
    // authedFetch attaches `Authorization: Bearer <token>`. On a 401 it signs
    // out, which flips session to null and lands back on the sign-in window.
    authedFetch("/color-matches")
      .then((res) => {
        if (res.status === 404) return EMPTY_CLOSET;   // see EMPTY_CLOSET
        if (!res.ok) throw new Error(`server said ${res.status}`);
        return res.json();
      })
      .then(setData)                              // success → store it → re-render
      .catch((err) => setError(err.message));     // network/parse failure
    // Keyed on the user id, not the session object: the session is replaced
    // every time the token refreshes (hourly), and that shouldn't refetch.
    // reloadKey is the one deliberate way to force a refetch.
  }, [session?.user.id, reloadKey]);

  // ── State: the things that change while you use the app ──
  const vp = useViewport();                     // live screen size; drives all the sizing below
  const [picked, setPicked] = useState(null);   // which palette is chosen (its filename)
  const [menu, setMenu] = useState(null);       // which menu-bar menu is open ("File" or null)
  const [popupOpen, setPopupOpen] = useState(false); // pink pop-up: upload clothing
  const [inspoOpen, setInspoOpen] = useState(false); // lilac pop-up: upload color inspo
  const [mauveOpen, setMauveOpen] = useState(false); // mauve pop-up: my clothing
  // Where each window sits. `null` means "you haven't moved this one yet", so it
  // keeps whatever spot the current viewport works out — the main window dead
  // centre, the pop-ups tucked beside it — and re-centres itself on every resize.
  // The first drag writes a real {x,y}; from then on the window stays where you
  // put it, pulled back into view only if the screen gets too small to hold it.
  const [mainAt, setMainAt] = useState(null);
  const [popupAt, setPopupAt] = useState(null);
  const [inspoAt, setInspoAt] = useState(null);
  const [mauveAt, setMauveAt] = useState(null);

  // Early returns. They must stay BELOW every hook above: React needs the same
  // hooks to run in the same order on every render, so returning before one of
  // them would break the app the moment the session changes.
  if (session === undefined) return <StatusScreen text="CHECKING WHO YOU ARE…" />;
  if (!session) return <SignIn wallpaper={WALLPAPER} mono={MONO} />;
  // Until the fetch resolves, draw a status card and nothing else. These early
  // returns are why every data.* read below is safe — we never reach them unless
  // data exists.
  if (error) return <StatusScreen text={`COULD NOT LOAD: ${error}`} />;
  if (!data) return <StatusScreen text="LOADING YOUR CLOSET…" />;

  // ── Geometry: all derived from the live viewport, so a resize just re-runs it ──
  const size = mainSize(vp);
  const main = mainAt ? onScreen(mainAt, size, vp) : centre(vp, size);
  // Inside the window: palette list on the left, or across the top when tight.
  const narrow = size.w < NARROW;
  // The menu bar drops its decorative menus before they'd wrap onto two lines.
  const tightBar = vp.w < 520;
  // A pop-up's 1.3× blow-up would hang off a phone screen, so the scale eases
  // back until the painted width fits. transformOrigin is top-left, so the
  // painted box is what has to be positioned — hence popupSize, not POPUP_W.
  const scale = clamp((vp.w - GUTTER * 2) / POPUP_W, 0.8, PROFILE_SCALE);
  const popupSize = { w: POPUP_W * scale, h: POPUP_H * scale };
  // A pop-up's parking spot: beside the main window when the screen is wide
  // enough for both, otherwise centred over it, dropped by `offset` so the
  // pop-ups stack instead of landing on the same pixel.
  const parked = (offset) => {
    const beside = main.x + size.w + GUTTER;
    const room = beside + popupSize.w + GUTTER <= vp.w;
    return onScreen({ x: room ? beside : (vp.w - popupSize.w) / 2, y: main.y + offset }, popupSize, vp);
  };
  const step = popupSize.h + GUTTER;             // one pop-up's height plus a gap
  const popup = popupAt ? onScreen(popupAt, popupSize, vp) : parked(36);
  const inspo = inspoAt ? onScreen(inspoAt, popupSize, vp) : parked(36 + step);
  const mauve = mauveAt ? onScreen(mauveAt, popupSize, vp) : parked(36 + step * 2);

  // The icons live to the right of the main window. Once it's centred on a
  // narrow screen there's nowhere to put them — the File menu is the way in.
  const showIcons = vp.w - (main.x + size.w) >= ICON_COL;

  // The document is keyed by filename and points at garments by name. The UI
  // wants a sorted list of ready-to-draw objects, so that join happens once here
  // instead of inside every component that renders a garment.
  const PALETTES = Object.entries(data.palettes)
    .map(([file, palette]) => ({
      id: file,
      name: stem(file),
      img: palette.src,
      colors: palette.colors,
      // one group per palette color — a palette asks two separate questions, so
      // the answers stay separate here too
      groups: palette.colors.map((hex) => ({
        hex,
        hits: (palette.matches[hex] ?? []).map((hit) => ({
          ...hit,
          src: data.garments[hit.garment]?.src,
          hex: data.garments[hit.garment]?.colors[0],   // the fallback swatch colour
        })),
      })),
    }))
    // numeric-aware, so "palette_2" lands before "palette_10" (a plain string
    // sort would not do that); otherwise alphabetical by filename
    .sort((a, b) => a.id.localeCompare(b.id, undefined, { numeric: true }))
    // the little number on each card is just its place in the list
    .map((pal, i) => ({ ...pal, cue: String(i + 1).padStart(2, "0") }));

  const garmentCount = Object.keys(data.garments).length;
  const pickedPal = PALETTES.find((p) => p.id === picked);

  function open(pal) {
    setPicked(pal.id);
  }

  // One lookup table instead of if/else chains: each draggable window says where
  // it currently is, how big it draws, and how to move it. Adding a window means
  // adding one line here, not editing startDrag.
  const DRAGGABLE = {
    main:  { at: main,  box: size,      moveTo: setMainAt },
    popup: { at: popup, box: popupSize, moveTo: setPopupAt },
    inspo: { at: inspo, box: popupSize, moveTo: setInspoAt },
    mauve: { at: mauve, box: popupSize, moveTo: setMauveAt },
  };

  // Dragging: works for the big window and every pop-up.
  // Uses pointer events, so it works with a mouse OR a finger.
  function startDrag(target, e) {
    e.preventDefault();
    const { at, box, moveTo } = DRAGGABLE[target];
    const startX = e.clientX, startY = e.clientY;
    const baseX = at.x, baseY = at.y;
    const move = (ev) => {
      const to = { x: baseX + (ev.clientX - startX), y: baseY + (ev.clientY - startY) };
      moveTo(onScreen(to, box, vp));
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  return (
    // The whole desktop = the whole screen. The dotted wallpaper fills every
    // pixel, and the windows float on top of it. No bars, any screen size.
    <div style={{
      position: "relative", width: "100%", height: "100%", overflow: "hidden",
      ...WALLPAPER,
      fontFamily: "Verdana, Geneva, sans-serif", userSelect: "none",
    }}>
      {/* fonts + tiny animations + one hover rule */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Silkscreen:wght@400;700&display=swap');
        @keyframes blink {0%,60%{opacity:1}61%,100%{opacity:.25}}
        .close-btn:hover{background:linear-gradient(#fff,#ffcde8)}
        .menu-item{display:flex;align-items:center;gap:6px;padding:3px 18px 3px 8px;cursor:default;white-space:nowrap}
        .menu-item:hover{background:#3d7dd8;color:#fff}
        .menu-title:hover{background:rgba(0,0,0,.07);border-radius:3px}
        .pal-list::-webkit-scrollbar{width:8px;height:8px}
        .pal-list::-webkit-scrollbar-thumb{background:#e79cc4;border-radius:4px}
        .stage::-webkit-scrollbar{width:8px}
        .stage::-webkit-scrollbar-thumb{background:#e79cc4;border-radius:4px}
        .closet::-webkit-scrollbar{width:8px}
        .closet::-webkit-scrollbar-thumb{background:#c78cb0;border-radius:4px}
      `}</style>

      {/* Click-catcher: any click outside the open menu closes it. Rendered
          only while a menu is open, and sits under the menu bar in z-order. */}
      {menu && (
        <div onClick={() => setMenu(null)} style={{ position: "fixed", inset: 0, zIndex: 900 }} />
      )}

      {/* ── top menu bar (spans the full width of the screen) ── */}
      <div style={{
        position: "absolute", inset: "0 0 auto 0", height: MENU_BAR, display: "flex",
        alignItems: "center", gap: tightBar ? 10 : 18, padding: tightBar ? "0 8px" : "0 12px",
        background: "linear-gradient(#fdfdfd,#e6e6e6)", borderBottom: "1px solid #b9b9b9",
        fontSize: 11.5, color: "#1c1c1c", boxShadow: "0 1px 0 rgba(255,255,255,.7) inset",
        // lifted above the click-catcher while a menu is open, so the dropdown
        // (a child of this bar) isn't covered by it
        zIndex: menu ? 901 : 5,
      }}>
        <span style={{ fontSize: 13 }}>{""}</span>
        <span style={{ fontWeight: 700 }}>♥ closet LLM ♥</span>
        {(tightBar ? ["File"] : ["File", "Edit", "View", "History"]).map((m) => (
          m === "File" ? (
            <span key={m} style={{ position: "relative" }}>
              <span
                className="menu-title"
                onClick={() => setMenu((openMenu) => (openMenu === "File" ? null : "File"))}
                style={{
                  padding: "2px 6px", borderRadius: 3, cursor: "default",
                  background: menu === "File" ? "#3d7dd8" : "transparent",
                  color: menu === "File" ? "#fff" : "inherit",
                }}
              >{m}</span>

              {menu === "File" && (
                <div style={{
                  position: "absolute", top: 20, left: 0, minWidth: 176, padding: "4px 0",
                  background: "rgba(252,252,252,.98)", border: "1px solid #b0b0b0", borderRadius: 5,
                  boxShadow: "0 8px 20px rgba(0,0,0,.24)", fontSize: 11.5, color: "#1c1c1c",
                }}>
                  {[
                    { label: "upload clothing", isOpen: popupOpen, show: () => setPopupOpen(true) },
                    { label: "upload color inspo", isOpen: inspoOpen, show: () => setInspoOpen(true) },
                    { label: "my clothing", isOpen: mauveOpen, show: () => setMauveOpen(true) },
                    // signOut fires onAuthStateChange → session becomes null →
                    // the early return above swaps in the sign-in window
                    { label: "sign out", isOpen: false, show: () => supabase.auth.signOut() },
                  ].map((item) => (
                    <div key={item.label} className="menu-item" onClick={() => { item.show(); setMenu(null); }}>
                      {/* checkmark column: marks a window already on screen */}
                      <span style={{ width: 10, textAlign: "center" }}>{item.isOpen ? "✓" : ""}</span>
                      <span>{item.label}</span>
                    </div>
                  ))}
                </div>
              )}
            </span>
          ) : (
            <span key={m}>{m}</span>
          )
        ))}
        <span style={{ marginLeft: "auto", fontFamily: MONO, fontSize: 10, letterSpacing: ".06em", color: "#6a6a6a" }}>11:11 PM</span>
      </div>

      {/* ── desktop icons ── They sit to the right of the main window, so on a
          screen too narrow to fit both they'd end up underneath it. Hidden in
          that case; the File menu opens the same windows. ── */}
      {showIcons && (
      <div style={{ position: "absolute", top: 60, right: 44, display: "grid", gap: 34, justifyItems: "center", width: 150 }}>
        {[
          { label: "upload clothing", icon: heartButton, open: () => setPopupOpen(true) },
          // The star fills the same square as the others, but its points leave the
          // corners empty, so it reads smaller. scale bumps it up to match by eye.
          { label: "upload inspo", icon: starButton, scale: 1.75, open: () => setInspoOpen(true) },
          { label: "my clothing", icon: flowerButton, open: () => setMauveOpen(true) },
        ].map((f) => (
          <div key={f.label} onClick={f.open} style={{ display: "grid", justifyItems: "center", gap: 7, cursor: "pointer" }}>
            {/* drop-shadow, not boxShadow: it follows the button's cut-out
                silhouette instead of drawing a rectangle behind it */}
            <img src={f.icon} alt="" draggable={false} style={{
              width: ICON_SIZE, height: ICON_SIZE, objectFit: "contain", display: "block",
              filter: "drop-shadow(2px 3px 0 rgba(160,60,110,.25))",
              // transform, not a bigger width: grows the picture without moving the label or the gaps
              transform: f.scale ? `scale(${f.scale})` : undefined,
            }} />
            <span style={{ fontFamily: MONO, fontSize: 9.5, letterSpacing: ".08em", color: "#7a3557" }}>{f.label}</span>
          </div>
        ))}
      </div>
      )}

      {/* ── the big "Pick your character!" window (drag it by its title bar) ── */}
      <div style={{
        position: "absolute", left: main.x, top: main.y, width: size.w, height: size.h, borderRadius: 8,
        background: "linear-gradient(#fdeaf1,#f9d6e3)", border: "1px solid #d99cb8",
        boxShadow: "0 14px 34px rgba(150,90,120,.26)",
      }}>
        {/* title bar */}
        <div onPointerDown={(e) => startDrag("main", e)} style={{
          height: 30, display: "flex", alignItems: "center", padding: "0 10px", gap: 7,
          borderRadius: "7px 7px 0 0",
          background: "repeating-linear-gradient(#fff4f8,#fff4f8 1px,#f7dbe7 1px,#f7dbe7 2px)",
          borderBottom: "1px solid #dfa4be", cursor: "grab", touchAction: "none",
        }}>
          <span style={{ width: 12, height: 12, borderRadius: "50%", background: "radial-gradient(circle at 34% 30%,#ffb0a6,#e0574a)", border: "1px solid #b7473c" }} />
          <span style={{ width: 12, height: 12, borderRadius: "50%", background: "radial-gradient(circle at 34% 30%,#ffe08a,#e0a92f)", border: "1px solid #b98d25" }} />
          <span style={{ width: 12, height: 12, borderRadius: "50%", background: "radial-gradient(circle at 34% 30%,#b9f39a,#5fbd45)", border: "1px solid #4d9a38" }} />
          <span style={{ margin: "0 auto", fontSize: 12, fontWeight: 700, color: "#4a2b38" }}></span>
          <span style={{ width: 14, height: 11, borderRadius: 3, border: "1px solid #dfa4be", background: "#fdeef4" }} />
        </div>

        {/* body: left list of palettes + center stage. 30px is the title bar,
            the only chrome above it. */}
        <div style={{
          display: "flex", flexDirection: narrow ? "column" : "row",
          height: "calc(100% - 30px)", padding: 12, boxSizing: "border-box",
        }}>
          {/* The palette photos, scrolling along whichever axis they're stacked
              on: a column down the left normally, a strip across the top once
              the window is too narrow to spare 150px of it. */}
          <div className="pal-list" style={{
            display: "flex", gap: 10,
            ...(narrow
              ? { flexDirection: "row", height: 128, flex: "none", overflowX: "auto", overflowY: "hidden", paddingBottom: 4 }
              : { flexDirection: "column", width: 150, overflowY: "auto", overflowX: "hidden", paddingRight: 4 }),
          }}>
            {PALETTES.map((pal) => {
              const active = picked === pal.id;
              return (
                <div key={pal.id} onClick={() => open(pal)} style={{
                  padding: 6, borderRadius: 5, cursor: "pointer", boxSizing: "border-box",
                  flex: "none", width: narrow ? 112 : "100%",
                  border: "1px solid " + (active ? "#e0398a" : "#eabfd2"),
                  background: active ? "linear-gradient(#fff2f9,#ffdcef)" : "linear-gradient(#fffdfe,#fdf1f6)",
                  boxShadow: active ? "0 0 0 2px rgba(224,57,138,.22)" : "0 1px 2px rgba(0,0,0,.08)",
                }}>
                  <img src={pal.img} alt={pal.name} draggable={false} style={{ width: "100%", height: narrow ? 70 : 84, objectFit: "cover", borderRadius: 4, display: "block", background: "#fff" }} />
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 5, gap: 4 }}>
                    {/* a long filename gets cut with an ellipsis rather than wrapping the card */}
                    <span title={pal.name} style={{ fontFamily: MONO, fontSize: 7, letterSpacing: ".02em", color: "#8a4467", lineHeight: 1.2, textTransform: "uppercase", minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{pal.name}</span>
                    <span style={{ fontFamily: MONO, fontSize: 7.5, color: "#d0459a", flex: "none" }}>{pal.cue}</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* center stage */}
          <div className="stage" style={{
            flex: 1, minWidth: 0, minHeight: 0,
            marginLeft: narrow ? 0 : 12, marginTop: narrow ? 12 : 0,
            background: "#fff", border: "1px solid #edc4d7",
            boxShadow: "0 1px 3px rgba(0,0,0,.12) inset", display: "grid",
            placeItems: pickedPal ? "start center" : "center", position: "relative", overflowY: "auto",
          }}>
            {PALETTES.length === 0 ? (
              garmentCount === 0 ? (
                // nothing at all yet
                <div style={{ display: "grid", justifyItems: "center", gap: 14, textAlign: "center", padding: 24 }}>
                  <div style={{ fontFamily: MONO, fontSize: 11, color: "#9a5b7c", letterSpacing: ".05em" }}>YOUR CLOSET IS EMPTY</div>
                  <div style={{ fontSize: 11, color: "#8a6b78", maxWidth: 250, lineHeight: 1.55 }}>
                    Upload some clothes and a color palette or two, and your matches show up here.
                  </div>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "center" }}>
                    <button onClick={() => setPopupOpen(true)} style={emptyBtn}>UPLOAD CLOTHING</button>
                    <button onClick={() => setInspoOpen(true)} style={emptyBtn}>UPLOAD COLOR INSPO</button>
                  </div>
                </div>
              ) : (
                // clothes are in, but there's nothing to match them against yet
                <div style={{ display: "grid", justifyItems: "center", gap: 14, textAlign: "center", padding: 24 }}>
                  <div style={{ fontFamily: MONO, fontSize: 11, color: "#9a5b7c", letterSpacing: ".05em" }}>NO COLOR INSPO YET</div>
                  <div style={{ fontSize: 11, color: "#8a6b78", maxWidth: 250, lineHeight: 1.55 }}>
                    {`${garmentCount} piece${garmentCount > 1 ? "s" : ""} in your closet and nothing to match them against. Upload a color palette or two.`}
                  </div>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "center" }}>
                    <button onClick={() => setInspoOpen(true)} style={emptyBtn}>UPLOAD COLOR INSPO</button>
                    <button onClick={() => setMauveOpen(true)} style={emptyBtn}>MY CLOTHING</button>
                  </div>
                </div>
              )
            ) : !pickedPal ? (
              <div style={{ position: "relative", display: "grid", justifyItems: "center", gap: 14, textAlign: "center", padding: 24 }}>
                <div style={{ width: narrow ? 132 : 190, height: narrow ? 132 : 190, border: "2px dashed #d9a8c4", borderRadius: 10, display: "grid", placeItems: "center", background: "repeating-linear-gradient(-45deg,#fdf3f9 0 8px,#ffffff 8px 16px)" }}>
                  <span style={{ fontFamily: MONO, fontSize: 9, color: "#c58bab", letterSpacing: ".08em" }}>EMPTY STAGE</span>
                </div>
                <div style={{ fontFamily: MONO, fontSize: 11, color: "#9a5b7c", letterSpacing: ".05em" }}>NO PALETTE SELECTED</div>
                <div style={{ fontSize: 11, color: "#8a6b78", maxWidth: 250, lineHeight: 1.55 }}>
                  {`Click a palette ${narrow ? "above" : "on the left"}.`} Its matches open here.
                  <span style={{ animation: "blink 1.1s steps(1) infinite", color: "#d0459a" }}>&nbsp;{"▦"}</span>
                </div>
              </div>
            ) : (
              <div style={{ position: "relative", display: "grid", justifyItems: "center", gap: 14, padding: 20, width: "100%", boxSizing: "border-box" }}>
                <img src={pickedPal.img} alt={pickedPal.name} draggable={false} style={{ width: narrow ? 150 : 220, height: narrow ? 150 : 220, objectFit: "contain", borderRadius: 6, background: "#fff" }} />
                <div style={{ fontFamily: MONO, fontSize: 15, letterSpacing: ".06em", color: "#4a2b38", textAlign: "center", textTransform: "uppercase", maxWidth: "100%", overflowWrap: "anywhere" }}>{pickedPal.name}</div>

                {/* what this palette pulls out of the closet */}
                <div style={{ width: "100%", borderTop: "1px dashed #e3c3d5", paddingTop: 12, display: "grid", gap: 12 }}>
                  <div style={{ fontFamily: MONO, fontSize: 8.5, letterSpacing: ".08em", color: "#c0468f" }}>
                    {`YOUR CLOSET · ${hitCount(pickedPal)} MATCHES`}
                  </div>
                  {/* the swatches always draw, so the palette's own colors are
                      visible even when nothing in the closet is close to them */}
                  {pickedPal.groups.map((group) => <MatchRow key={group.hex} group={group} size={narrow ? 56 : 70} />)}
                  {garmentCount === 0 ? (
                    <div style={{ display: "grid", gap: 8, justifyItems: "start" }}>
                      <div style={{ fontSize: 11, color: "#8a6b78", lineHeight: 1.55 }}>
                        Nothing in your closet yet. Upload some clothing and the matches show up here.
                      </div>
                      <button onClick={() => setPopupOpen(true)} style={emptyBtn}>UPLOAD CLOTHING</button>
                    </div>
                  ) : hitCount(pickedPal) === 0 ? (
                    <div style={{ fontSize: 11, color: "#8a6b78", lineHeight: 1.55 }}>
                      Nothing you own scores under {data.meta.cutoff} against these colors.
                    </div>
                  ) : null}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── pink pop-up: upload clothing → POST /upload-garments ── */}
      {popupOpen && (
        <div style={{
          position: "absolute", left: popup.x, top: popup.y, width: POPUP_W, zIndex: 45,
          borderRadius: 7, background: "linear-gradient(#ffe6f4,#ffd0e9)", border: "1px solid #d3699f",
          boxShadow: "0 12px 28px rgba(150,60,110,.3)",
          transform: `scale(${scale})`, transformOrigin: "top left",
        }}>
          {/* pop-up title bar (drag here) */}
          <div onPointerDown={(e) => startDrag("popup", e)} style={{
            height: 26, display: "flex", alignItems: "center", gap: 6, padding: "0 7px",
            borderRadius: "6px 6px 0 0", background: "linear-gradient(#ffa8d6,#f279b8)",
            borderBottom: "1px solid #d05e97", cursor: "grab", touchAction: "none",
          }}>
            <span style={{ marginLeft: "auto", display: "flex", gap: 4 }}>
              <span style={{ width: 14, height: 13, border: "1px solid #c95d93", borderRadius: 2, background: "#ffd3ea", display: "grid", placeItems: "center", fontSize: 8, color: "#8a3462" }}>{"–"}</span>
              <span style={{ width: 14, height: 13, border: "1px solid #c95d93", borderRadius: 2, background: "#ffd3ea", display: "grid", placeItems: "center", fontSize: 8, color: "#8a3462" }}>{"□"}</span>
              <span onClick={(e) => { e.stopPropagation(); setPopupOpen(false); }} onPointerDown={(e) => e.stopPropagation()} style={{ width: 14, height: 13, border: "1px solid #c95d93", borderRadius: 2, background: "#ffbcdd", display: "grid", placeItems: "center", fontSize: 9, color: "#7d1f45", cursor: "pointer" }}>{"×"}</span>
            </span>
          </div>

          {/* a successful upload refetches /color-matches, so the piece lands in
              the "my clothing" window and in any palette it scores against */}
          <UploadPanel kind="garment" mono={MONO} onUploaded={reload} />
        </div>
      )}

      {/* ── lilac pop-up: upload color inspo → POST /upload-palettes ── */}
      {inspoOpen && (
        <div style={{
          position: "absolute", left: inspo.x, top: inspo.y, width: POPUP_W, zIndex: 46,
          borderRadius: 7, background: "linear-gradient(#f3e9ff,#e6d6fa)", border: "1px solid #9f7cc6",
          boxShadow: "0 12px 28px rgba(100,60,150,.3)",
          transform: `scale(${scale})`, transformOrigin: "top left",
        }}>
          {/* title bar (drag here) */}
          <div onPointerDown={(e) => startDrag("inspo", e)} style={{
            height: 26, display: "flex", alignItems: "center", gap: 6, padding: "0 7px",
            borderRadius: "6px 6px 0 0", background: "linear-gradient(#d9bdfa,#b98ee8)",
            borderBottom: "1px solid #9a72c9", cursor: "grab", touchAction: "none",
          }}>
            <span style={{ marginLeft: "auto", display: "flex", gap: 4 }}>
              <span style={{ width: 14, height: 13, border: "1px solid #9a72c9", borderRadius: 2, background: "#eadcff", display: "grid", placeItems: "center", fontSize: 8, color: "#5b3488" }}>{"–"}</span>
              <span style={{ width: 14, height: 13, border: "1px solid #9a72c9", borderRadius: 2, background: "#eadcff", display: "grid", placeItems: "center", fontSize: 8, color: "#5b3488" }}>{"□"}</span>
              <span onClick={(e) => { e.stopPropagation(); setInspoOpen(false); }} onPointerDown={(e) => e.stopPropagation()} style={{ width: 14, height: 13, border: "1px solid #9a72c9", borderRadius: 2, background: "#dcc6fb", display: "grid", placeItems: "center", fontSize: 9, color: "#4e2a7a", cursor: "pointer" }}>{"×"}</span>
            </span>
          </div>

          {/* If UploadPanel hands back the filename of the last upload, that
              palette is selected as soon as the refetch lands, so the inspo you
              just added is the one on stage. With no name, it just refetches. */}
          <UploadPanel kind="palette" mono={MONO} onUploaded={(name) => { if (name) setPicked(name); reload(); }} />
        </div>
      )}

      {/* ── mauve pop-up: my clothing (opened by the round desktop icon) ── */}
      {mauveOpen && (
        <div style={{
          position: "absolute", left: mauve.x, top: mauve.y, width: POPUP_W, zIndex: 47,
          borderRadius: 7, background: "linear-gradient(#f7dcea,#e8c1d9)", border: "1px solid #a76e8f",
          boxShadow: "0 12px 28px rgba(120,60,100,.3)",
          transform: `scale(${scale})`, transformOrigin: "top left",
        }}>
          {/* title bar (drag here) */}
          <div onPointerDown={(e) => startDrag("mauve", e)} style={{
            height: 26, display: "flex", alignItems: "center", gap: 6, padding: "0 7px",
            borderRadius: "6px 6px 0 0", background: "linear-gradient(#ddaac8,#c78cb0)",
            borderBottom: "1px solid #a76e8f", cursor: "grab", touchAction: "none",
          }}>
            <span style={{ marginLeft: "auto", display: "flex", gap: 4 }}>
              <span style={{ width: 14, height: 13, border: "1px solid #a0688a", borderRadius: 2, background: "#eed2e1", display: "grid", placeItems: "center", fontSize: 8, color: "#6d3352" }}>{"–"}</span>
              <span style={{ width: 14, height: 13, border: "1px solid #a0688a", borderRadius: 2, background: "#eed2e1", display: "grid", placeItems: "center", fontSize: 8, color: "#6d3352" }}>{"□"}</span>
              <span onClick={(e) => { e.stopPropagation(); setMauveOpen(false); }} onPointerDown={(e) => e.stopPropagation()} style={{ width: 14, height: 13, border: "1px solid #a0688a", borderRadius: 2, background: "#e2bcd4", display: "grid", placeItems: "center", fontSize: 9, color: "#57243d", cursor: "pointer" }}>{"×"}</span>
            </span>
          </div>

          {/* the closet itself: every garment the API returned, hex underneath */}
          <ClosetGrid garments={data.garments} onUpload={() => setPopupOpen(true)} />
        </div>
      )}

    </div>
  );
}