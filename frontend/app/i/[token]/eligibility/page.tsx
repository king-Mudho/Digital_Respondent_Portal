"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { StudyHeader } from "@/components/respondent/StudyHeader";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { NONE_OF_THESE, ROLE_CATEGORIES } from "@/lib/constants/roleCategories";
import { submitEligibility } from "@/lib/api/respondent";
import { useRespondentFlow } from "@/lib/store/respondentFlow";

export default function EligibilityPage() {
  const params = useParams<{ token: string }>();
  const router = useRouter();
  const token = useRespondentFlow((s) => s.token) || params.token;
  const setEligibility = useRespondentFlow((s) => s.setEligibility);

  const [fullName, setFullName] = useState("");
  const [roleCategory, setRoleCategory] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<"eligible" | "ineligible" | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      const isNoneOfThese = roleCategory === NONE_OF_THESE;
      const res = await submitEligibility({
        token,
        fullName,
        roleCategory: isNoneOfThese ? "" : roleCategory,
      });
      setEligibility(fullName, roleCategory, res.is_eligible);
      if (res.is_eligible) {
        router.push(`/i/${params.token}/information`);
      } else {
        setResult("ineligible");
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (result === "ineligible") {
    return (
      <main className="min-h-screen flex flex-col">
        <StudyHeader />
        <section className="flex-1 flex items-center justify-center px-6 py-16">
          <Card className="max-w-md w-full text-center space-y-4">
            <h2 className="font-semibold text-lg">Thank you for your time</h2>
            <p className="text-text-muted">
              This study is looking for a knowledgeable representative of the
              organisation&apos;s finances, operations or strategy. Could you
              please let us know the best person at your organisation to
              contact for this study, or ask them to reach out to the
              research team using the details in the original invitation?
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
          <div>
            <h2 className="font-semibold text-lg">A little about you</h2>
            <p className="text-text-muted text-sm">
              This helps us confirm you&apos;re the right person to answer on
              behalf of the organisation.
            </p>
          </div>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="full_name" className="block text-sm font-medium mb-1">
                Your full name
              </label>
              <input
                id="full_name"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="w-full rounded-md border border-border px-3 py-2.5 min-h-11"
              />
            </div>
            <div>
              <label htmlFor="role_category" className="block text-sm font-medium mb-1">
                Which best describes your role?
              </label>
              <select
                id="role_category"
                required
                value={roleCategory}
                onChange={(e) => setRoleCategory(e.target.value)}
                className="w-full rounded-md border border-border px-3 py-2.5 min-h-11 bg-surface"
              >
                <option value="" disabled>
                  Select one
                </option>
                {ROLE_CATEGORIES.map((role) => (
                  <option key={role.value} value={role.value}>
                    {role.label}
                  </option>
                ))}
                <option value={NONE_OF_THESE}>None of these describe me</option>
              </select>
            </div>
            <Button type="submit" disabled={submitting} className="w-full">
              {submitting ? "Checking…" : "Continue"}
            </Button>
          </form>
        </Card>
      </section>
    </main>
  );
}
