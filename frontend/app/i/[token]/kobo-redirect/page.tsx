"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { StudyHeader } from "@/components/respondent/StudyHeader";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { getKoboRedirectUrl } from "@/lib/api/respondent";
import { PARTICIPANT_INFORMATION_SHEET_VERSION } from "@/lib/constants/participantInformation";
import { useRespondentFlow } from "@/lib/store/respondentFlow";

export default function KoboRedirectPage() {
  const params = useParams<{ token: string }>();
  const router = useRouter();
  const token = useRespondentFlow((s) => s.token) || params.token;
  const roleCategory = useRespondentFlow((s) => s.roleCategory);
  const [formUrl, setFormUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getKoboRedirectUrl({
      token,
      administrationMode: "01",
      respondentRoleCategory: roleCategory,
      consentVersion: PARTICIPANT_INFORMATION_SHEET_VERSION,
    })
      .then((res) => {
        if (cancelled) return;
        setFormUrl(res.kobo_form_url);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(
          err instanceof ApiError
            ? err.message
            : "We couldn't open the questionnaire right now. Please try again shortly.",
        );
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, roleCategory]);

  return (
    <main className="min-h-screen flex flex-col">
      <StudyHeader />
      <section className="flex-1 flex items-center justify-center px-6 py-16">
        <Card className="max-w-md w-full text-center space-y-4">
          {error ? (
            <p className="text-danger">{error}</p>
          ) : formUrl ? (
            <>
              <p className="text-text-muted">
                Thank you. You&apos;re ready to begin the questionnaire.
              </p>
              <Button className="w-full" onClick={() => window.open(formUrl, "_self")}>
                Start the questionnaire
              </Button>
            </>
          ) : (
            <p className="text-text-muted">Preparing your questionnaire…</p>
          )}
        </Card>
      </section>
    </main>
  );
}
