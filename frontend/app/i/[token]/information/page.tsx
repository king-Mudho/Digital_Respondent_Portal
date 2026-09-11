"use client";

import { useParams, useRouter } from "next/navigation";
import { StudyHeader } from "@/components/respondent/StudyHeader";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PARTICIPANT_INFORMATION_SHEET } from "@/lib/constants/participantInformation";

export default function ParticipantInformationPage() {
  const params = useParams<{ token: string }>();
  const router = useRouter();

  return (
    <main className="min-h-screen flex flex-col">
      <StudyHeader />
      <section className="flex-1 flex items-center justify-center px-6 py-16">
        <Card className="max-w-xl w-full space-y-6">
          <h2 className="font-semibold text-lg">Participant Information</h2>
          <div className="text-text-muted text-sm whitespace-pre-line leading-relaxed">
            {PARTICIPANT_INFORMATION_SHEET}
          </div>
          <Button className="w-full" onClick={() => router.push(`/i/${params.token}/consent`)}>
            Continue to consent
          </Button>
        </Card>
      </section>
    </main>
  );
}
