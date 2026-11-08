"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { StudyHeader } from "@/components/respondent/StudyHeader";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { validateExpertToken, type ExpertInvitation } from "@/lib/api/expertRespondent";
import { respondentErrorMessage } from "@/lib/api/respondentErrors";

/** Section A of the expert questionnaire, from the server (apps/experts/instrument.py), read before consenting. */
export default function ExpertInformationPage() {
  const params = useParams<{ token: string }>();
  const router = useRouter();
  const [data, setData] = useState<ExpertInvitation | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    validateExpertToken(params.token).then(setData).catch((err: unknown) => setError(respondentErrorMessage(err)));
  }, [params.token]);

  return (
    <main className="min-h-screen flex flex-col">
      <StudyHeader />
      <section className="flex-1 flex items-center justify-center px-6 py-16">
        <Card className="max-w-xl w-full space-y-5">
          {error ? (
            <p className="text-danger">{error}</p>
          ) : !data ? (
            <p className="text-text-muted">Loading…</p>
          ) : (
            <>
              <div>
                <p className="text-xs uppercase tracking-wide text-text-muted">Agribusiness Bankability Index (ABI)</p>
                <h2 className="font-semibold text-lg">Information for invited experts</h2>
                <p className="text-sm text-text-muted">
                  Dear {data.expert_name}, please read this before deciding whether to take part. Your Expert ID is{" "}
                  <span className="font-mono">{data.expert_id}</span>.
                </p>
              </div>
              <div className="space-y-3 text-sm leading-relaxed">
                {data.information.map((part) => (
                  <p key={part.title}>
                    <span className="font-medium">{part.title}.</span> <span className="text-text-muted">{part.text}</span>
                  </p>
                ))}
                <p className="text-xs text-text-muted">{data.ethics_line}</p>
              </div>
              <Button className="w-full" onClick={() => router.push(`/ex/${params.token}/consent`)}>
                Continue to consent
              </Button>
            </>
          )}
        </Card>
      </section>
    </main>
  );
}
