import { RESEARCH_DISCLAIMER } from "@/lib/constants/disclaimers";

export function DisclaimerBanner() {
  return (
    <p className="text-sm text-text-muted border-t border-border pt-4 mt-6">
      {RESEARCH_DISCLAIMER}
    </p>
  );
}
