"use client";

import Link from "next/link";
import { useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { IfRole, IfScreen } from "@/components/admin/RoleGate";
import { Pagination, usePaging, SearchBox, type Paginated } from "@/components/admin/Pagination";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";

interface SampleCase {
  id: number;
  sample_id: string;
  organisation_name: string;
  organisation_master_id: string;
  sample_type: string;
  status: string;
  workflow_status: string | null;
}

const VERIFICATION_STEPS: Record<string, { to: string; label: string }> = {
  S00: { to: "S01", label: "S00 Selected → S01 Verification required" },
  S01: { to: "S02", label: "S01 Verification required → S02 Organisation verified" },
  S02: { to: "S03", label: "S02 Organisation verified → S03 Eligible respondent identified" },
};

/**
 * Moves every Main case at one verification step to the next. All 400 cases
 * start at S00, and a case's status only follows its respondent (and
 * reminders are only offered) from S03 onward -- one case at a time that was
 * about 1,200 clicks. Each case still gets its own audited transition.
 */
function BulkVerificationPanel() {
  const queryClient = useQueryClient();
  const [from, setFrom] = useState("S00");
  const [result, setResult] = useState<string | null>(null);
  const { data: counts } = useQuery({
    queryKey: ["sample-cases-at-step", from],
    queryFn: () => adminFetch<Paginated<SampleCase>>(`/sample-cases/?sample_type=MAIN&workflow_status=${from}&page=1`),
  });
  const count = counts?.count ?? 0;
  const move = useMutation({
    mutationFn: () =>
      adminFetch<{ moved: number }>("/sample-cases/bulk-transition/", {
        method: "POST",
        body: JSON.stringify({ from_status: from }),
      }),
    onSuccess: (data) => {
      setResult(`Moved ${data.moved} case${data.moved === 1 ? "" : "s"} to ${VERIFICATION_STEPS[from].to}.`);
      queryClient.invalidateQueries({ queryKey: ["sample-cases"] });
      queryClient.invalidateQueries({ queryKey: ["sample-cases-at-step"] });
    },
    onError: (err) => setResult(err instanceof Error ? err.message : "Could not move the cases."),
  });

  return (
    <Card className="mb-4 space-y-2">
      <h3 className="font-medium text-sm">Move cases through verification</h3>
      <div className="flex flex-wrap items-center gap-2">
        <label className="text-sm w-full sm:w-auto min-w-0">
          <span className="sr-only">Verification step</span>
          <select
            value={from}
            onChange={(e) => {
              setFrom(e.target.value);
              setResult(null);
            }}
            className="w-full sm:w-auto max-w-full rounded-md border border-border px-3 py-2 bg-surface text-sm"
          >
            {Object.entries(VERIFICATION_STEPS).map(([key, step]) => (
              <option key={key} value={key}>
                {step.label}
              </option>
            ))}
          </select>
        </label>
        <Button
          variant="outline"
          disabled={count === 0 || move.isPending}
          onClick={() => {
            if (window.confirm(`Move all ${count} Main cases at ${from} to ${VERIFICATION_STEPS[from].to}?`)) {
              move.mutate();
            }
          }}
        >
          {move.isPending ? "Moving…" : `Move all ${count}`}
        </Button>
      </div>
      {result && <p className="text-sm text-text-muted">{result}</p>}
    </Card>
  );
}

interface ContactRA {
  id: number;
  username: string;
  full_name: string;
}

const PROVINCES: Array<[string, string]> = [
  ["BULAWAYO", "Bulawayo"], ["HARARE", "Harare"], ["MANICALAND", "Manicaland"],
  ["MASHONALAND_CENTRAL", "Mashonaland Central"], ["MASHONALAND_EAST", "Mashonaland East"],
  ["MASHONALAND_WEST", "Mashonaland West"], ["MASVINGO", "Masvingo"], ["MATABELELAND_NORTH", "Matabeleland North"],
  ["MATABELELAND_SOUTH", "Matabeleland South"], ["MIDLANDS", "Midlands"],
];

const raName = (ra: ContactRA) => (ra.full_name ? `${ra.full_name} (${ra.username})` : ra.username);

/**
 * Hands Main cases to a Contact RA in bulk (added 2026-09-15). All 400
 * started on one shared account; one case page at a time that was 400
 * dropdowns. "How many" splits a big province between several RAs.
 */
function BulkAssignmentPanel() {
  const queryClient = useQueryClient();
  const [from, setFrom] = useState("any");
  const [province, setProvince] = useState("");
  const [limit, setLimit] = useState("");
  const [to, setTo] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const { data: ras } = useQuery({
    queryKey: ["contact-ras"],
    queryFn: () => adminFetch<{ results: ContactRA[] }>("/auth/contact-ras/"),
  });
  const filters = {
    from,
    province,
    limit: limit ? Number(limit) : null,
    to_ra: to === "none" ? null : to ? Number(to) : null,
  };
  const { data: preview } = useQuery({
    queryKey: ["bulk-assign-preview", filters],
    queryFn: () =>
      adminFetch<{ count: number }>("/sample-cases/bulk-assign/", {
        method: "POST",
        body: JSON.stringify({ ...filters, preview: true }),
      }),
    enabled: to !== "",
  });
  const count = preview?.count ?? 0;
  const target = to === "none" ? "nobody (unassigned)" : raName(ras?.results.find((r) => String(r.id) === to) ?? { id: 0, username: "", full_name: "" });
  const move = useMutation({
    mutationFn: () =>
      adminFetch<{ moved: number }>("/sample-cases/bulk-assign/", { method: "POST", body: JSON.stringify(filters) }),
    onSuccess: (data) => {
      setResult(`Moved ${data.moved} case${data.moved === 1 ? "" : "s"} to ${target}.`);
      queryClient.invalidateQueries({ queryKey: ["bulk-assign-preview"] });
      queryClient.invalidateQueries({ queryKey: ["sample-cases"] });
    },
    onError: (err) => setResult(err instanceof Error ? err.message : "Could not move the cases."),
  });
  const select = "w-full sm:w-auto max-w-full rounded-md border border-border px-3 py-2 bg-surface text-sm";

  return (
    <Card className="mb-4 space-y-2">
      <h3 className="font-medium text-sm">Reassign cases</h3>
      <div className="flex flex-wrap items-end gap-2">
        <label className="text-xs text-text-muted w-full sm:w-auto min-w-0">
          From
          <select value={from} onChange={(e) => { setFrom(e.target.value); setResult(null); }} className={`${select} block mt-1`}>
            <option value="any">Anyone</option>
            <option value="unassigned">Unassigned</option>
            {ras?.results.map((ra) => <option key={ra.id} value={ra.id}>{raName(ra)}</option>)}
          </select>
        </label>
        <label className="text-xs text-text-muted w-full sm:w-auto min-w-0">
          Province
          <select value={province} onChange={(e) => { setProvince(e.target.value); setResult(null); }} className={`${select} block mt-1`}>
            <option value="">All provinces</option>
            {PROVINCES.map(([code, label]) => <option key={code} value={code}>{label}</option>)}
          </select>
        </label>
        <label className="text-xs text-text-muted w-full sm:w-28 min-w-0">
          How many
          <input
            type="number"
            min={1}
            value={limit}
            placeholder="All"
            onChange={(e) => { setLimit(e.target.value); setResult(null); }}
            className={`${select} block mt-1 sm:w-28`}
          />
        </label>
        <label className="text-xs text-text-muted w-full sm:w-auto min-w-0">
          To
          <select value={to} onChange={(e) => { setTo(e.target.value); setResult(null); }} className={`${select} block mt-1`}>
            <option value="">Choose a Contact RA…</option>
            {ras?.results.map((ra) => <option key={ra.id} value={ra.id}>{raName(ra)}</option>)}
            <option value="none">Nobody (unassign)</option>
          </select>
        </label>
        <Button
          variant="outline"
          disabled={!to || count === 0 || move.isPending}
          onClick={() => {
            if (window.confirm(`Move ${count} Main case${count === 1 ? "" : "s"} to ${target}?`)) move.mutate();
          }}
        >
          {move.isPending ? "Moving…" : to ? `Move ${count} case${count === 1 ? "" : "s"}` : "Move cases"}
        </Button>
      </div>
      <p className="text-xs text-text-muted">
        Cases move in Sample ID order. To split a large province, move part of it with &quot;How many&quot;, then the rest to the next RA.
      </p>
      {result && <p className="text-sm text-text-muted">{result}</p>}
    </Card>
  );
}

export default function SampleRegisterPage() {
  const [sampleType, setSampleType] = useState("MAIN");
  const [search, setSearch] = useState("");
  const { page, setPage, pageSize, setPageSize } = usePaging();

  const { data, isLoading } = useQuery({
    queryKey: ["sample-cases", sampleType, search, page, pageSize],
    queryFn: () =>
      adminFetch<Paginated<SampleCase>>(
        `/sample-cases/?sample_type=${sampleType}&page=${page}&page_size=${pageSize}` +
          (search ? `&search=${encodeURIComponent(search)}` : ""),
      ),
    // Without this the table blanks to "Loading…" on every keystroke and
    // every page step, which makes the register feel broken.
    placeholderData: keepPreviousData,
  });

  function changeFilter(fn: () => void) {
    fn();
    setPage(1); // page 3 of Main is rarely page 3 of Reserve
  }

  return (
    <AdminShell backHref="/admin/dashboard" backLabel="Dashboard">
      <div className="flex items-center justify-between gap-4 flex-wrap mb-4">
        <h2 className="font-semibold text-xl">
          {sampleType === "MAIN" ? "Main-400 Register" : "Reserve Register"}
        </h2>
        <div className="flex items-center gap-3 flex-wrap">
          <SearchBox
            value={search}
            onChange={(v) => changeFilter(() => setSearch(v))}
            placeholder="Search ID or organisation"
          />
          <label className="text-sm text-text-muted">
            <span className="sr-only">Sample type</span>
            <select
              value={sampleType}
              onChange={(e) => changeFilter(() => setSampleType(e.target.value))}
              className="rounded-md border border-border px-3 py-2 bg-surface text-sm"
            >
              <option value="MAIN">Main</option>
              <option value="RESERVE">Reserve</option>
            </select>
          </label>
          {/* Cases are created from an organisation, so this is the route
              in -- but only for the roles that hold that screen. */}
          <IfScreen path="/admin/organisations">
            <Link href="/admin/organisations">
              <Button variant="outline">Register organisation</Button>
            </Link>
          </IfScreen>
        </div>
      </div>
      {sampleType === "MAIN" && (
        <IfRole roles={["PI_ADMIN", "FIELD_COORDINATOR"]}>
          <BulkVerificationPanel />
          <BulkAssignmentPanel />
        </IfRole>
      )}
      <Card>
        {isLoading || !data ? (
          <p className="text-text-muted">Loading…</p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-text-muted">
                    <th className="py-2 pr-4">Sample ID</th>
                    <th className="py-2 pr-4">Master ID</th>
                    <th className="py-2 pr-4">Organisation</th>
                    <th className="py-2 pr-4">Status</th>
                    <th className="py-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((sc) => (
                    <tr key={sc.id} className="border-t border-border">
                      <td className="py-2 pr-4 font-mono text-xs">{sc.sample_id}</td>
                      <td className="py-2 pr-4 font-mono text-xs">{sc.organisation_master_id}</td>
                      <td className="py-2 pr-4">{sc.organisation_name}</td>
                      <td className="py-2 pr-4">
                        <span className="rounded-full bg-bg border border-border px-2 py-0.5 text-xs">
                          {sc.workflow_status ?? sc.status}
                        </span>
                      </td>
                      <td className="py-2">
                        <Link href={`/admin/sample/${sc.sample_id}`} className="text-header underline text-xs">
                          View
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {data.results.length === 0 && (
                <p className="text-text-muted text-sm py-4">
                  {search ? `No cases match "${search}".` : "No cases found."}
                </p>
              )}
            </div>
            <Pagination page={page} count={data.count} onPageChange={setPage} pageSize={pageSize} onPageSizeChange={setPageSize} label="cases" />
          </>
        )}
      </Card>
    </AdminShell>
  );
}
