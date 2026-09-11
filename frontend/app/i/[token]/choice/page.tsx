"use client";

import { useParams, useRouter } from "next/navigation";
import { StudyHeader } from "@/components/respondent/StudyHeader";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useRespondentFlow } from "@/lib/store/respondentFlow";

const CHOICES = [
  {
    value: "SELF_NOW" as const,
    title: "Complete it myself now",
    description: "Fill in the questionnaire online, at your own pace (about 15-25 minutes).",
  },
  {
    value: "PHONE_ASSISTED" as const,
    title: "Have a researcher call me",
    description: "A researcher will call you at a time that suits you and go through it together.",
  },
  {
    value: "WHATSAPP_ASSISTED" as const,
    title: "Complete it via WhatsApp",
    description: "A researcher will guide you through it over a WhatsApp call.",
  },
  {
    value: "REQUEST_CONTACT" as const,
    title: "Ask someone to contact me another way",
    description: "We'll get in touch to find a way that works for you.",
  },
];

export default function ParticipationChoicePage() {
  const params = useParams<{ token: string }>();
  const router = useRouter();
  const setParticipationChoice = useRespondentFlow((s) => s.setParticipationChoice);

  function handleSelect(choice: (typeof CHOICES)[number]["value"]) {
    setParticipationChoice(choice);
    if (choice === "SELF_NOW") {
      router.push(`/i/${params.token}/kobo-redirect`);
    } else {
      router.push(`/i/${params.token}/appointment`);
    }
  }

  return (
    <main className="min-h-screen flex flex-col">
      <StudyHeader />
      <section className="flex-1 flex items-center justify-center px-6 py-16">
        <Card className="max-w-md w-full space-y-6">
          <h2 className="font-semibold text-lg">How would you like to take part?</h2>
          <div className="flex flex-col gap-3">
            {CHOICES.map((choice) => (
              <button
                key={choice.value}
                onClick={() => handleSelect(choice.value)}
                className="text-left rounded-md border border-border p-4 hover:border-accent transition-colors min-h-11"
              >
                <p className="font-medium">{choice.title}</p>
                <p className="text-sm text-text-muted">{choice.description}</p>
              </button>
            ))}
          </div>
        </Card>
      </section>
    </main>
  );
}
