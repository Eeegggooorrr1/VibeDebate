import { afterEach, describe, expect, it, vi } from "vitest";
vi.mock("../auth/session", () => ({
  accessToken: vi.fn(async () => "memory-only-token"),
  endSession: vi.fn(),
}));
import { ApiError, request } from "./http";

afterEach(() => vi.unstubAllGlobals());
describe("authenticated API transport", () => {
  it("sends a bearer token and JSON request with the expected prefix", async () => {
    const fetch = vi.fn(async () => new Response(JSON.stringify({ ok: true })));
    vi.stubGlobal("fetch", fetch);
    await request("/me/profile", { method: "PATCH", body: "{}" });
    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/me/profile",
      expect.objectContaining({
        method: "PATCH",
        headers: expect.objectContaining({
          Authorization: "Bearer memory-only-token",
          "Content-Type": "application/json",
        }),
      }),
    );
  });
  it("preserves backend field errors without exposing raw English messages", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              detail: [
                {
                  loc: ["body", "interests"],
                  msg: "Invalid UUID",
                  type: "uuid_parsing",
                },
              ],
            }),
            { status: 422 },
          ),
      ),
    );
    await expect(request("/me")).rejects.toMatchObject({
      status: 422,
      message: "Проверьте заполненные поля.",
      details: [expect.objectContaining({ loc: ["body", "interests"] })],
    });
  });
  it("turns connection failures into a retryable localized error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      }),
    );
    await expect(request("/me")).rejects.toBeInstanceOf(ApiError);
    await expect(request("/me")).rejects.toMatchObject({
      status: 0,
      code: "network_error",
    });
  });
});
