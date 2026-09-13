import { AdminShell } from "@/components/admin/AdminShell";
import { IfRole } from "@/components/admin/RoleGate";
import { Card } from "@/components/ui/card";
import { RESEARCH_DISCLAIMER } from "@/lib/constants/disclaimers";

/**
 * A12 -- data-lock / analysis export. Required research disclaimer shown
 * on every export context (docs/18_DATA_PRIVACY_AND_COMPLIANCE.md).
 */
export default function ExportPage() {
  return (
    <AdminShell backHref="/admin/dashboard" backLabel="Dashboard">
      <h2 className="font-semibold text-xl mb-4">Data Export</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="space-y-3">
          <h3 className="font-medium">De-identified analysis export</h3>
          <p className="text-sm text-text-muted">
            CSV with no contact-identifying fields -- safe for analysis and
            sharing with the wider research team. Available to Analysts,
            Field Coordinators and the PI/Admin.
          </p>
          {/* eslint-disable-next-line @next/next/no-html-link-for-pages -- this is a file download from an API route, not page navigation; <Link> would try to client-route it. */}
          <a
            href="/api/proxy/export/analysis/"
            className="inline-block rounded-md bg-header text-white px-4 py-2.5 text-sm font-medium"
          >
            Download analysis export (CSV)
          </a>
        </Card>

        {/* Analysts and Field Coordinators reach this screen but the
            operational export is PI/Admin only -- showing them a button
            that always 403s is worse than not showing it. */}
        <IfRole roles={["PI_ADMIN"]}>
          <Card className="space-y-3">
            <h3 className="font-medium">Full operational export</h3>
            <p className="text-sm text-text-muted">
              Includes contact data (names, phone, email, gatekeeper details).
              Internal operations use only -- never distributed externally.
              PI/Admin only.
            </p>
            {/* eslint-disable-next-line @next/next/no-html-link-for-pages -- file download, not page navigation. */}
            <a
              href="/api/proxy/export/operational/"
              className="inline-block rounded-md bg-header text-white px-4 py-2.5 text-sm font-medium"
            >
              Download operational export (CSV)
            </a>
          </Card>
        </IfRole>
      </div>
      <p className="text-sm text-text-muted border-t border-border pt-4 mt-6 max-w-2xl">
        {RESEARCH_DISCLAIMER}
      </p>
    </AdminShell>
  );
}
