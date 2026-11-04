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
  /** They have written back (not counting an automatic greeting); somebody has called them (2026-11-04). */
  replied?: boolean;
  called?: boolean;
}

/** What the list can be narrowed to by what happened (backend communications.STATUS_FILTERS), with counts. */
export type StatusFilter = "" | "read" | "unread" | "no_report" | "replied" | "no_reply" | "called" | "not_called";

export interface StatusFilterOption {
  key: Exclude<StatusFilter, "">;
  label: string;
  count: number;
}

export interface ThreadPage {
  count: number;
  page: number;
  page_size: number;
  results: ThreadRow[];
  unknown_waiting: number;
  status_filters?: StatusFilterOption[];
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
  /** Documents, pictures, videos and voice notes the study sent on WhatsApp (2026-11-04). */
  attachments?: InAttachment[];
}

export interface InAttachment {
  id: number;
  kind: "VOICE" | "IMAGE" | "VIDEO" | "CONTACT" | "DOCUMENT" | "OTHER";
  label: string;
  content_type: string;
  contact: string;
  error: string;
  size: number;
  url: string;
  filename?: string;
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
  /** WhatsApp voice notes, pictures, shared contacts and files (2026-10-14); url is relative to the API proxy. */
  attachments?: InAttachment[];
  /** AUTO: a business WhatsApp's automatic greeting, shown but not waiting (2026-10-20). */
  reply_kind: "" | "YES" | "NO" | "PHONE" | "AUTO";
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

export interface DialNumber {
  number: string;
  whatsapp_link: string;
  tel: string;
}

export interface Person {
  name: string;
  role: string;
  phone: string;
  whatsapp: string;
  email: string;
  eligible: boolean | null;
  gatekeeper?: string;
  numbers?: DialNumber[];
}

export interface ProgressRow {
  label: string;
  value: string;
  at: string;
  detail: string;
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
  details?: { label: string; value: string }[];
  public_contacts?: string;
  source_url?: string;
  other_emails?: string[];
  progress?: ProgressRow[];
}

export interface MediaOptions {
  available: boolean;
  extensions: string[];
  image_max_mb: number;
  max_mb: number;
  files_per_send: number;
  caption_max: number;
}

export type CallChannel = "PHONE" | "WHATSAPP_CALL" | "WHATSAPP_VIDEO";

/** The call buttons: every number with its links, and what a call can be logged as (2026-11-04). */
export interface CallOptions {
  can_log: boolean;
  ident: string;
  numbers: (DialNumber & { person: string })[];
  outcomes: { value: string; label: string }[];
  channels: { value: CallChannel; label: string }[];
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
  media?: MediaOptions;
}

export interface ComposerData {
  can_write: boolean;
  blocked: string;
  whatsapp: ChannelOption;
  sms: ChannelOption;
  email: ChannelOption;
  actions: { key: "introduction" | "invitation"; label: string; href?: string }[];
  max_length: number;
  /** A WhatsApp or SMS message longer than this goes out as numbered parts (2026-10-17). */
  part_max?: number;
}

/** How many WhatsApp/SMS messages a written text goes out as: the server splits at paragraph and sentence breaks into
 *  numbered parts of at most `partMax` characters, so this is an estimate a part either way. */
export function messageParts(length: number, partMax = 1500): number {
  return length <= partMax ? 1 : Math.ceil(length / (partMax - 40));
}

export interface ThreadData {
  subject: ContactCardData;
  items: TimelineItem[];
  composer: ComposerData;
  calls?: CallOptions;
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
  attachments?: InAttachment[];
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
