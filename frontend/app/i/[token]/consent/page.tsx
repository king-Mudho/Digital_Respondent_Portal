"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { DisclaimerBanner } from "@/components/respondent/DisclaimerBanner";
import { StudyHeader } from "@/components/respondent/StudyHeader";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { submitConsent } from "@/lib/api/respondent";
import { PARTICIPANT_INFORMATION_SHEET_VERSION } from "@/lib/constants/participantInformation";
import { useRespondentFlow } from "@/lib/store/respondentFlow";

export default function ConsentPage() {
  const params = useParams<{ token: string }>();
  const router = useRouter();
  const token = useRespondentFlow((s) => s.token) || params.token;
  const [submitting, setSubmitting] = useState(false);
  const [declined, setDeclined] = useState(false);

  async function handleDecision(decision: "GIVEN" | "DECLINED") {
    setSubmitting(true);
    try {
      await submitConsent({
        token,
        consentType: "PARTICIPATION",
        decision,
        informationSheetVersion: PARTICIPANT_INFORMATION_SHEET_VERSION,
      });
      if (decision === "GIVEN") {
        router.push(`/i/${params.token}/choice`);
      } else {
        setDeclined(true);
      }
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
              Thank you for considering this study. Your decision not to
              participate has been recorded and no further action is
              needed. If you change your mind, you can use the link in your
              original invitation to return to this point.
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
            to take part in this study.
          </p>
          <div className="flex flex-col gap-3">
            <Button disabled={submitting} onClick={() => handleDecision("GIVEN")}>
              I agree to take part
            </Button>
            <Button
              variant="outline"
              disabled={submitting}
              onClick={() => handleDecision("DECLINED")}
            >
              I do not wish to take part
            </Button>
          </div>
          <DisclaimerBanner />
        </Card>
      </section>
    </main>
  );
}
