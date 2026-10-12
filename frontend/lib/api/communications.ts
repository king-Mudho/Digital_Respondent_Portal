/**
 * Types for the Communications screen (backend apps/messaging/communications.py, 2026-10-12).
 */

export type Channel = "WHATSAPP" | "SMS" | "EMAIL";
export type Kind = "main" | "kii";
export type DeliveryStatus = "QUEUED" | "SENT" | "DELIVERED" | "READ" | "UNDELIVERED" | "FAILED";

export interface ThreadRow {
  kind: Kind;
  id: number;
  ref: string;
  organisation: string;
  person: string;
  last_activity: string;
  waiting: boolean;
  last_sent_status: DeliveryStatus | "";
  channels: Channel[];
  last_message: { direction: "in" | "out" | ""; channel: Channel | ""; text: string };
}

export interface ThreadPage {
  count: number;
  page: number;
  page_size: number;
  results: ThreadRow[];
  unknown_waiting: number;
}

export interface OutItem {
  type: "out";
  id: string;
  at: string;
  channel: Channel;
  purpose: string;
  purpose_label: string;
  provider: "twilio" | "smtp" | "gmail_sent";
  status: DeliveryStatus;
  status_label: string;
  problem: string;
  subject: string;
  body: string;
  to: string;
  by: string;
  from_mailbox: boolean;
}

export interface InItem {
  type: "in";
  id: string;
  at: string;
  channel: Channel;
  from: string;
  subject: string;
  body: string;
  quoted: string;
  has_attachments: boolean;
  reply_kind: "" | "YES" | "NO";
  waiting: boolean;
  handled_by: string;
}

export interface EventItem {
  type: "event";
  id: string;
  at: string;
  text: string;
  detail: string;
  tone: "info" | "good" | "warn" | "muted";
}

export type TimelineItem = OutItem | InItem | EventItem;

export interface Person {
  name: string;
  role: string;
  phone: string;
  whatsapp: string;
  email: string;
  eligible: boolean | null;
}

export interface ContactCardData {
  kind: Kind;
  id: number;
  ref: string;
  organisation: string;
  person: string;
  status: string;
  sample_type: string;
  province: string;
  assigned_to: string;
  page: string;
  people: Person[];
}

export interface Recipient {
  value: string;
  label: string;
}

export interface ChannelOption {
  available: boolean;
  reason: string;
  recipients: Recipient[];
  reply_subject?: string;
}

export interface ComposerData {
  can_write: boolean;
  blocked: string;
  whatsapp: ChannelOption;
  sms: ChannelOption;
  email: ChannelOption;
  actions: { key: "introduction" | "invitation"; label: string; href?: string }[];
  max_length: number;
}

export interface ThreadData {
  subject: ContactCardData;
  items: TimelineItem[];
  composer: ComposerData;
}

export interface TemplateApproval {
  label: string;
  sid: string;
  name: string;
  status: string;
  category: string;
  rejection_reason: string;
}

export interface Summary {
  whatsapp: {
    configured: boolean;
    sender: string;
    left_today: number;
    daily_max: number;
    templates: TemplateApproval[];
    templates_approved: number;
  };
  sms: { configured: boolean; left_today: number; daily_max: number };
  email: {
    configured: boolean;
    from: string;
    inbox_sync: { configured: boolean; last_synced_at: string | null; last_error: string };
  };
  week: Record<Channel, Record<DeliveryStatus, number>>;
  received_week: Record<Channel, number>;
  waiting: number;
}

export interface UnknownMessage {
  message_id: number;
  id: string;
  at: string;
  channel: Channel;
  from: string;
  body: string;
  waiting: boolean;
  handled_by: string;
  can_reply: boolean;
}

export const CHANNEL_LABEL: Record<Channel, string> = { WHATSAPP: "WhatsApp", SMS: "SMS", EMAIL: "Email" };

export function threadKey(kind: Kind, id: number): string {
  return `${kind}-${id}`;
}

export function parseThreadKey(key: string | null): { kind: Kind; id: number } | null {
  const match = /^(main|kii)-(\d+)$/.exec(key ?? "");
  return match ? { kind: match[1] as Kind, id: Number(match[2]) } : null;
}

/** "14:05" today, "Mon 14:05" this week, "12 Oct" this year, "12 Oct 2025" otherwise. */
export function shortTime(iso: string): string {
  const when = new Date(iso);
  const now = new Date();
  const time = when.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  if (when.toDateString() === now.toDateString()) return time;
  const days = (now.getTime() - when.getTime()) / 86400000;
  if (days < 6) return `${when.toLocaleDateString([], { weekday: "short" })} ${time}`;
  const sameYear = when.getFullYear() === now.getFullYear();
  return when.toLocaleDateString([], { day: "numeric", month: "short", ...(sameYear ? {} : { year: "numeric" }) });
}

export function fullTime(iso: string): string {
  return new Date(iso).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}
