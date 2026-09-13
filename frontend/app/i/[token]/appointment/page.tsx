"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { StudyHeader } from "@/components/respondent/StudyHeader";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { requestAppointment } from "@/lib/api/respondent";
import { respondentErrorMessage } from "@/lib/api/respondentErrors";
import { useRespondentFlow } from "@/lib/store/respondentFlow";

const MODE_BY_CHOICE: Record<string, string> = {
  PHONE_ASSISTED: "PHONE",
  WHATSAPP_ASSISTED: "WHATSAPP_VOICE",
  REQUEST_CONTACT: "PHONE",
};

/** Local-time `YYYY-MM-DDTHH:mm` for a datetime-local `min` attribute.
 * toISOString() would shift a Zimbabwean respondent's window by the UTC
 * offset, so build it from the local parts. */
function localDateTimeValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  );
}

export default function AppointmentRequestPage() {
  const params = useParams<{ token: string }>();
  const router = useRouter();
  const token = useRespondentFlow((s) => s.token) || params.token;
  const participationChoice = useRespondentFlow((s) => s.participationChoice);
  const [preferredDateTime, setPreferredDateTime] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const earliest = localDateTimeValue(new Date());

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const scheduled = new Date(preferredDateTime);
    // The browser's own `min` is bypassable and absent on some mobile
    // pickers, so re-check here. A past appointment lands silently in the
    // RA's queue as something already missed.
    if (Number.isNaN(scheduled.getTime())) {
      setError("Please choose a date and time.");
      return;
    }
    if (scheduled.getTime() < Date.now()) {
      setError("Please choose a time in the future.");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await requestAppointment({
        token,
        scheduledFor: scheduled.toISOString(),
        mode: MODE_BY_CHOICE[participationChoice ?? "REQUEST_CONTACT"],
      });
      router.push(`/i/${params.token}/done?requested=call`);
    } catch (err) {
      setError(respondentErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen flex flex-col">
      <StudyHeader />
      <section className="flex-1 flex items-center justify-center px-6 py-16">
        <Card className="max-w-md w-full space-y-6">
          <h2 className="font-semibold text-lg">When works best for you?</h2>
          <p className="text-text-muted text-sm">
            Let us know a preferred date and time, and a researcher will
            confirm with you.
          </p>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && <p className="text-danger text-sm">{error}</p>}
            <label className="block">
              <span className="sr-only">Preferred date and time</span>
              <input
                type="datetime-local"
                required
                min={earliest}
                value={preferredDateTime}
                onChange={(e) => setPreferredDateTime(e.target.value)}
                className="w-full rounded-md border border-border px-3 py-2.5 min-h-11"
              />
            </label>
            <Button type="submit" disabled={submitting} className="w-full">
              {submitting ? "Submitting…" : "Request this time"}
            </Button>
            <button
              type="button"
              onClick={() => router.push(`/i/${params.token}/choice`)}
              className="w-full text-sm text-text-muted underline min-h-11"
            >
              Choose a different way to take part
            </button>
          </form>
        </Card>
      </section>
    </main>
  );
}
