import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/client";

const replaceMock = vi.fn();
vi.mock("next/navigation", () => ({
  useParams: () => ({ token: "bad-token" }),
  useRouter: () => ({ replace: replaceMock, push: vi.fn() }),
}));

vi.mock("@/lib/api/respondent", () => ({
  validateToken: vi.fn().mockRejectedValue(new ApiError(400, "token_expired", "Expired.")),
}));

import InvitationValidatePage from "@/app/i/[token]/page";

describe("InvitationValidatePage", () => {
  it("shows a clear, specific error state for an expired token rather than crashing", async () => {
    render(<InvitationValidatePage />);

    await waitFor(() => {
      expect(screen.getByText(/invitation not valid/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/expired/i)).toBeInTheDocument();
    expect(replaceMock).not.toHaveBeenCalled();
  });
});
