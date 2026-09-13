"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AdminShell } from "@/components/admin/AdminShell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { adminFetch } from "@/lib/api/admin";

const MODES = ["TEAMS", "ZOOM", "MEET", "WHATSAPP_VOICE", "WHATSAPP_VIDEO", "PHONE", "FACE_TO_FACE"];

export default function NewKIIRecordPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    stakeholder_category: "",
    participant_name: "",
    participant_role: "",
    preferred_mode: "PHONE",
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const record = await adminFetch<{ id: number }>("/kii/", {
        method: "POST",
        body: JSON.stringify(form),
      });
      router.push(`/admin/kii/${record.id}`);
    } catch (err) {
      // Without this a rejected POST left the form looking untouched,
      // with no indication anything had gone wrong.
      setError(err instanceof ApiError ? err.message : "Could not create the KII record.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AdminShell backHref="/admin/kii" backLabel="KII Register">
      <h2 className="font-semibold text-xl mb-4">New KII Record</h2>
      <Card className="max-w-lg">
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && <p className="text-danger text-sm">{error}</p>}
          <div>
            <label className="block text-sm font-medium mb-1">Stakeholder category</label>
            <input
              required
              value={form.stakeholder_category}
              onChange={(e) => setForm((f) => ({ ...f, stakeholder_category: e.target.value }))}
              className="w-full rounded-md border border-border px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Participant name</label>
            <input
              required
              value={form.participant_name}
              onChange={(e) => setForm((f) => ({ ...f, participant_name: e.target.value }))}
              className="w-full rounded-md border border-border px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Participant role</label>
            <input
              required
              value={form.participant_role}
              onChange={(e) => setForm((f) => ({ ...f, participant_role: e.target.value }))}
              className="w-full rounded-md border border-border px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Preferred mode</label>
            <select
              value={form.preferred_mode}
              onChange={(e) => setForm((f) => ({ ...f, preferred_mode: e.target.value }))}
              className="w-full rounded-md border border-border px-3 py-2 bg-surface"
            >
              {MODES.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
          <Button type="submit" disabled={submitting}>
            {submitting ? "Creating…" : "Create KII record"}
          </Button>
        </form>
      </Card>
    </AdminShell>
  );
}
