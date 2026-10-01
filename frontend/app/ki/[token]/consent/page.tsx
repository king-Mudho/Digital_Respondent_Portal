"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { DisclaimerBanner } from "@/components/respondent/DisclaimerBanner";
import { StudyHeader } from "@/components/respondent/StudyHeader";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { submitKIIConsent } from "@/lib/api/kiiRespondent";
import { respondentErrorMessage } from "@/lib/api/respondentErrors";
import { KII_PARTICIPANT_INFORMATION_SHEET_VERSION } from "@/lib/constants/kiiParticipantInformation";

export default function KIIConsentPage() {
  const params = useParams<{ token: string }>();
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [declined, setDeclined] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleDecision(decision: "GIVEN" | "DECLINED") {
    setSubmitting(true);
    setError(null);
    try {
      await submitKIIConsent({
        token: params.token,
        decision,
        informationSheetVersion: KII_PARTICIPANT_INFORMATION_SHEET_VERSION,
      });
      if (decision === "GIVEN") {
        router.push(`/ki/${params.token}/kobo-redirect`);
      } else {
        setDeclined(true);
      }
    } catch (err) {
      setError(respondentErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  if (declined) {
    return (
      <main className="min-h-screen flex flex-col">
        <StudyHeader />
        <section className="flex-1 flex items-center justify-center px-6 py-16">
          <Card className="max-w-md w-full text-center space-y-4">
            <h2 className="font-semibold text-lg">Thank you</h2>
            <p className="text-text-muted">
              Thank you for considering this interview. Your decision not to
              take part has been recorded and no further action is needed.
              If you change your mind, you can use the link you were sent to
              return to this point.
            </p>
          </Card>
        </section>
      </main>
    );
  }

  return (
    <main className="min-h-screen flex flex-col">
      <StudyHeader />
      <section className="flex-1 flex items-center justify-center px-6 py-16">
        <Card className="max-w-md w-full space-y-6">
          <h2 className="font-semibold text-lg">Your consent</h2>
          <p className="text-text-muted text-sm">
            By choosing &quot;I agree to take part&quot; below, you confirm
            you have read the participant information and voluntarily agree
            to take part in this interview.
          </p>
          {error && <p className="text-danger text-sm">{error}</p>}
          <div className="flex flex-col gap-3">
            <Button disabled={submitting} onClick={() => handleDecision("GIVEN")}>
              {submitting ? "Recording your decision…" : "I agree to take part"}
            </Button>
            <Button
              variant="outline"
              disabled={submitting}
              onClick={() => handleDecision("DECLINED")}
            >
              I do not wish to take part
            </Button>
          </div>
          <button
            type="button"
            onClick={() => router.push(`/ki/${params.token}/information`)}
            className="w-full text-sm text-text-muted underline min-h-11"
          >
            Re-read the participant information
          </button>
          <DisclaimerBanner />
        </Card>
      </section>
    </main>
  );
}
