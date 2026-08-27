import React, { useState, useRef } from "react";
import data from "./data/matches.json";

// Font used for the little pixel-style labels.
const MONO = "Silkscreen, monospace";

// The one palette detail matches.json doesn't carry, because it isn't a fact
// about the photo — it's display copy. Colors, image paths and matched garments
// all come out of the JSON, so nothing here can drift from data/colors.json.
// A palette with no entry falls back to its number.
const NAMES = {
  "color_palette_1.jpeg": "OLIVE & DENIM",
  "color_palette_2.jpeg": "OCHRE & BABY PINK",
  "color_palette_3.jpeg": "GREEN GLOW & BURGUNDY",
  "color_palette_4.jpeg": "BUTTER & PINK",
  "color_palette_5.jpeg": "MALACHITE & MERLOT",
  "color_palette_6.jpeg": "CORAL & DARK GREY",
  "color_palette_7.jpeg": "PLUM & SILVER",
  "color_palette_8.jpeg": "MAUVE & BLACK",
  "color_palette_9.jpeg": "OLIVE & MAGENTA",
  "color_palette_10.jpeg": "SAGE & PEACH",
  "color_palette_11.jpeg": "PUMPKIN & ROBIN EGG",
  "color_palette_12.jpeg": "PEAR & CHARCOAL",
  "color_palette_13.jpeg": "FAWN & MAGENTA",
  "color_palette_14.jpeg": "ESPRESSO & BABY BLUE",
  "color_palette_15.jpeg": "SKY BLUE & CHESTNUT",
  "color_palette_16.jpeg": "RED & AMETHYST",
  "color_palette_17.jpeg": "LILAC & BERRY",
  "color_palette_18.jpeg": "APPLE & PUMPKIN",
  "color_palette_19.jpeg": "AZURE & RASPBERRY",
};

// "color_palette_10.jpeg" -> 10. Sorting on the number keeps 2 before 10,
// which sorting on the filename wouldn't.
const number = (file) => Number(file.match(/\d+/)?.[0] ?? 0);

// matches.json is keyed by filename and points at garments by name. The UI
// wants a sorted list of ready-to-draw objects, so that join happens once here
// instead of inside every component that renders a garment.
const PALETTES = Object.entries(data.palettes)
  .map(([file, palette]) => ({
    id: file,
    cue: String(number(file)).padStart(2, "0"),
    name: NAMES[file] ?? `PALETTE ${String(number(file)).padStart(2, "0")}`,
    img: palette.src,
    colors: palette.colors,
    // one group per palette color — a palette asks two separate questions, so
    // the answers stay separate here too
    groups: palette.colors.map((hex) => ({
      hex,
      hits: (palette.matches[hex] ?? []).map((hit) => ({
        ...hit,
        src: data.garments[hit.garment]?.src,
      })),
    })),
  }))
  .sort((a, b) => number(a.id) - number(b.id));

// How much bigger the profile pop-ups draw than they measure.
const PROFILE_SCALE = 1.3;

const hitCount = (pal) => pal.groups.reduce((n, g) => n + g.hits.length, 0);

// A small colored square + its hex code (each palette has two main colors).
function Swatch({ hex }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span style={{ width: 16, height: 16, borderRadius: 3, background: hex, border: "1px solid rgba(0,0,0,.15)" }} />
      <span style={{ fontFamily: MONO, fontSize: 8, color: "#943d6c", letterSpacing: ".04em" }}>{hex}</span>
    </div>
  );
}

// One garment photo, straight out of the closet folder. The number under it is
// the color distance — lower is closer, so the list already reads best-first.
function Garment({ hit, size }) {
  return (
    <div style={{ display: "grid", justifyItems: "center", gap: 3 }}>
      <img
        src={hit.src}
        alt={hit.garment}
        title={`${hit.garment} · ${hit.score}`}
        draggable={false}
        style={{ width: size, height: size, objectFit: "cover", borderRadius: 4, border: "1px solid #e79cc4", background: "#fff", display: "block" }}
      />
      <span style={{ fontFamily: MONO, fontSize: 7, color: "#c0468f" }}>{hit.score.toFixed(1)}</span>
    </div>
  );
}

