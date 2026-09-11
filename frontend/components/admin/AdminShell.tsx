"use client";

import { useRequireAuth } from "@/hooks/useRequireAuth";
import { AdminNav } from "./AdminNav";

export function AdminShell({ children }: { children: React.ReactNode }) {
  const authChecked = useRequireAuth();

  if (!authChecked) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <p className="text-text-muted">Checking session…</p>
      </main>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      <AdminNav />
      <main className="flex-1 px-6 py-6">{children}</main>
    </div>
  );
}
