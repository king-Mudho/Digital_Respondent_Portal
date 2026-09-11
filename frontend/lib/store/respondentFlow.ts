import { create } from "zustand";

/**
 * Respondent-flow-in-progress state, scoped to one token's session, not
 * persisted beyond the browser tab (docs/07_FRONTEND_ARCHITECTURE.md) --
 * unlike ABI's 24-question wizard, this flow is short and each step is
 * already durably recorded server-side as it completes, so there is no
 * multi-day draft to protect here.
 */
interface RespondentFlowState {
  token: string;
  organisationConfirmation: string;
  fullName: string;
  roleCategory: string;
  isEligible: boolean | null;
  consentVersion: string;
  participationChoice:
    | "SELF_NOW"
    | "PHONE_ASSISTED"
    | "WHATSAPP_ASSISTED"
    | "REQUEST_CONTACT"
    | null;
  setToken: (token: string) => void;
  setOrganisationConfirmation: (text: string) => void;
  setEligibility: (fullName: string, roleCategory: string, isEligible: boolean) => void;
  setParticipationChoice: (choice: RespondentFlowState["participationChoice"]) => void;
  reset: () => void;
}

const initialState = {
  token: "",
  organisationConfirmation: "",
  fullName: "",
  roleCategory: "",
  isEligible: null as boolean | null,
  consentVersion: "v1.0",
  participationChoice: null as RespondentFlowState["participationChoice"],
};

export const useRespondentFlow = create<RespondentFlowState>((set) => ({
  ...initialState,
  setToken: (token) => set({ token }),
  setOrganisationConfirmation: (organisationConfirmation) => set({ organisationConfirmation }),
  setEligibility: (fullName, roleCategory, isEligible) => set({ fullName, roleCategory, isEligible }),
  setParticipationChoice: (participationChoice) => set({ participationChoice }),
  reset: () => set(initialState),
}));
