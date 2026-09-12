"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { logout } from "@/lib/api/admin";
import { cn } from "@/lib/utils/cn";

const LINKS = [
  { href: "/admin/dashboard", label: "Executive" },
  { href: "/admin/dashboard/sampling", label: "Sampling" },
  { href: "/admin/dashboard/contact", label: "Contact" },
  { href: "/admin/dashboard/kii-documents", label: "KII/Doc Dashboard" },
  { href: "/admin/sample", label: "Main-400 Register" },
  { href: "/admin/organisations", label: "Organisations" },
  { href: "/admin/appointments", label: "Appointments" },
  { href: "/admin/qa", label: "QA Queue" },
  { href: "/admin/kii", label: "KII Register" },
  { href: "/admin/documents", label: "Documents" },
  { href: "/admin/reserve", label: "Reserve Activation" },
  { href: "/admin/cost", label: "Cost" },
  { href: "/admin/audit", label: "Audit Log" },
  { href: "/admin/export", label: "Export" },
];

export function AdminNav() {
  const pathname = usePathname();
  const router = useRouter();

  return (
    <nav className="bg-header text-white">
      <div className="px-6 py-3 flex items-center justify-between">
        <p className="font-semibold">ABF-FST Research Operations Centre</p>
        <div className="flex items-center gap-4">
          <Link href="/admin/account" className="text-sm text-white/80 hover:text-white">
            Change password
          </Link>
          <button
            onClick={async () => {
              await logout();
              router.replace("/admin/login");
            }}
            className="text-sm text-white/80 hover:text-white"
          >
            Sign out
          </button>
        </div>
      </div>
      <div className="px-6 flex gap-4 overflow-x-auto border-t border-white/10 text-sm">
        {LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={cn(
              "py-2 whitespace-nowrap border-b-2 border-transparent",
              pathname === link.href && "border-accent font-medium",
            )}
          >
            {link.label}
          </Link>
        ))}
      </div>
    </nav>
  );
}
