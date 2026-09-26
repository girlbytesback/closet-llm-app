import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// supabase.js throws at import without the VITE_ env vars and would talk to a
// real project, so the whole module is swapped for a stub. vi.hoisted makes
// the stub exist before vi.mock (which is hoisted above the imports) runs.
const auth = vi.hoisted(() => ({
  getSession: vi.fn(),
  signOut: vi.fn(),
  onAuthStateChange: vi.fn(),
}));
vi.mock("./supabase", () => ({ supabase: { auth } }));

const { authedFetch } = await import("./api");

// api.js registers its listener once, at import. Grab it now, before any
// beforeEach clears the mock's call history.
expect(auth.onAuthStateChange).toHaveBeenCalledTimes(1);
const onAuthChange = auth.onAuthStateChange.mock.calls[0][0];

// Let the fire-and-forget promises (and their .catch) settle.
const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

let fetchMock;

beforeEach(() => {
  fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 200 }));
  vi.stubGlobal("fetch", fetchMock);
  auth.getSession.mockReset();
  auth.signOut.mockReset().mockResolvedValue({ error: null });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("authedFetch", () => {
  it("attaches the access token as a bearer header", async () => {
    auth.getSession.mockResolvedValue({ data: { session: { access_token: "tok-123" } } });

    await authedFetch("/garments");

    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/garments");
    expect(init.headers.get("Authorization")).toBe("Bearer tok-123");
  });

  it("sends no Authorization header when signed out", async () => {
    auth.getSession.mockResolvedValue({ data: { session: null } });

    await authedFetch("/garments");

    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers.has("Authorization")).toBe(false);
  });

  it("keeps the caller's headers and options", async () => {
    auth.getSession.mockResolvedValue({ data: { session: { access_token: "tok" } } });

    await authedFetch("/upload-garments", {
      method: "POST",
      body: "payload",
      headers: { "X-Custom": "yes" },
    });

    const [, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe("POST");
    expect(init.body).toBe("payload");
    expect(init.headers.get("X-Custom")).toBe("yes");
    expect(init.headers.get("Authorization")).toBe("Bearer tok");
  });

  it("signs out when the server answers 401", async () => {
    auth.getSession.mockResolvedValue({ data: { session: { access_token: "stale" } } });
    fetchMock.mockResolvedValue(new Response(null, { status: 401 }));

    const res = await authedFetch("/garments");

    expect(res.status).toBe(401);
    expect(auth.signOut).toHaveBeenCalledTimes(1);
  });

  it("does not sign out on other statuses", async () => {
    auth.getSession.mockResolvedValue({ data: { session: { access_token: "tok" } } });
    fetchMock.mockResolvedValue(new Response(null, { status: 500 }));

    const res = await authedFetch("/garments");

    expect(res.status).toBe(500);
    expect(auth.signOut).not.toHaveBeenCalled();
  });
});

describe("session cookie sync", () => {
  it.each(["INITIAL_SESSION", "SIGNED_IN", "TOKEN_REFRESHED"])(
    "POSTs the access token to /session on %s",
    async (event) => {
      onAuthChange(event, { access_token: "tok-abc" });
      await flush();

      expect(fetchMock).toHaveBeenCalledTimes(1);
      const [path, init] = fetchMock.mock.calls[0];
      expect(path).toBe("/session");
      expect(init.method).toBe("POST");
      expect(init.headers).toEqual({ "Content-Type": "application/json" });
      expect(JSON.parse(init.body)).toEqual({ access_token: "tok-abc" });
    }
  );

  it("sends only the access token, not the rest of the session", async () => {
    onAuthChange("SIGNED_IN", {
      access_token: "tok",
      refresh_token: "secret-refresh",
      user: { id: "u1" },
    });
    await flush();

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ access_token: "tok" });
  });

  it("DELETEs /session on SIGNED_OUT", async () => {
    onAuthChange("SIGNED_OUT", null);
    await flush();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith("/session", { method: "DELETE" });
  });

  it("does nothing on page load with no session", async () => {
    onAuthChange("INITIAL_SESSION", null);
    await flush();

    expect(fetchMock).not.toHaveBeenCalled();
  });

  describe("when the network fails", () => {
    // The callback throws the fetch promise away, so the only way a missing
    // .catch shows up is as an unhandled rejection. Collect those directly.
    let unhandled;
    const onUnhandled = (reason) => unhandled.push(reason);

    beforeEach(() => {
      unhandled = [];
      process.on("unhandledRejection", onUnhandled);
      // A plain function, not vi.fn(): the spy chains its own handler onto
      // returned promises, which would mark the rejection handled and hide a
      // missing .catch in api.js.
      const calls = [];
      fetchMock = Object.assign(
        (...args) => {
          calls.push(args);
          return Promise.reject(new TypeError("Failed to fetch"));
        },
        { calls }
      );
      vi.stubGlobal("fetch", fetchMock);
    });

    afterEach(() => {
      process.off("unhandledRejection", onUnhandled);
    });

    it("swallows a failed POST", async () => {
      onAuthChange("SIGNED_IN", { access_token: "tok" });
      await flush();

      expect(fetchMock.calls).toHaveLength(1);
      expect(unhandled).toEqual([]);
    });

    it("swallows a failed DELETE", async () => {
      onAuthChange("SIGNED_OUT", null);
      await flush();

      expect(fetchMock.calls).toHaveLength(1);
      expect(unhandled).toEqual([]);
    });
  });
});
