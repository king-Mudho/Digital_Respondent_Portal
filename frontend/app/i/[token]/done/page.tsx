import { DisclaimerBanner } from "@/components/respondent/DisclaimerBanner";
import { StudyHeader } from "@/components/respondent/StudyHeader";
import { Card } from "@/components/ui/card";

/**
 * R10 -- neutral completion/thank you. No provisional ABI score, band, or
 * financing recommendation is ever shown here (docs/10_INVITATION_AND_
 * CONSENT.md, docs/18_DATA_PRIVACY_AND_COMPLIANCE.md).
 */
export default function DonePage() {
  return (
    <main className="min-h-screen flex flex-col">
      <StudyHeader />
      <section className="flex-1 flex items-center justify-center px-6 py-16">
        <Card className="max-w-md w-full text-center space-y-4">
          <h2 className="font-semibold text-lg">Thank you</h2>
          <p className="text-text-muted">
            Thank you for your time and participation in this study. If you
            have any questions, please contact the research team using the
            details in your original invitation.
          </p>
          <DisclaimerBanner />
        </Card>
      </section>
    </main>
  );
}
