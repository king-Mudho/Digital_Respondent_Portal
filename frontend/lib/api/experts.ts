/** The ABI expert panel (backend apps/experts, 2026-11-08). */

export interface ExpertRow {
  expert_id: string;
  full_name: string;
  title: string;
  institution: string;
  institution_category: string;
  panel_area: string;
  panel_area_label: string;
  years_experience: number | null;
  phone: string;
  whatsapp_number: string;
  email: string;
  conflicts_note: string;
  notes: string;
  status: "PROSPECT" | "INVITED" | "CONSENTED" | "COMPLETED" | "DECLINED";
  status_label: string;
  completed_at: string | null;
  created_at: string;
  link: { status: string; issued_at: string; expires_at: string; channel: string } | null;
}

export interface PanelArea {
  area: string;
  label: string;
  target: number;
  registered: number;
  invited: number;
  completed: number;
}

export interface ExpertPanel {
  results: ExpertRow[];
  panel: PanelArea[];
  completed: number;
  target: number;
  /** Why invitations can't go out now (no ethics reference yet, or the panel is complete); "" when they can. */
  invitations_closed: string;
  form_configured: boolean;
  panel_areas: { value: string; label: string }[];
  institution_categories: { value: string; label: string }[];
}

export interface ExpertDetail extends ExpertRow {
  invitations: {
    id: number;
    status: string;
    status_label: string;
    channel: string;
    issued_at: string;
    expires_at: string;
    first_opened_at: string | null;
    revoked_reason: string;
  }[];
  consent: { decision: string; at: string } | null;
}

export const EXPERT_STATUS_TONE: Record<ExpertRow["status"], string> = {
  PROSPECT: "text-text-muted",
  INVITED: "text-header",
  CONSENTED: "text-warning",
  COMPLETED: "text-success",
  DECLINED: "text-danger",
};
