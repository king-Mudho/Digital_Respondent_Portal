"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { StudyHeader } from "@/components/respondent/StudyHeader";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  getKIIRespondentProfile,
  submitKIIFieldVerification,
  type KIIRespondentProfile,
} from "@/lib/api/kiiRespondent";
import { respondentErrorMessage } from "@/lib/api/respondentErrors";

// The KII informant checks the research team's background facts before the KII Guide (PI decision, 2026-10-13), the
// same step Main-400 respondents have at /i/[token]/verify. Facts whose source was too weak to show are asked as open
// questions instead -- their value is never displayed. Skips itself when there is nothing to check; never a gate.
const FACT_OPTIONS = [
  { value: "YES_CORRECT", label: "Yes, correct" },
  { value: "PARTLY_CORRECT", label: "Partly correct", needsValue: true },
  { value: "NO_CORRECT_VALUE_PROVIDED", label: "No — correct it", needsValue: true },
  { value: "DO_NOT_KNOW", label: "Don't know" },
  { value: "PREFER_NOT_TO_SAY", label: "Prefer not to say" },
  { value: "NOT_APPLICABLE", label: "Not applicable" },
];
const QUESTION_OPTIONS = [
  { value: "NO_CORRECT_VALUE_PROVIDED", label: "I'll answer", needsValue: true },
  { value: "DO_NOT_KNOW", label: "Don't know" },
  { value: "PREFER_NOT_TO_SAY", label: "Prefer not to say" },
  { value: "NOT_APPLICABLE", label: "Not applicable" },
];
const NEEDS_VALUE = new Set(["PARTLY_CORRECT", "NO_CORRECT_VALUE_PROVIDED"]);

function Choices({
  options, value, onChange, label,
}: { options: { value: string; label: string }[]; value?: string; onChange: (v: string) => void; label: string }) {
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3" role="group" aria-label={label}>
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          aria-pressed={value === opt.value}
          className={`min-h-11 rounded-md border px-3 py-2 text-sm text-left sm:text-center ${
            value === opt.value ? "border-accent bg-accent/10 font-medium" : "border-border bg-surface"
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

export default function KIIVerifyPage() {
  const params = useParams<{ token: string }>();
  const router = useRouter();
  const token = params.token;
  const [profile, setProfile] = useState<KIIRespondentProfile | null | undefined>(undefined);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [values, setValues] = useState<Record<number, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getKIIRespondentProfile(token).then(setProfile).catch(() => setProfile(null));
  }, [token]);

  const goOn = () => router.push(`/ki/${token}/kobo-redirect`);

  const items = profile ? [...profile.fields.map((f) => f.id), ...profile.questions.map((q) => q.id)] : [];
  useEffect(() => {
    if (profile === null || (profile && items.length === 0)) goOn();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile]);

  if (!profile || items.length === 0) {
    return (
      <main className="min-h-screen flex flex-col">
        <StudyHeader />
        <section className="flex-1 flex items-center justify-center px-6 py-16">
          <p className="text-text-muted">Loading…</p>
        </section>
      </main>
    );
  }

  const allAnswered = items.every((id) => answers[id]);
  const missingValue = items.some((id) => NEEDS_VALUE.has(answers[id] ?? "") && !(values[id] ?? "").trim());

  async function handleContinue() {
    setSubmitting(true);
    setError(null);
    try {
      // One at a time, as on the Main-400 page: a retry after a failure part-way simply re-sends each answer.
      for (const id of items) {
        await submitKIIFieldVerification({ token, fieldId: id, status: answers[id], respondentValue: values[id] ?? "" });
      }
      goOn();
    } catch (err) {
      setError(respondentErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  const valueBox = (id: number, label: string, placeholder: string) =>
    NEEDS_VALUE.has(answers[id] ?? "") && (
      <label className="block mt-2">
        <span className="sr-only">{label}</span>
        <input
          placeholder={placeholder}
          value={values[id] ?? ""}
          onChange={(e) => setValues((v) => ({ ...v, [id]: e.target.value }))}
          className="min-h-11 w-full rounded-md border border-border px-3 py-2.5 text-base"
        />
      </label>
    );

  return (
    <main className="min-h-screen flex flex-col">
      <StudyHeader />
      <section className="flex-1 flex items-center justify-center px-6 py-16">
        <Card className="max-w-xl w-full space-y-6">
          <div>
            <h2 className="font-semibold text-lg">Before the interview questions</h2>
            <p className="text-text-muted text-sm mt-2">
              The research team reviewed publicly available information about your organisation and role, to avoid asking
              you things that are already known. Please confirm each item, correct it, say you&apos;re unsure, or decline.
              Your own answers are kept separately from this background information.
            </p>
          </div>

          {profile.fields.length > 0 && (
            <div className="space-y-5">
              {profile.fields.map((field) => (
                <div key={field.id} className="border-t border-border pt-4">
                  <p className="text-sm font-medium">{field.label}</p>
                  <p className="text-sm text-text-muted mb-2">
                    We have this as: <span className="text-text">{field.preliminary_documentary_value}</span>
                  </p>
                  <Choices options={FACT_OPTIONS} value={answers[field.id]} label={`Is this correct: ${field.label}?`}
                    onChange={(v) => setAnswers((a) => ({ ...a, [field.id]: v }))} />
                  {valueBox(field.id, `What ${field.label} should say`, "What should it say?")}
                </div>
              ))}
            </div>
          )}

          {profile.questions.length > 0 && (
            <div className="space-y-5">
              <p className="border-t border-border pt-4 text-sm text-text-muted">
                We couldn&apos;t confirm these from public sources. Please answer if you can.
              </p>
              {profile.questions.map((q) => (
                <div key={q.id}>
                  <p className="text-sm font-medium mb-2">{q.label}</p>
                  <Choices options={QUESTION_OPTIONS} value={answers[q.id]} label={q.label}
                    onChange={(v) => setAnswers((a) => ({ ...a, [q.id]: v }))} />
                  {valueBox(q.id, `Your answer: ${q.label}`, "Your answer")}
                </div>
              ))}
            </div>
          )}

          {error && <p role="alert" className="text-danger text-sm">{error}</p>}
          {missingValue && <p className="text-text-muted text-sm">Please fill in your answer, or choose a different option.</p>}
          <Button className="w-full" disabled={!allAnswered || missingValue || submitting} onClick={handleContinue}>
            {submitting ? "Saving your answers…" : "Continue to the interview"}
          </Button>
          <button type="button" onClick={goOn} className="w-full text-sm text-text-muted underline min-h-11">
            Skip this step
          </button>
        </Card>
      </section>
    </main>
  );
}
