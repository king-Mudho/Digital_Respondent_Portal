import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: vi.fn() }),
}));

import { ApiError } from "@/lib/api/client";

vi.mock("@/lib/api/admin", () => ({
  login: vi.fn().mockRejectedValue(new ApiError(401, "invalid_credentials", "Invalid username or password.")),
}));

import AdminLoginPage from "@/app/admin/login/page";

describe("AdminLoginPage", () => {
  it("shows an error and does not navigate on invalid credentials", async () => {
    render(<AdminLoginPage />);

    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: "wrong" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "wrong" } });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText(/invalid username or password/i)).toBeInTheDocument();
    });
    expect(pushMock).not.toHaveBeenCalled();
  });
});
