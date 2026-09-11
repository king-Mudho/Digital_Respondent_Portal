"use client";

import { useQuery } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { StatCard } from "@/components/dashboard/StatCard";
import { adminFetch } from "@/lib/api/admin";

interface ContactDashboard {
  organisations_verified: number;
  eligible_respondents_identified: number;
  invitations_sent: number;
  invitations_opened: number;
  appointments_upcoming: number;
  refusals: number;
  unreachable_cases: number;
}

/** docs/16_DASHBOARDS_AND_REPORTING.md "Contact dashboard" -- counts only,
 * never an individual name. */
export default function ContactDashboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard-contact"],
    queryFn: () => adminFetch<ContactDashboard>("/dashboards/contact/"),
  });

  return (
    <AdminShell>
      <h2 className="font-semibold text-xl mb-4">Contact Dashboard</h2>
      {isLoading || !data ? (
        <p className="text-text-muted">Loading…</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard label="Organisations verified" value={data.organisations_verified} />
          <StatCard label="Eligible respondents identified" value={data.eligible_respondents_identified} />
          <StatCard label="Invitations sent" value={data.invitations_sent} />
          <StatCard label="Invitations opened" value={data.invitations_opened} />
          <StatCard label="Appointments upcoming" value={data.appointments_upcoming} />
          <StatCard label="Refusals" value={data.refusals} />
          <StatCard label="Unreachable cases" value={data.unreachable_cases} />
        </div>
      )}
    </AdminShell>
  );
}
