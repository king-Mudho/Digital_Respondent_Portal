import { redirect } from "next/navigation";

/** Conversations became Communications on 2026-10-12 (WhatsApp, SMS and email in one place); old links land there. */
export default function ConversationsPage() {
  redirect("/admin/communications");
}
