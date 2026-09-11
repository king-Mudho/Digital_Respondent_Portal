"use client";

import { useParams, useRouter } from "next/navigation";
import { StudyHeader } from "@/components/respondent/StudyHeader";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useRespondentFlow } from "@/lib/store/respondentFlow";

export default function ConfirmOrganisationPage() {
  const params = useParams<{ token: string }>();
  const router = useRouter();
  const organisationConfirmation = useRespondentFlow((s) => s.organisationConfirmation);

  if (!organisationConfirmation) {
    // Direct navigation without validating first -- re-run validation.
    router.replace(`/i/${params.token}`);
    return null;
  }

  return (
    <main className="min-h-screen flex flex-col">
      <StudyHeader />
      <section className="flex-1 flex items-center justify-center px-6 py-16">
        <Card className="max-w-md w-full text-center space-y-6">
          <p className="text-lg text-text">{organisationConfirmation}</p>
          <div className="flex flex-col gap-3">
            <Button onClick={() => router.push(`/i/${params.token}/eligibility`)}>
              Yes, that&apos;s correct
            </Button>
            <p className="text-sm text-text-muted">
              If this isn&apos;t right, please contact the research team using the
              details in your invitation message rather than continuing.
            </p>
          </div>
        </Card>
      </section>
    </main>
  );
}
