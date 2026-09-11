import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useParams: () => ({ token: "tok" }),
  useRouter: () => ({ push: pushMock, replace: vi.fn() }),
}));

const submitEligibilityMock = vi.fn();
vi.mock("@/lib/api/respondent", () => ({
  submitEligibility: (...args: unknown[]) => submitEligibilityMock(...args),
}));

import EligibilityPage from "@/app/i/[token]/eligibility/page";

describe("EligibilityPage", () => {
  beforeEach(() => {
    pushMock.mockClear();
    submitEligibilityMock.mockReset();
  });

  it("does not call the API when required fields are empty (native validation blocks submit)", () => {
    render(<EligibilityPage />);
    // A real click on the submit button runs the browser's constraint
    // validation before the submit event fires; jsdom implements this too,
    // but only via a click/requestSubmit path -- dispatching a raw "submit"
    // event bypasses it entirely, which would make this test pass for the
    // wrong reason (see https://github.com/testing-library/dom-testing-library
    // for the general gotcha).
    fireEvent.click(screen.getByRole("button", { name: /continue/i }));
    expect(submitEligibilityMock).not.toHaveBeenCalled();
  });

  it("shows the referral message, never advances to /information, when ineligible", async () => {
    submitEligibilityMock.mockResolvedValue({ respondent_id: 1, is_eligible: false });
    render(<EligibilityPage />);

    fireEvent.change(screen.getByLabelText(/your full name/i), { target: { value: "Gatekeeper" } });
    fireEvent.change(screen.getByLabelText(/which best describes your role/i), {
      target: { value: "NONE_OF_THESE" },
    });
    fireEvent.click(screen.getByRole("button", { name: /continue/i }));

    await waitFor(() => {
      expect(screen.getByText(/thank you for your time/i)).toBeInTheDocument();
    });
    expect(pushMock).not.toHaveBeenCalledWith(expect.stringContaining("/information"));
  });

  it("advances to /information when eligible", async () => {
    submitEligibilityMock.mockResolvedValue({ respondent_id: 2, is_eligible: true });
    render(<EligibilityPage />);

    fireEvent.change(screen.getByLabelText(/your full name/i), { target: { value: "Jane Doe" } });
    fireEvent.change(screen.getByLabelText(/which best describes your role/i), {
      target: { value: "CEO_MD" },
    });
    fireEvent.click(screen.getByRole("button", { name: /continue/i }));

    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith("/i/tok/information");
    });
  });
});
