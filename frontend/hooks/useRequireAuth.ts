"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getSession } from "@/lib/api/admin";

export function useRequireAuth() {
  const router = useRouter();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getSession().then((session) => {
      if (cancelled) return;
      if (!session.authenticated) {
        router.replace("/admin/login");
      } else {
        setChecked(true);
      }
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return checked;
}
