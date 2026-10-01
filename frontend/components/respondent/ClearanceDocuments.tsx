"use client";

import { useQuery } from "@tanstack/react-query";
import { clearanceDocumentFileUrl, fetchClearanceDocuments } from "@/lib/api/respondent";

/**
 * "Is this a genuine study?" -- the official letters that approved it, for a respondent who has opened
 * their own invitation link to check for themselves. Shown on the information step, before consent.
 * Renders nothing at all (not even a heading) if the PI hasn't marked any document public yet, so an
 * unconfigured study doesn't show an empty, oddly bare box.
 */
export function ClearanceDocuments({ token }: { token: string }) {
  const { data } = useQuery({
    queryKey: ["clearance-documents", token],
    queryFn: () => fetchClearanceDocuments(token),
    retry: false,
  });

  const documents = data?.results ?? [];
  if (documents.length === 0) return null;

  return (
    <section className="border border-border rounded-md p-4 space-y-3" aria-label="Verify this study">
      <h3 className="font-medium text-sm">How to verify this is a genuine study</h3>
      <p className="text-xs text-text-muted">
        This research has been formally approved. You can open the official letters below to check for
        yourself before you decide whether to take part.
      </p>
      <ul className="space-y-2">
        {documents.map((doc) => (
          <li key={doc.id} className="flex flex-wrap items-start justify-between gap-2 border-t border-border pt-2 first:border-t-0 first:pt-0">
            <div>
              <p className="text-sm">{doc.title}</p>
              <p className="text-xs text-text-muted">
                {doc.issuing_body}
                {doc.reference_number && <> · {doc.reference_number}</>}
                {doc.issue_date && <> · {doc.issue_date}</>}
              </p>
              {doc.description && <p className="text-xs text-text-muted mt-0.5">{doc.description}</p>}
            </div>
            <a
              href={clearanceDocumentFileUrl(token, doc.id)}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm underline text-header shrink-0"
            >
              View letter
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}
