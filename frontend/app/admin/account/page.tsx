"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { adminFetch } from "@/lib/api/admin";

export default function ChangePasswordPage() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const changePassword = useMutation({
    mutationFn: () =>
      adminFetch("/auth/change-password/", {
        method: "POST",
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      }),
    onSuccess: () => {
      setError(null);
      setSuccess(true);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    },
    onError: (err) => {
      setSuccess(false);
      setError(err instanceof ApiError ? err.message : "Failed to change password.");
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      setSuccess(false);
      setError("New password and confirmation do not match.");
      return;
    }
    changePassword.mutate();
  };

  return (
    <AdminShell backHref="/admin/dashboard" backLabel="Dashboard">
      <h2 className="font-semibold text-xl mb-4">Change Password</h2>
      <Card className="max-w-md">
        <form onSubmit={handleSubmit} className="space-y-3">
          {error && <p className="text-danger text-sm">{error}</p>}
          {success && <p className="text-success text-sm">Password changed successfully.</p>}
          <label className="block text-sm space-y-1">
            <span className="block text-text-muted text-xs">Current password</span>
            <input
              type="password"
              required
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="w-full rounded-md border border-border px-3 py-2 text-sm"
            />
          </label>
          <label className="block text-sm space-y-1">
            <span className="block text-text-muted text-xs">New password</span>
            <input
              type="password"
              required
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="w-full rounded-md border border-border px-3 py-2 text-sm"
            />
          </label>
          <label className="block text-sm space-y-1">
            <span className="block text-text-muted text-xs">Confirm new password</span>
            <input
              type="password"
              required
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full rounded-md border border-border px-3 py-2 text-sm"
            />
          </label>
          <Button type="submit" disabled={changePassword.isPending}>
            Change password
          </Button>
        </form>
      </Card>
    </AdminShell>
  );
}
