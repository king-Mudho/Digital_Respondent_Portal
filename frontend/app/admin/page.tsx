"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { adminFetch } from "@/lib/api/admin";

/**
 * /admin is just an entry point -- send each role to its own first screen
 * rather than to /admin/dashboard, which four of the eight roles (Contact,
 * QUAN QA, KII and Documentary RA) are refused.
 */
export default function AdminIndexPage() {
  const router = useRouter();
  useEffect(() => {
    adminFetch<{ landing_path: string }>("/auth/me/")
      .then((me) => router.replace(me.landing_path))
      .catch(() => router.replace("/admin/login"));
  }, [router]);
  return null;
}
