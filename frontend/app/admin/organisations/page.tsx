"use client";

import Link from "next/link";
import { useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { IfScreen, WriteOnly } from "@/components/admin/RoleGate";
import { Pagination, usePaging, SearchBox } from "@/components/admin/Pagination";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { adminFetch } from "@/lib/api/admin";

// Mirrors backend/apps/sampling/models.py -- Province/Actor Family/Size
// Class are the real, PI-approved stratification categories (2026-09-12,
// from the approved sampling register's own "Stratum Allocation" sheet).
// Entity type and value chain are deliberately free text below, not a
// dropdown -- the real register's data for those two is far richer than a
// small fixed list (hundreds of distinct, sometimes multi-valued entries).
const PROVINCES = [
  "HARARE", "BULAWAYO", "MANICALAND", "MASHONALAND_CENTRAL", "MASHONALAND_EAST",
  "MASHONALAND_WEST", "MASVINGO", "MATABELELAND_NORTH", "MATABELELAND_SOUTH", "MIDLANDS",
];
const ACTOR_FAMILIES = [
  "AGGREGATION_MARKET_RETAIL", "INPUTS_MECHANISATION", "PROCESSING_MANUFACTURING",
  "PRODUCER_PRIMARY", "SERVICES_ENABLING", "FINANCE_INSURANCE",
  "INSTITUTIONAL_COMMERCIAL_UNIT", "OTHER_VERIFY",
];
const SIZE_CLASSES = ["MICRO", "SME", "UNKNOWN", "LARGE_CORPORATE", "INSTITUTIONAL_OTHER"];

interface Organisation {
  id: number;
  master_id: string;
  name: string;
  entity_type: string;
  province: string;
  district: string;
  actor_family: string;
  value_chain: string;
  size_class: string;
  verification_status: string;
}

const EMPTY_ORG_FORM = {
  name: "",
  entity_type: "",
  province: PROVINCES[0],
  district: "",
  actor_family: ACTOR_FAMILIES[0],
  value_chain: "",
  size_class: SIZE_CLASSES[0],
};

const emptyEditForm = { name: "", district: "", entity_type: "", value_chain: "" };

export default function OrganisationsPage() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState(EMPTY_ORG_FORM);
  const [error, setError] = useState<string | null>(null);
  const [justCreated, setJustCreated] = useState<Organisation | null>(null);
  const [caseType, setCaseType] = useState("MAIN");
  const [search, setSearch] = useState("");
  const { page, setPage, pageSize, setPageSize } = usePaging();
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState(emptyEditForm);

  const { data: organisations, isLoading } = useQuery({
    queryKey: ["organisations", search, page, pageSize],
    queryFn: () =>
      adminFetch<{ count?: number; results: Organisation[] } | Organisation[]>(
        `/organisations/?page=${page}&page_size=${pageSize}` + (search ? `&search=${encodeURIComponent(search)}` : ""),
      ),
    placeholderData: keepPreviousData,
  });

  const createOrganisation = useMutation({
    mutationFn: () => adminFetch<Organisation>("/organisations/", { method: "POST", body: JSON.stringify(form) }),
    onSuccess: (org) => {
      setError(null);
      setJustCreated(org);
      setForm(EMPTY_ORG_FORM);
      queryClient.invalidateQueries({ queryKey: ["organisations"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Failed to register organisation."),
  });

  const createSampleCase = useMutation({
    mutationFn: (organisationId: number) =>
      adminFetch<{ sample_id: string }>("/sample-cases/", {
        method: "POST",
        body: JSON.stringify({ organisation: organisationId, sample_type: caseType }),
      }),
    onSuccess: (sampleCase) => {
      setError(null);
      setJustCreated(null);
      queryClient.invalidateQueries({ queryKey: ["organisations"] });
      window.location.href = `/admin/sample/${sampleCase.sample_id}`;
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Failed to create sample case."),
  });

  const updateOrganisation = useMutation({
    mutationFn: (id: number) =>
      adminFetch<Organisation>(`/organisations/${id}/`, { method: "PATCH", body: JSON.stringify(editForm) }),
    onSuccess: () => {
      setError(null);
      setEditingId(null);
      queryClient.invalidateQueries({ queryKey: ["organisations"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Could not save the correction."),
  });

  const startEditing = (org: Organisation) => {
    setEditingId(org.id);
    setEditForm({ name: org.name, district: org.district, entity_type: org.entity_type, value_chain: org.value_chain });
  };

  const orgList = Array.isArray(organisations) ? organisations : organisations?.results ?? [];
  const orgCount = Array.isArray(organisations) ? organisations.length : organisations?.count ?? 0;

  return (
    <AdminShell backHref="/admin/dashboard" backLabel="Dashboard">
      <h2 className="font-semibold text-xl mb-4">Register Organisation</h2>
      {error && <p className="text-danger text-sm mb-4">{error}</p>}

      <div className="space-y-6">
        <WriteOnly note={null}>
        <Card className="space-y-3">
          <h3 className="font-medium">New organisation</h3>
          <p className="text-text-muted text-xs">
            Master_ID is generated automatically from the province once saved.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <label className="text-sm space-y-1">
              <span className="block text-text-muted text-xs">Name</span>
              <input
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                className="w-full rounded-md border border-border px-2 py-1.5 text-sm"
              />
            </label>
            <label className="text-sm space-y-1">
              <span className="block text-text-muted text-xs">District</span>
              <input
                value={form.district}
                onChange={(e) => setForm((f) => ({ ...f, district: e.target.value }))}
                className="w-full rounded-md border border-border px-2 py-1.5 text-sm"
              />
            </label>
            <label className="text-sm space-y-1">
              <span className="block text-text-muted text-xs">Province</span>
              <select
                value={form.province}
                onChange={(e) => setForm((f) => ({ ...f, province: e.target.value }))}
                className="w-full rounded-md border border-border px-2 py-1.5 text-sm bg-surface"
              >
                {PROVINCES.map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </label>
            <label className="text-sm space-y-1">
              <span className="block text-text-muted text-xs">Entity type</span>
              <input
                value={form.entity_type}
                onChange={(e) => setForm((f) => ({ ...f, entity_type: e.target.value }))}
                placeholder="e.g. Small/Medium Enterprise (SME)"
                className="w-full rounded-md border border-border px-2 py-1.5 text-sm"
              />
            </label>
            <label className="text-sm space-y-1">
              <span className="block text-text-muted text-xs">Actor family</span>
              <select
                value={form.actor_family}
                onChange={(e) => setForm((f) => ({ ...f, actor_family: e.target.value }))}
                className="w-full rounded-md border border-border px-2 py-1.5 text-sm bg-surface"
              >
                {ACTOR_FAMILIES.map((a) => (
                  <option key={a} value={a}>{a}</option>
                ))}
              </select>
            </label>
            <label className="text-sm space-y-1">
              <span className="block text-text-muted text-xs">Value chain</span>
              <input
                value={form.value_chain}
                onChange={(e) => setForm((f) => ({ ...f, value_chain: e.target.value }))}
                placeholder="e.g. Horticulture"
                className="w-full rounded-md border border-border px-2 py-1.5 text-sm"
              />
            </label>
            <label className="text-sm space-y-1">
              <span className="block text-text-muted text-xs">Size class</span>
              <select
                value={form.size_class}
                onChange={(e) => setForm((f) => ({ ...f, size_class: e.target.value }))}
                className="w-full rounded-md border border-border px-2 py-1.5 text-sm bg-surface"
              >
                {SIZE_CLASSES.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </label>
          </div>
          <Button
            onClick={() => createOrganisation.mutate()}
            disabled={createOrganisation.isPending || !form.name || !form.district}
          >
            {createOrganisation.isPending ? "Registering…" : "Register organisation"}
          </Button>
        </Card>
        </WriteOnly>

        {justCreated && (
          <Card className="space-y-3">
            <h3 className="font-medium">
              {justCreated.name} registered — {justCreated.master_id}
            </h3>
            <p className="text-text-muted text-sm">Create its sample case now, or do it later from the list below.</p>
            <div className="flex flex-wrap items-end gap-2">
              <label className="text-sm space-y-1">
                <span className="block text-text-muted text-xs">Sample type</span>
                <select
                  value={caseType}
                  onChange={(e) => setCaseType(e.target.value)}
                  className="rounded-md border border-border px-2 py-1.5 text-sm bg-surface"
                >
                  <option value="MAIN">Main</option>
                  <option value="RESERVE">Reserve</option>
                </select>
              </label>
              <Button onClick={() => createSampleCase.mutate(justCreated.id)} disabled={createSampleCase.isPending}>
                {createSampleCase.isPending ? "Creating…" : "Create sample case"}
              </Button>
            </div>
          </Card>
        )}

        <Card>
          <div className="flex items-center justify-between gap-4 flex-wrap mb-3">
            <h3 className="font-medium">Registered organisations</h3>
            <SearchBox
              value={search}
              onChange={(v) => {
                setSearch(v);
                setPage(1);
              }}
              placeholder="Search name, Master ID or district"
            />
          </div>
          {isLoading ? (
            <p className="text-text-muted">Loading…</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-text-muted">
                    <th className="py-2 pr-4">Master ID</th>
                    <th className="py-2 pr-4">Name</th>
                    <th className="py-2 pr-4">Province</th>
                    <th className="py-2 pr-4">Verification</th>
                    <th className="py-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {orgList.map((org) =>
                    editingId === org.id ? (
                      <tr key={org.id} className="border-t border-border">
                        <td className="py-2 pr-4 font-mono text-xs align-top">{org.master_id}</td>
                        <td className="py-2 pr-4 align-top" colSpan={3}>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-lg">
                            <label className="text-xs space-y-1">
                              <span className="block text-text-muted">Name</span>
                              <input
                                value={editForm.name}
                                onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))}
                                className="w-full rounded-md border border-border px-2 py-1 text-sm"
                              />
                            </label>
                            <label className="text-xs space-y-1">
                              <span className="block text-text-muted">District</span>
                              <input
                                value={editForm.district}
                                onChange={(e) => setEditForm((f) => ({ ...f, district: e.target.value }))}
                                className="w-full rounded-md border border-border px-2 py-1 text-sm"
                              />
                            </label>
                            <label className="text-xs space-y-1">
                              <span className="block text-text-muted">Entity type</span>
                              <input
                                value={editForm.entity_type}
                                onChange={(e) => setEditForm((f) => ({ ...f, entity_type: e.target.value }))}
                                className="w-full rounded-md border border-border px-2 py-1 text-sm"
                              />
                            </label>
                            <label className="text-xs space-y-1">
                              <span className="block text-text-muted">Value chain</span>
                              <input
                                value={editForm.value_chain}
                                onChange={(e) => setEditForm((f) => ({ ...f, value_chain: e.target.value }))}
                                className="w-full rounded-md border border-border px-2 py-1 text-sm"
                              />
                            </label>
                          </div>
                          <p className="text-text-muted text-xs mt-2">
                            Province ({org.province}), actor family and size class can&rsquo;t be corrected here --
                            changing them could break Main-400/Reserve-400 sampling pairing. Ask the technical
                            administrator if one of those is genuinely wrong.
                          </p>
                        </td>
                        <td className="py-2 align-top">
                          <div className="flex flex-col gap-1">
                            <Button
                              onClick={() => updateOrganisation.mutate(org.id)}
                              disabled={updateOrganisation.isPending || !editForm.name.trim() || !editForm.district.trim()}
                            >
                              {updateOrganisation.isPending ? "Saving…" : "Save"}
                            </Button>
                            <button
                              onClick={() => setEditingId(null)}
                              className="text-text-muted underline text-xs"
                              disabled={updateOrganisation.isPending}
                            >
                              Cancel
                            </button>
                          </div>
                        </td>
                      </tr>
                    ) : (
                      <tr key={org.id} className="border-t border-border">
                        <td className="py-2 pr-4 font-mono text-xs">{org.master_id}</td>
                        <td className="py-2 pr-4">{org.name}</td>
                        <td className="py-2 pr-4">{org.province}</td>
                        <td className="py-2 pr-4">{org.verification_status}</td>
                        <td className="py-2">
                          <WriteOnly note={null}>
                            <div className="flex flex-col gap-1 items-start">
                              <button onClick={() => startEditing(org)} className="text-header underline text-xs">
                                Edit
                              </button>
                              <button
                                onClick={() => {
                                  setCaseType("MAIN");
                                  setJustCreated(org);
                                }}
                                className="text-header underline text-xs"
                              >
                                Create sample case
                              </button>
                            </div>
                          </WriteOnly>
                        </td>
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
              {orgList.length === 0 && (
                <p className="text-text-muted text-sm py-4">
                  {search ? `No organisations match "${search}".` : "No organisations registered yet."}
                </p>
              )}
              <Pagination page={page} count={orgCount} onPageChange={setPage} pageSize={pageSize} onPageSizeChange={setPageSize} label="organisations" />
            </div>
          )}
        </Card>

        <IfScreen path="/admin/sample">
          <p className="text-text-muted text-xs">
            Looking for an existing case? <Link href="/admin/sample" className="underline">Main-400 Register</Link>
          </p>
        </IfScreen>
      </div>
    </AdminShell>
  );
}
