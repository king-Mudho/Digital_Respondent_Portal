"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { DisclaimerBanner } from "@/components/respondent/DisclaimerBanner";
import { StudyHeader } from "@/components/respondent/StudyHeader";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { submitExpertConsent, validateExpertToken, type ExpertInvitation } from "@/lib/api/expertRespondent";
import { respondentErrorMessage } from "@/lib/api/respondentErrors";

/**
 * The expert's consent, recorded on the portal before the questionnaire can open (AGENTS.md rule 6; the server
 * refuses the questionnaire link without it). Agreeing needs all three statements of section B ticked; declining
 * needs none.
 */
export default function ExpertConsentPage() {
  const params = useParams<{ token: string }>();
  const router = useRouter();
  const [data, setData] = useState<ExpertInvitation | null>(null);
  const [ticked, setTicked] = useState<boolean[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [declined, setDeclined] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    validateExpertToken(params.token)
      .then((res) => {
        setData(res);
        setTicked(res.consent_statements.map(() => false));
      })
      .catch((err: unknown) => setError(respondentErrorMessage(err)));
  }, [params.token]);

  async function decide(decision: "GIVEN" | "DECLINED") {
    if (!data) return;
    setSubmitting(true);
    setError(null);
    try {
      await submitExpertConsent({ token: params.token, decision, informationSheetVersion: data.information_sheet_version });
      if (decision === "GIVEN") router.push(`/ex/${params.token}/questionnaire`);
      else setDeclined(true);
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
        <Card className="max-w-md w-full space-y-5">
          {declined ? (
            <div className="text-center space-y-2">
              <h2 className="font-semibold text-lg">Thank you</h2>
              <p className="text-text-muted">
                Thank you for considering this invitation. Your decision not to take part has been recorded and no further
                action is needed.
              </p>
            </div>
          ) : !data ? (
            <p className={error ? "text-danger" : "text-text-muted"}>{error ?? "Loading…"}</p>
          ) : (
            <>
              <h2 className="font-semibold text-lg">Your consent</h2>
              <div className="space-y-3">
                {data.consent_statements.map((statement, i) => (
                  <label key={statement} className="flex items-start gap-3 text-sm">
                    <input
                      type="checkbox"
                      className="mt-1 h-4 w-4"
                      checked={ticked[i] ?? false}
                      onChange={(e) => setTicked((t) => t.map((v, j) => (j === i ? e.target.checked : v)))}
                    />
                    <span>{statement}</span>
                  </label>
                ))}
              </div>
              {error && <p role="alert" className="text-danger text-sm">{error}</p>}
              <div className="flex flex-col gap-3">
                <Button disabled={submitting || !ticked.every(Boolean)} onClick={() => decide("GIVEN")}>
                  {submitting ? "Recording your decision…" : "I agree to take part"}
                </Button>
                <Button variant="outline" disabled={submitting} onClick={() => decide("DECLINED")}>
                  I do not wish to take part
                </Button>
              </div>
              <button
                type="button"
                onClick={() => router.push(`/ex/${params.token}/information`)}
                className="w-full text-sm text-text-muted underline min-h-11"
              >
                Re-read the information
              </button>
              <DisclaimerBanner />
            </>
          )}
        </Card>
      </section>
    </main>
  );
}
