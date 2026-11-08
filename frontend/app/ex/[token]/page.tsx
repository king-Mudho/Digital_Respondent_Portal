"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { StudyHeader } from "@/components/respondent/StudyHeader";
import { Card } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { validateExpertToken } from "@/lib/api/expertRespondent";

const ERROR_MESSAGES: Record<string, string> = {
  token_invalid: "This invitation link is not valid. Please check the link you were sent.",
  token_expired: "This invitation link has expired. Please contact the research team for a new one.",
  token_revoked: "This invitation has been withdrawn. Please contact the research team if you believe this is a mistake.",
};

/**
 * An ABI panel expert's personal link (backend apps/experts, 2026-11-08). Checks the link, then goes to the
 * information for experts -- or straight to the questionnaire if they already consented, or says thank you if
 * their questionnaire has arrived.
 */
export default function ExpertInvitationPage() {
  const params = useParams<{ token: string }>();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [completed, setCompleted] = useState(false);

  useEffect(() => {
    let cancelled = false;
    validateExpertToken(params.token)
      .then((res) => {
        if (cancelled) return;
        if (res.completed) setCompleted(true);
        else router.replace(`/ex/${params.token}/${res.consented ? "questionnaire" : "information"}`);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const code = err instanceof ApiError ? err.code : "token_invalid";
        setError(ERROR_MESSAGES[code] ?? ERROR_MESSAGES.token_invalid);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.token]);

  return (
    <main className="min-h-screen flex flex-col">
      <StudyHeader />
      <section className="flex-1 flex items-center justify-center px-6 py-16">
        <Card className="max-w-md w-full text-center">
          {error ? (
            <>
              <h2 className="font-semibold text-lg mb-2 text-danger">Invitation not valid</h2>
              <p className="text-text-muted">{error}</p>
            </>
          ) : completed ? (
            <>
              <h2 className="font-semibold text-lg mb-2">Thank you</h2>
              <p className="text-text-muted">Your ratings have been received. Thank you for your contribution to the study.</p>
            </>
          ) : (
            <p className="text-text-muted">Checking your invitation…</p>
          )}
        </Card>
      </section>
    </main>
  );
}
