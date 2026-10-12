import { CHANNEL_LABEL, type Channel, type DeliveryStatus } from "@/lib/api/communications";

const CHANNEL_STYLE: Record<Channel, string> = {
  WHATSAPP: "text-success border-success",
  SMS: "text-accent border-accent",
  EMAIL: "text-header border-header",
};

/** A small outlined label naming the channel, coloured per channel so a mixed thread reads at a glance. */
export function ChannelBadge({ channel, className = "" }: { channel: Channel; className?: string }) {
  return (
    <span
      className={`inline-flex items-center rounded border px-1.5 py-px text-[10px] font-semibold uppercase tracking-wide ${CHANNEL_STYLE[channel]} ${className}`}
    >
      {CHANNEL_LABEL[channel]}
    </span>
  );
}

const TICK_TITLE: Record<DeliveryStatus, string> = {
  QUEUED: "Waiting to go",
  SENT: "Sent",
  DELIVERED: "Delivered to the phone",
  READ: "Read",
  UNDELIVERED: "Not delivered",
  FAILED: "Not sent",
};

/**
 * WhatsApp-style delivery marks: a clock while queued, one tick sent, two ticks delivered, two blue ticks read, a red
 * "!" when it did not arrive. Email only ever reaches "sent" (or a bounce), so it shows one tick at most.
 */
export function StatusTicks({ status, className = "" }: { status: DeliveryStatus | ""; className?: string }) {
  if (!status) return null;
  const title = TICK_TITLE[status];
  if (status === "UNDELIVERED" || status === "FAILED") {
    return (
      <span title={title} aria-label={title} className={`inline-flex h-4 w-4 items-center justify-center rounded-full bg-danger text-[10px] font-bold text-white ${className}`}>
        !
      </span>
    );
  }
  if (status === "QUEUED") {
    return (
      <svg viewBox="0 0 16 16" width="14" height="14" role="img" aria-label={title} className={`text-text-muted ${className}`}>
        <title>{title}</title>
        <circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" strokeWidth="1.5" />
        <path d="M8 4.5V8l2.5 1.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    );
  }
  const double = status === "DELIVERED" || status === "READ";
  const colour = status === "READ" ? "text-[#2f8fdc]" : "text-text-muted";
  return (
    <svg viewBox="0 0 20 14" width="18" height="13" role="img" aria-label={title} className={`${colour} ${className}`}>
      <title>{title}</title>
      <path d="M1.5 7.5l3.5 3.5L12 3.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      {double && <path d="M8.5 10.5l.5.5L16.5 3.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />}
    </svg>
  );
}
