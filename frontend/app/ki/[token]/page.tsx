"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { StudyHeader } from "@/components/respondent/StudyHeader";
import { Card } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { validateKIIToken } from "@/lib/api/kiiRespondent";

const ERROR_MESSAGES: Record<string, string> = {
  token_invalid: "This invitation link is not valid. Please check the link you were sent.",
  token_expired: "This invitation link has expired. Please contact the research team for a new one.",
  token_revoked: "This invitation has been revoked. Please contact the research team if you believe this is a mistake.",
};

/**
 * KII self-service invitation entry point -- the KII equivalent of
 * app/i/[token]/page.tsx, validating the token before routing on. No
 * Zustand store here (unlike the Main-400 flow): the token is the only
 * state this short flow needs, and it's already in the URL.
 */
export default function KIIInvitationValidatePage() {
  const params = useParams<{ token: string }>();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    validateKIIToken(params.token)
      .then(() => {
        if (cancelled) return;
        router.replace(`/ki/${params.token}/information`);
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
          ) : (
            <p className="text-text-muted">Checking your invitation…</p>
          )}
        </Card>
      </section>
    </main>
  );
}
