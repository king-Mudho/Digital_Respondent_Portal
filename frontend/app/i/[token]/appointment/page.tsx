"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { StudyHeader } from "@/components/respondent/StudyHeader";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { requestAppointment } from "@/lib/api/respondent";
import { useRespondentFlow } from "@/lib/store/respondentFlow";

const MODE_BY_CHOICE: Record<string, string> = {
  PHONE_ASSISTED: "PHONE",
  WHATSAPP_ASSISTED: "WHATSAPP_VOICE",
  REQUEST_CONTACT: "PHONE",
};

export default function AppointmentRequestPage() {
  const params = useParams<{ token: string }>();
  const router = useRouter();
  const token = useRespondentFlow((s) => s.token) || params.token;
  const participationChoice = useRespondentFlow((s) => s.participationChoice);
  const [preferredDateTime, setPreferredDateTime] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await requestAppointment({
        token,
        scheduledFor: new Date(preferredDateTime).toISOString(),
        mode: MODE_BY_CHOICE[participationChoice ?? "REQUEST_CONTACT"],
      });
      router.push(`/i/${params.token}/done`);
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
            <input
              type="datetime-local"
              required
              value={preferredDateTime}
              onChange={(e) => setPreferredDateTime(e.target.value)}
              className="w-full rounded-md border border-border px-3 py-2.5 min-h-11"
            />
            <Button type="submit" disabled={submitting} className="w-full">
              {submitting ? "Submitting…" : "Request this time"}
            </Button>
          </form>
        </Card>
      </section>
    </main>
  );
}
