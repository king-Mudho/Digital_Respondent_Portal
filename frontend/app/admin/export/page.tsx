import { AdminShell } from "@/components/admin/AdminShell";
import { Card } from "@/components/ui/card";
import { RESEARCH_DISCLAIMER } from "@/lib/constants/disclaimers";

/**
 * A12 -- data-lock / analysis export. Required research disclaimer shown
 * on every export context (docs/18_DATA_PRIVACY_AND_COMPLIANCE.md).
 */
export default function ExportPage() {
  return (
    <AdminShell>
      <h2 className="font-semibold text-xl mb-4">Data Export</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="space-y-3">
          <h3 className="font-medium">De-identified analysis export</h3>
          <p className="text-sm text-text-muted">
            CSV with no contact-identifying fields -- safe for analysis and
            sharing with the wider research team. Available to Analysts,
            Field Coordinators and the PI/Admin.
          </p>
          <a
            href="/api/proxy/export/analysis/"
            className="inline-block rounded-md bg-header text-white px-4 py-2.5 text-sm font-medium"
          >
            Download analysis export (CSV)
          </a>
        </Card>

        <Card className="space-y-3">
          <h3 className="font-medium">Full operational export</h3>
          <p className="text-sm text-text-muted">
            Includes contact data (names, phone, email, gatekeeper details).
            Internal operations use only -- never distributed externally.
            PI/Admin only.
          </p>
          <a
            href="/api/proxy/export/operational/"
            className="inline-block rounded-md bg-header text-white px-4 py-2.5 text-sm font-medium"
          >
            Download operational export (CSV)
          </a>
        </Card>
      </div>
      <p className="text-sm text-text-muted border-t border-border pt-4 mt-6 max-w-2xl">
        {RESEARCH_DISCLAIMER}
      </p>
    </AdminShell>
  );
}
