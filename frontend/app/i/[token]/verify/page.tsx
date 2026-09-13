"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { StudyHeader } from "@/components/respondent/StudyHeader";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  getRespondentPreProfile,
  submitFieldVerification,
  type RespondentPreProfile,
  type VerificationStatus,
} from "@/lib/api/respondent";
import { respondentErrorMessage } from "@/lib/api/respondentErrors";
import { useRespondentFlow } from "@/lib/store/respondentFlow";

// PROIT verification screen (ABF-FST_PROIT_v1.0_Portal_Deployment_Tool.docx
// Section 3): "Before this interview, the research team reviewed relevant
// publicly available or institutionally authorised information about your
// organisation and professional role to reduce repetitive background
// questions." Placed after consent, before the completion-mode choice.
// Self-skips (never shown) whenever there's nothing to verify -- see
// getRespondentPreProfile.
const RESPONSE_OPTIONS: { value: VerificationStatus; label: string; needsCorrection?: boolean }[] = [
  { value: "YES_CORRECT", label: "Yes, correct" },
  { value: "PARTLY_CORRECT", label: "Partly correct" },
  { value: "NO_CORRECT_VALUE_PROVIDED", label: "No -- correct it", needsCorrection: true },
  { value: "DO_NOT_KNOW", label: "Don't know" },
  { value: "PREFER_NOT_TO_SAY", label: "Prefer not to say" },
  { value: "NOT_APPLICABLE", label: "Not applicable" },
];

export default function VerifyPage() {
  const params = useParams<{ token: string }>();
  const router = useRouter();
  const token = useRespondentFlow((s) => s.token) || params.token;

  const [profile, setProfile] = useState<RespondentPreProfile | null | undefined>(undefined);
  const [responses, setResponses] = useState<Record<number, VerificationStatus>>({});
  const [corrections, setCorrections] = useState<Record<number, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getRespondentPreProfile(token)
      .then(setProfile)
      .catch(() => setProfile(null));
  }, [token]);

  const goToChoice = () => router.push(`/i/${params.token}/choice`);

  // Nothing to verify -- skip straight through, exactly as if this screen
  // didn't exist.
  useEffect(() => {
    if (profile === null || (profile && profile.fields.length === 0)) {
      goToChoice();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile]);

  if (profile === undefined || profile === null || profile.fields.length === 0) {
    return (
      <main className="min-h-screen flex flex-col">
        <StudyHeader />
        <section className="flex-1 flex items-center justify-center px-6 py-16">
          <p className="text-text-muted">Loading…</p>
        </section>
      </main>
    );
  }

  const allAnswered = profile.fields.every((f) => responses[f.id]);
  // "No -- correct it" without the correction would record an empty
  // respondent value, which is indistinguishable from "didn't answer" in
  // the reconciled record.
  const missingCorrection = profile.fields.some(
    (f) => responses[f.id] === "NO_CORRECT_VALUE_PROVIDED" && !(corrections[f.id] ?? "").trim(),
  );

  async function handleContinue() {
    setSubmitting(true);
    setError(null);
    try {
      // Sequential, not Promise.all: these are separate writes, and a
      // partial failure part-way through a parallel batch left the
      // respondent stuck on this screen with no message and no idea which
      // answers had been saved. In order, a retry simply re-sends the
      // ones that already succeeded, which is idempotent per field.
      for (const field of profile!.fields) {
        await submitFieldVerification({
          token,
          fieldId: field.id,
          status: responses[field.id],
          respondentValue: corrections[field.id] ?? "",
        });
      }
      goToChoice();
    } catch (err) {
      setError(respondentErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  // Nothing here is required of the respondent -- PROIT is a burden
  // reduction, not an extra gate, so there is always a way past it.
  function skipVerification() {
    goToChoice();
  }

  return (
    <main className="min-h-screen flex flex-col">
      <StudyHeader />
      <section className="flex-1 flex items-center justify-center px-6 py-16">
        <Card className="max-w-xl w-full space-y-6">
          <div>
            <h2 className="font-semibold text-lg">Before we continue</h2>
            <p className="text-text-muted text-sm mt-2">
              Before this interview, the research team reviewed relevant publicly available or institutionally
              authorised information about your organisation and professional role, to reduce repetitive background
              questions. Please confirm each item below, correct it, say you&apos;re unsure, or decline to verify it. Your
              direct responses remain distinct from this background information.
            </p>
          </div>

          <div className="space-y-5">
            {profile.fields.map((field) => (
              <div key={field.id} className="border-t border-border pt-4">
                <p className="text-sm font-medium">{field.label}</p>
                <p className="text-sm text-text-muted mb-2">
                  We have this as: <span className="text-text">{field.preliminary_documentary_value}</span>
                </p>
                <div className="flex flex-wrap gap-2">
                  {RESPONSE_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => setResponses((r) => ({ ...r, [field.id]: opt.value }))}
                      className={`rounded-md border px-2.5 py-1.5 text-xs ${
                        responses[field.id] === opt.value
                          ? "border-accent bg-accent/10 font-medium"
                          : "border-border bg-surface"
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
                {responses[field.id] === "NO_CORRECT_VALUE_PROVIDED" && (
                  <input
                    placeholder="What should it say instead?"
                    value={corrections[field.id] ?? ""}
                    onChange={(e) => setCorrections((c) => ({ ...c, [field.id]: e.target.value }))}
                    className="mt-2 w-full rounded-md border border-border px-3 py-2 text-sm"
                  />
                )}
              </div>
            ))}
          </div>

          {error && <p className="text-danger text-sm">{error}</p>}
          {missingCorrection && (
            <p className="text-text-muted text-sm">
              Please fill in what the corrected value should be, or choose a different answer.
            </p>
          )}
          <Button
            className="w-full"
            disabled={!allAnswered || missingCorrection || submitting}
            onClick={handleContinue}
          >
            {submitting ? "Saving your answers…" : "Continue"}
          </Button>
          <button
            type="button"
            onClick={skipVerification}
            className="w-full text-sm text-text-muted underline min-h-11"
          >
            Skip this step
          </button>
        </Card>
      </section>
    </main>
  );
}
