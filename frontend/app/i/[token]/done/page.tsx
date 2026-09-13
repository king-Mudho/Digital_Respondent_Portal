import { DisclaimerBanner } from "@/components/respondent/DisclaimerBanner";
import { StudyHeader } from "@/components/respondent/StudyHeader";
import { Card } from "@/components/ui/card";

/**
 * R10 -- neutral completion/thank you. No provisional ABI score, band, or
 * financing recommendation is ever shown here (docs/10_INVITATION_AND_
 * CONSENT.md, docs/18_DATA_PRIVACY_AND_COMPLIANCE.md).
 *
 * Two routes end here and they mean different things. Someone who asked
 * for a researcher to call them has *not* finished taking part, and told
 * only "thank you for your participation" would reasonably conclude it
 * was over and not expect the call. `?requested=call` distinguishes them.
 */
export default async function DonePage({
  searchParams,
}: {
  searchParams: Promise<{ requested?: string }>;
}) {
  const { requested } = await searchParams;
  const awaitingCall = requested === "call";

  return (
    <main className="min-h-screen flex flex-col">
      <StudyHeader />
      <section className="flex-1 flex items-center justify-center px-6 py-16">
        <Card className="max-w-md w-full text-center space-y-4">
          <h2 className="font-semibold text-lg">
            {awaitingCall ? "Your request has been sent" : "Thank you"}
          </h2>
          <p className="text-text-muted">
            {awaitingCall
              ? "Thank you. A researcher will be in touch to confirm a time that works for you. There's nothing else you need to do for now — if you need to change anything, contact the research team using the details in your original invitation."
              : "Thank you for your time and participation in this study. If you have any questions, please contact the research team using the details in your original invitation."}
          </p>
          <DisclaimerBanner />
        </Card>
      </section>
    </main>
  );
}
