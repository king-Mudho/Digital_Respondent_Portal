"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { login } from "@/lib/api/admin";

export default function AdminLoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(username, password);
      router.push("/admin/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Sign in failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen flex flex-col">
      <header className="bg-header text-white px-6 py-4">
        <p className="text-xs uppercase tracking-wide text-white/70">
          Chinhoyi University of Technology
        </p>
        <h1 className="font-semibold">ABF-FST Research Operations Centre</h1>
      </header>
      <section className="flex-1 flex items-center justify-center px-6 py-16">
        <Card className="max-w-sm w-full space-y-6">
          <h2 className="font-semibold text-lg">Internal sign in</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="username" className="block text-sm font-medium mb-1">
                Username
              </label>
              <input
                id="username"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full rounded-md border border-border px-3 py-2.5 min-h-11"
              />
            </div>
            <div>
              <label htmlFor="password" className="block text-sm font-medium mb-1">
                Password
              </label>
              <input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-md border border-border px-3 py-2.5 min-h-11"
              />
            </div>
            {error && <p className="text-danger text-sm">{error}</p>}
            <Button type="submit" disabled={submitting} className="w-full">
              {submitting ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </Card>
      </section>
    </main>
  );
}
