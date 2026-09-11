import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { ApiError, apiFetch } from "@/lib/api/client";

describe("apiFetch", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("throws a typed ApiError with the backend's error envelope", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      statusText: "Bad Request",
      json: async () => ({ error: { code: "token_expired", message: "Expired.", field_errors: {} } }),
    }) as unknown as typeof fetch;

    await expect(apiFetch("/invitations/validate/?t=x")).rejects.toMatchObject({
      code: "token_expired",
      message: "Expired.",
    });
  });

  it("resolves with parsed JSON on success", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: "valid" }),
    }) as unknown as typeof fetch;

    const result = await apiFetch<{ status: string }>("/invitations/validate/?t=x");
    expect(result.status).toBe("valid");
  });

  it("is an instance of ApiError, not a generic Error, so callers can branch on .code", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      statusText: "Forbidden",
      json: async () => ({ error: { code: "consent_required", message: "No consent.", field_errors: {} } }),
    }) as unknown as typeof fetch;

    try {
      await apiFetch("/kobo/redirect-url/?t=x");
      expect.fail("expected apiFetch to throw");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
    }
  });
});
