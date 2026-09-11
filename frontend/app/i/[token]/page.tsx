"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { StudyHeader } from "@/components/respondent/StudyHeader";
import { Card } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { validateToken } from "@/lib/api/respondent";
import { useRespondentFlow } from "@/lib/store/respondentFlow";

const ERROR_MESSAGES: Record<string, string> = {
  token_invalid: "This invitation link is not valid. Please check the link you were sent.",
  token_expired: "This invitation link has expired. Please contact the research team for a new one.",
  token_revoked: "This invitation has been revoked. Please contact the research team if you believe this is a mistake.",
};

export default function InvitationValidatePage() {
  const params = useParams<{ token: string }>();
  const router = useRouter();
  const setToken = useRespondentFlow((s) => s.setToken);
  const setOrganisationConfirmation = useRespondentFlow((s) => s.setOrganisationConfirmation);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    validateToken(params.token)
      .then((res) => {
        if (cancelled) return;
        setToken(params.token);
        setOrganisationConfirmation(res.organisation_name_confirmation);
        router.replace(`/i/${params.token}/confirm`);
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
