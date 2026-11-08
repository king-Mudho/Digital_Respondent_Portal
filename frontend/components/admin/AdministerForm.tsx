"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { adminFetch } from "@/lib/api/admin";
import { KII_PARTICIPANT_INFORMATION_SHEET_VERSION } from "@/lib/constants/kiiParticipantInformation";
import { PARTICIPANT_INFORMATION_SHEET_VERSION } from "@/lib/constants/participantInformation";
import { ROLE_CATEGORIES } from "@/lib/constants/roleCategories";

/**
 * Filling in the form with them, on the phone or a WhatsApp call (backend apps/ra/administer.py, 2026-11-08). The RA
 * reads the participant information aloud, records the respondent's verbal consent (and, for the questionnaire, who
 * they are speaking to and their role), and the form opens with the RA stamped in it -- which is what credits the
 * completion to them. The server refuses it for a case not assigned to them, a locked Reserve, or someone who withdrew.
 */
export function AdministerForm({ kind, ident, onDone }: { kind: "main" | "kii"; ident: string; onDone: () => void }) {
  const [mode, setMode] = useState<"PHONE" | "WHATSAPP_CALL">("PHONE");
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [url, setUrl] = useState<string | null>(null);

  const open = useMutation({
    mutationFn: () =>
      adminFetch<{ kobo_form_url: string }>(`/ra/administer/${kind}/${encodeURIComponent(ident)}/`, {
        method: "POST",
        body: JSON.stringify({
          mode,
          respondent_name: name,
          role_category: role,
          recording_consent: recording,
          information_sheet_version: kind === "main" ? PARTICIPANT_INFORMATION_SHEET_VERSION : KII_PARTICIPANT_INFORMATION_SHEET_VERSION,
        }),
      }),
    onSuccess: (data) => {
      setError(null);
      setUrl(data.kobo_form_url);
      window.open(data.kobo_form_url, "_blank", "noopener");
    },
    onError: (err) => setError(err instanceof Error ? err.message : "The form could not be opened."),
  });

  const ready = agreed && (kind === "kii" || (name.trim() && role));
  const input = "mt-1 block min-h-11 w-full rounded-md border border-border bg-bg px-2";

  return (
    <div className="space-y-2 rounded-md border border-header p-3">
      <p className="text-sm font-medium">{kind === "main" ? "Fill in the questionnaire with them now" : "Interview them now"}</p>
      <p className="text-xs text-text-muted">
        Read them the participant information first. Never read out or change answers they give, and never describe the
        study as a loan, a credit rating or a guarantee.
      </p>
      <label className="block text-sm">
        How you are talking
        <select value={mode} onChange={(e) => setMode(e.target.value as typeof mode)} className={input}>
          <option value="PHONE">Phone call</option>
          <option value="WHATSAPP_CALL">WhatsApp call</option>
        </select>
      </label>
      {kind === "main" && (
        <>
          <label className="block text-sm">
            Who you are speaking to
            <input value={name} onChange={(e) => setName(e.target.value)} className={input} placeholder="Full name" />
          </label>
          <label className="block text-sm">
            Their role in the organisation
            <select value={role} onChange={(e) => setRole(e.target.value)} className={input}>
              <option value="">Choose…</option>
              {ROLE_CATEGORIES.map((r) => (
                <option key={r.value} value={r.value}>{r.label}</option>
              ))}
            </select>
          </label>
        </>
      )}
      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" className="mt-1 h-4 w-4" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
        <span>I read them the participant information and they agreed, voluntarily, to take part.</span>
      </label>
      {kind === "kii" && (
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-1 h-4 w-4" checked={recording} onChange={(e) => setRecording(e.target.checked)} />
          <span>They also agreed to the interview being audio-recorded (leave unticked if not asked or not agreed).</span>
        </label>
      )}
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      {url && (
        <p className="text-sm text-success">
          The form opened in a new tab. <a href={url} target="_blank" rel="noopener noreferrer" className="underline">Open it again</a>
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <Button type="button" disabled={!ready || open.isPending} onClick={() => open.mutate()}>
          {open.isPending ? "Opening…" : "Record consent and open the form"}
        </Button>
        <Button type="button" variant="outline" onClick={onDone}>Close</Button>
      </div>
    </div>
  );
}