// Everything that matched one of the palette's colors: the swatch, then the
// garments themselves.
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
          {group.hits.map((hit) => <Garment key={hit.garment} hit={hit} size={size} />)}
        </div>
      )}
    </div>
  );
}

export default function PickYourCharacter() {
  // ── State: the things that change while you use the app ──
  const [picked, setPicked] = useState(null);        // which palette is chosen
  const [windows, setWindows] = useState([]);        // open profile pop-ups
  const [main, setMain] = useState({ x: 44, y: 74 }); // position of the big window
  const zc = useRef(40);                              // stacking counter for pop-ups

  const pickedPal = PALETTES.find((p) => p.id === picked);

  // Open (or re-focus) a palette's profile window, and mark it picked.
  function open(pal) {
    setPicked(pal.id);
    zc.current += 1;
    const z = zc.current;
    setWindows((ws) => {
      const existing = ws.find((w) => w.id === pal.id);
      if (existing) return ws.map((w) => (w.id === pal.id ? { ...w, z } : w));
      const n = ws.length;
      return [...ws, { id: pal.id, x: 668 + (n % 3) * 24, y: 110 + (n % 4) * 26, z }];
    });
  }

  function raise(id) {
    zc.current += 1;
    const z = zc.current;
    setWindows((ws) => ws.map((w) => (w.id === id ? { ...w, z } : w)));
  }

  function closeWin(id) {
    setWindows((ws) => ws.filter((w) => w.id !== id));
  }

  // Dragging: works for the big window ("main") and each pop-up.
  // Uses pointer events, so it works with a mouse OR a finger.
  function startDrag(target, e) {
    e.preventDefault();
    const base = target === "main" ? main : windows.find((w) => w.id === target);
    if (!base) return;
    if (target !== "main") raise(target);
    const startX = e.clientX, startY = e.clientY;
    const baseX = base.x, baseY = base.y;
    const move = (ev) => {
      const x = Math.max(0, baseX + (ev.clientX - startX));
      const y = Math.max(26, baseY + (ev.clientY - startY));
      if (target === "main") setMain({ x, y });
      else setWindows((ws) => ws.map((w) => (w.id === target ? { ...w, x, y } : w)));
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  return (
    // The whole desktop = the whole screen. The pink wallpaper fills every
    // pixel, and the windows float on top of it. No bars, any screen size.
    <div style={{
      position: "relative", width: "100%", height: "100vh", overflow: "hidden",
      background: "radial-gradient(120% 90% at 78% 12%, #ffc5e6 0%, #f7b8dd 26%, #e9c3d8 52%, #d9d3cf 74%, #cfd6cc 100%)",
      fontFamily: "Verdana, Geneva, sans-serif", userSelect: "none",
    }}>
      {/* fonts + tiny animations + one hover rule */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Silkscreen:wght@400;700&display=swap');
        html, body, #root { margin: 0; height: 100%; }
        @keyframes blink {0%,60%{opacity:1}61%,100%{opacity:.25}}
        @keyframes pop {from{transform:scale(${PROFILE_SCALE * 0.94});opacity:0}to{transform:scale(${PROFILE_SCALE});opacity:1}}
        .close-btn:hover{background:linear-gradient(#fff,#ffcde8)}
        .pal-list::-webkit-scrollbar{width:8px}
        .pal-list::-webkit-scrollbar-thumb{background:#e79cc4;border-radius:4px}
        .stage::-webkit-scrollbar{width:8px}
        .stage::-webkit-scrollbar-thumb{background:#e79cc4;border-radius:4px}
      `}</style>

      {/* ── top menu bar (spans the full width of the screen) ── */}
      <div style={{
        position: "absolute", inset: "0 0 auto 0", height: 26, display: "flex",
        alignItems: "center", gap: 18, padding: "0 12px",
        background: "linear-gradient(#fdfdfd,#e6e6e6)", borderBottom: "1px solid #b9b9b9",
        fontSize: 11.5, color: "#1c1c1c", boxShadow: "0 1px 0 rgba(255,255,255,.7) inset", zIndex: 5,
      }}>
        <span style={{ fontSize: 13 }}>{""}</span>
        <span style={{ fontWeight: 700 }}>Game</span>
        {["File", "Edit", "View", "History", "Bookmarks", "People", "Window", "Help"].map((m) => (
          <span key={m}>{m}</span>
        ))}
        <span style={{ marginLeft: "auto", fontFamily: MONO, fontSize: 10, letterSpacing: ".06em", color: "#6a6a6a" }}>11:11 PM</span>
      </div>

      {/* ── desktop icons (pinned to the top-right of the screen) ── */}
      <div style={{ position: "absolute", top: 60, right: 44, display: "grid", gap: 34, justifyItems: "center", width: 150 }}>
        {[
          { top: "linear-gradient(#ffd0ea,#f79ccb)", tab: "#ffd6ee" },
          { top: "linear-gradient(#ffdcef,#f2a9cf)", tab: "#ffe2f3" },
        ].map((f) => (
          <div key={f.label} style={{ display: "grid", justifyItems: "center", gap: 7 }}>
            <div style={{
              width: 76, height: 60, borderRadius: "4px 10px 6px 6px", background: f.top,
              border: "1px solid #d9679f", boxShadow: "2px 3px 0 rgba(160,60,110,.25)",
              display: "grid", placeItems: "center", position: "relative",
            }}>
              <div style={{ position: "absolute", top: -7, left: 6, width: 30, height: 9, borderRadius: "4px 4px 0 0", background: f.tab, border: "1px solid #d9679f", borderBottom: "none" }} />
              <span style={{ color: "#e0398a", fontSize: 26, textShadow: "0 1px 0 #fff" }}>{"♥"}</span>
            </div>
            <span style={{ fontFamily: MONO, fontSize: 9.5, letterSpacing: ".08em", color: "#7a3557" }}>{f.label}</span>
          </div>
        ))}
        <div style={{ display: "grid", justifyItems: "center", gap: 7 }}>
          <div style={{
            width: 70, height: 70, borderRadius: "50%",
            background: "radial-gradient(circle at 34% 30%,#fff 0 6%,#f6b9d6 24%,#d1728f 74%,#b45c7c 100%)",
            border: "1px solid #b45c7c", boxShadow: "2px 3px 0 rgba(160,60,110,.25)", display: "grid", placeItems: "center",
          }}>
            <span style={{ color: "#8e3f60", fontSize: 18 }}>{"♥"}</span>
          </div>
        </div>
      </div>

      {/* ── the big "Pick your character!" window (drag it by its title bar) ── */}
      <div style={{
        position: "absolute", left: main.x, top: main.y, width: 600, height: 800, borderRadius: 8,
        background: "linear-gradient(#f3f3f3,#e4e4e4)", border: "1px solid #9a9a9a",
        boxShadow: "0 14px 34px rgba(120,70,100,.28)",
      }}>
        {/* title bar */}
        <div onPointerDown={(e) => startDrag("main", e)} style={{
          height: 30, display: "flex", alignItems: "center", padding: "0 10px", gap: 7,
          borderRadius: "7px 7px 0 0",
          background: "repeating-linear-gradient(#f7f7f7,#f7f7f7 1px,#e2e2e2 1px,#e2e2e2 2px)",
          borderBottom: "1px solid #a8a8a8", cursor: "grab", touchAction: "none",
        }}>
          <span style={{ width: 12, height: 12, borderRadius: "50%", background: "radial-gradient(circle at 34% 30%,#ffb0a6,#e0574a)", border: "1px solid #b7473c" }} />
          <span style={{ width: 12, height: 12, borderRadius: "50%", background: "radial-gradient(circle at 34% 30%,#ffe08a,#e0a92f)", border: "1px solid #b98d25" }} />
          <span style={{ width: 12, height: 12, borderRadius: "50%", background: "radial-gradient(circle at 34% 30%,#b9f39a,#5fbd45)", border: "1px solid #4d9a38" }} />
          <span style={{ margin: "0 auto", fontSize: 12, fontWeight: 700, color: "#2a2a2a" }}></span>
          <span style={{ width: 14, height: 11, borderRadius: 3, border: "1px solid #9a9a9a", background: "#efefef" }} />
        </div>

        {/* finder-style toolbar */}
        <div style={{
          height: 52, display: "flex", alignItems: "flex-end", gap: 22, padding: "4px 14px 5px",
          background: "linear-gradient(#ededed,#dcdcdc)", borderBottom: "1px solid #b0b0b0",
        }}>
          <div style={{ display: "grid", justifyItems: "center", gap: 1, color: "#333" }}>
            <span style={{ width: 34, height: 22, borderRadius: 11, background: "linear-gradient(#fafafa,#d8d8d8)", border: "1px solid #a5a5a5", display: "grid", placeItems: "center", fontSize: 12 }}>{"←"}</span>
            <span style={{ fontSize: 9 }}>Back</span>
          </div>
          <div style={{ display: "grid", justifyItems: "center", gap: 1, color: "#333" }}>
            <span style={{ display: "flex", gap: 2, padding: 4, borderRadius: 5, background: "linear-gradient(#fafafa,#d8d8d8)", border: "1px solid #a5a5a5" }}>
              <span style={{ width: 8, height: 12, background: "#8a8a8a" }} />
              <span style={{ width: 8, height: 12, background: "#c4c4c4" }} />
              <span style={{ width: 8, height: 12, background: "#c4c4c4" }} />
            </span>
            <span style={{ fontSize: 9 }}>View</span>
          </div>
          <div style={{ display: "flex", gap: 20, marginLeft: 6 }}>
            <div style={{ display: "grid", justifyItems: "center", gap: 2, color: "#333" }}><span style={{ width: 24, height: 19, borderRadius: 3, background: "linear-gradient(#c9d6e6,#8fa4bd)", border: "1px solid #6c7f96" }} /><span style={{ fontSize: 9 }}>Computer</span></div>
            <div style={{ display: "grid", justifyItems: "center", gap: 2, color: "#333" }}><span style={{ width: 0, height: 0, borderLeft: "12px solid transparent", borderRight: "12px solid transparent", borderBottom: "12px solid #b98a5e" }} /><span style={{ fontSize: 9 }}>Home</span></div>
            <div style={{ display: "grid", justifyItems: "center", gap: 2, color: "#333" }}><span style={{ fontSize: 17, lineHeight: "14px", color: "#d8395f" }}>{"♥"}</span><span style={{ fontSize: 9 }}>Favorites</span></div>
            <div style={{ display: "grid", justifyItems: "center", gap: 2, color: "#333" }}><span style={{ fontFamily: MONO, fontSize: 15, lineHeight: "15px", color: "#3a3a3a" }}>A</span><span style={{ fontSize: 9 }}>Applications</span></div>
          </div>
        </div>

        {/* body: left list of palettes + center stage */}
        <div style={{ display: "flex", height: "calc(100% - 82px)", padding: 12, boxSizing: "border-box" }}>
          {/* left: the palette photos (scrolls if there are many) */}
          <div className="pal-list" style={{ width: 150, display: "flex", flexDirection: "column", gap: 10, overflowY: "auto", overflowX: "hidden", paddingRight: 4 }}>
            {PALETTES.map((pal) => {
              const active = picked === pal.id;
              return (
                <div key={pal.id} onClick={() => open(pal)} style={{
                  padding: 6, borderRadius: 5, cursor: "pointer", boxSizing: "border-box", flex: "none",
                  border: "1px solid " + (active ? "#e0398a" : "#d3d3d3"),
                  background: active ? "linear-gradient(#fff2f9,#ffdcef)" : "linear-gradient(#ffffff,#f4f4f4)",
                  boxShadow: active ? "0 0 0 2px rgba(224,57,138,.22)" : "0 1px 2px rgba(0,0,0,.08)",
                }}>
                  <img src={pal.img} alt={pal.name} draggable={false} style={{ width: "100%", height: 84, objectFit: "cover", borderRadius: 4, display: "block" }} />
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 5, gap: 4 }}>
                    <span style={{ fontFamily: MONO, fontSize: 7, letterSpacing: ".02em", color: "#8a4467", lineHeight: 1.2 }}>{pal.name}</span>
                    <span style={{ fontFamily: MONO, fontSize: 7.5, color: "#d0459a", flex: "none" }}>{pal.cue}</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* center stage */}
          <div className="stage" style={{
            flex: 1, marginLeft: 12, background: "#fff", border: "1px solid #c9c9c9",
            boxShadow: "0 1px 3px rgba(0,0,0,.12) inset", display: "grid",
            placeItems: pickedPal ? "start center" : "center", position: "relative", overflowY: "auto",
          }}>
            {!pickedPal ? (
              <div style={{ position: "relative", display: "grid", justifyItems: "center", gap: 14, textAlign: "center", padding: 24 }}>
                <div style={{ width: 190, height: 190, border: "2px dashed #d9a8c4", borderRadius: 10, display: "grid", placeItems: "center", background: "repeating-linear-gradient(-45deg,#fdf3f9 0 8px,#ffffff 8px 16px)" }}>
                  <span style={{ fontFamily: MONO, fontSize: 9, color: "#c58bab", letterSpacing: ".08em" }}>EMPTY STAGE</span>
                </div>
                <div style={{ fontFamily: MONO, fontSize: 11, color: "#9a5b7c", letterSpacing: ".05em" }}>NO PALETTE SELECTED</div>
                <div style={{ fontSize: 11, color: "#8b8b8b", maxWidth: 250, lineHeight: 1.55 }}>
                  Click a palette on the left. A profile window opens beside this one.
                  <span style={{ animation: "blink 1.1s steps(1) infinite", color: "#d0459a" }}>&nbsp;{"▦"}</span>
                </div>
              </div>
            ) : (
              <div style={{ position: "relative", display: "grid", justifyItems: "center", gap: 14, padding: 20, width: "100%", boxSizing: "border-box" }}>
                <img src={pickedPal.img} alt={pickedPal.name} draggable={false} style={{ width: 220, height: 220, objectFit: "contain", borderRadius: 6, background: "#fff" }} />
                <div style={{ fontFamily: MONO, fontSize: 15, letterSpacing: ".06em", color: "#2a2a2a", textAlign: "center" }}>{pickedPal.name}</div>

                {/* what this palette pulls out of the closet */}
                <div style={{ width: "100%", borderTop: "1px dashed #e3c3d5", paddingTop: 12, display: "grid", gap: 12 }}>
                  <div style={{ fontFamily: MONO, fontSize: 8.5, letterSpacing: ".08em", color: "#c0468f" }}>
                    {`YOUR CLOSET · ${hitCount(pickedPal)} MATCHES`}
                  </div>
                  {hitCount(pickedPal) === 0 ? (
                    <div style={{ fontSize: 11, color: "#8b8b8b", lineHeight: 1.55 }}>
                      Nothing you own scores under {data.meta.cutoff} against these colors.
                    </div>
                  ) : (
                    pickedPal.groups.map((group) => <MatchRow key={group.hex} group={group} size={70} />)
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── profile pop-up windows ── */}
      {windows.map((w) => {
        const pal = PALETTES.find((p) => p.id === w.id);
        if (!pal) return null;
        return (
          <div key={w.id} style={{
            position: "absolute", left: w.x, top: w.y, width: 312, zIndex: w.z,
            borderRadius: 7, background: "linear-gradient(#ffe6f4,#ffd0e9)", border: "1px solid #d3699f",
            boxShadow: "0 12px 28px rgba(150,60,110,.3)", animation: "pop .16s ease-out",
            transform: `scale(${PROFILE_SCALE})`, transformOrigin: "top left",
          }}>
            {/* pop-up title bar (drag here) */}
            <div onPointerDown={(e) => startDrag(w.id, e)} style={{
              height: 26, display: "flex", alignItems: "center", gap: 6, padding: "0 7px",
              borderRadius: "6px 6px 0 0", background: "linear-gradient(#ffa8d6,#f279b8)",
              borderBottom: "1px solid #d05e97", cursor: "grab", touchAction: "none",
            }}>
              <span style={{ fontSize: 11, color: "#7d2652" }}>{"♥"}</span>
              <span style={{ fontFamily: MONO, fontSize: 8.5, letterSpacing: ".06em", color: "#6d1f47" }}>{pal.name}.PROFILE</span>
              <span style={{ marginLeft: "auto", display: "flex", gap: 4 }}>
                <span style={{ width: 14, height: 13, border: "1px solid #c95d93", borderRadius: 2, background: "#ffd3ea", display: "grid", placeItems: "center", fontSize: 8, color: "#8a3462" }}>{"–"}</span>
                <span style={{ width: 14, height: 13, border: "1px solid #c95d93", borderRadius: 2, background: "#ffd3ea", display: "grid", placeItems: "center", fontSize: 8, color: "#8a3462" }}>{"□"}</span>
                <span onClick={(e) => { e.stopPropagation(); closeWin(w.id); }} onPointerDown={(e) => e.stopPropagation()} style={{ width: 14, height: 13, border: "1px solid #c95d93", borderRadius: 2, background: "#ffbcdd", display: "grid", placeItems: "center", fontSize: 9, color: "#7d1f45", cursor: "pointer" }}>{"×"}</span>
              </span>
            </div>

            {/* pop-up body */}
            <div style={{ padding: "11px 12px 13px", display: "grid", gap: 11 }}>
              <div style={{ display: "flex", gap: 11 }}>
                <img src={pal.img} alt={pal.name} draggable={false} style={{ width: 104, height: 104, flex: "none", objectFit: "cover", border: "1px solid #e79cc4", background: "#fff", borderRadius: 2, display: "block" }} />
                <div style={{ display: "grid", alignContent: "start", gap: 8 }}>
                  <div style={{ fontFamily: MONO, fontSize: 11, color: "#5f1a3e", letterSpacing: ".04em", lineHeight: 1.3 }}>{pal.name}</div>
                  <div style={{ fontFamily: MONO, fontSize: 8, color: "#c0468f", letterSpacing: ".06em" }}>{pal.colors.length} MAIN COLORS</div>
                  {pal.colors.map((hex) => <Swatch key={hex} hex={hex} />)}
                </div>
              </div>

              {/* the closet, scored against this palette */}
              <div className="stage" style={{ borderTop: "1px solid #f0b8d8", paddingTop: 9, display: "grid", gap: 10, maxHeight: 300, overflowY: "auto", paddingRight: 4 }}>
                {hitCount(pal) === 0 ? (
                  <span style={{ fontFamily: MONO, fontSize: 8, color: "#b07b9a", letterSpacing: ".05em" }}>
                    {`NOTHING UNDER ${data.meta.cutoff}`}
                  </span>
                ) : (
                  pal.groups.map((group) => <MatchRow key={group.hex} group={group} size={78} />)
                )}
              </div>

              {/* one button, full width — clicking the palette already selects it */}
              <span className="close-btn" onClick={() => closeWin(w.id)} style={{
                display: "block", textAlign: "center", padding: "7px 0", fontFamily: MONO, fontSize: 8.5,
                letterSpacing: ".06em", color: "#8a3462", background: "linear-gradient(#fff,#ffdcef)",
                border: "1px solid #e79cc4", borderRadius: 3, cursor: "pointer",
              }}>CLOSE</span>
            </div>
          </div>
        );
      })}

      {/* ── dock (pinned to the bottom-center of the screen) ── */}
      <div style={{
        position: "absolute", left: "50%", bottom: 22, transform: "translateX(-50%)",
        display: "flex", alignItems: "center", gap: 12, padding: "8px 16px", borderRadius: 14,
        background: "linear-gradient(rgba(40,32,38,.86),rgba(20,16,20,.9))",
        border: "1px solid rgba(255,255,255,.18)", boxShadow: "0 10px 24px rgba(80,40,70,.35)",
      }}>
        {[
          { bg: "linear-gradient(#ffd6ec,#f79ac9)", icon: "♥" },
          { bg: "linear-gradient(#ffe3f2,#f4a8d2)", icon: "♪" },
          { bg: "linear-gradient(#fff0f8,#f6b9dc)", icon: "✉" },
          { bg: "linear-gradient(#ffd6ec,#f79ac9)", icon: "○" },
          { bg: "linear-gradient(#ffe3f2,#f4a8d2)", icon: "▣" },
          { bg: "linear-gradient(#fff0f8,#f6b9dc)", icon: "☉" },
        ].map((d, i) => (
          <span key={i} style={{ width: 26, height: 26, borderRadius: 6, background: d.bg, display: "grid", placeItems: "center", fontSize: 12, color: "#8a3462" }}>{d.icon}</span>
        ))}
      </div>
    </div>
  );
}
