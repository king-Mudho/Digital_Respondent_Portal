"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";

interface QueueSubmission {
  id: number;
  sample_id: string;
  kobo_submission_uuid: string;
  administration_mode: string;
  qa_status: string;
  submitted_at: string;
  completion_seconds: number | null;
}

export default function QAQueuePage() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["qa-queue"],
    queryFn: () => adminFetch<{ results: QueueSubmission[] } | QueueSubmission[]>("/qa/queue/"),
  });
  const [notes, setNotes] = useState<Record<number, string>>({});

  const decide = useMutation({
    mutationFn: ({ id, decision, note }: { id: number; decision: string; note: string }) =>
      adminFetch(`/qa/submission/${id}/decision/`, {
        method: "POST",
        body: JSON.stringify({ decision, note }),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["qa-queue"] }),
  });

  const items = Array.isArray(data) ? data : data?.results ?? [];

  return (
    <AdminShell>
      <h2 className="font-semibold text-xl mb-4">QUAN QA Queue</h2>
      {isLoading ? (
        <p className="text-text-muted">Loading…</p>
      ) : items.length === 0 ? (
        <Card>
          <p className="text-text-muted text-sm">No submissions pending QA decision.</p>
        </Card>
      ) : (
        <div className="space-y-4">
          {items.map((submission) => (
            <Card key={submission.id} className="space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-mono text-sm">{submission.sample_id}</p>
                  <p className="text-xs text-text-muted">
                    Submitted {new Date(submission.submitted_at).toLocaleString()} · Mode{" "}
                    {submission.administration_mode} ·{" "}
                    {submission.completion_seconds
                      ? `${Math.round(submission.completion_seconds / 60)} min`
                      : "duration unknown"}
                  </p>
                </div>
                <span className="rounded-full bg-bg border border-border px-2 py-0.5 text-xs">
                  {submission.qa_status}
                </span>
              </div>
              <textarea
                placeholder="Note (required)"
                value={notes[submission.id] ?? ""}
                onChange={(e) => setNotes((prev) => ({ ...prev, [submission.id]: e.target.value }))}
                className="w-full rounded-md border border-border px-3 py-2 text-sm"
                rows={2}
              />
              <div className="flex gap-2">
                <Button
                  onClick={() =>
                    decide.mutate({ id: submission.id, decision: "ACCEPT", note: notes[submission.id] ?? "" })
                  }
                >
                  Accept
                </Button>
                <Button
                  variant="outline"
                  onClick={() =>
                    decide.mutate({ id: submission.id, decision: "QUERY", note: notes[submission.id] ?? "" })
                  }
                >
                  Re-query
                </Button>
                <Button
                  variant="outline"
                  onClick={() =>
                    decide.mutate({ id: submission.id, decision: "REJECT", note: notes[submission.id] ?? "" })
                  }
                >
                  Reject
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </AdminShell>
  );
}
