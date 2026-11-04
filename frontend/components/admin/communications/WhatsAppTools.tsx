"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import type { MediaOptions } from "@/lib/api/communications";

export interface SharedContact {
  name: string;
  number: string;
  note: string;
}

const IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png"];
const GALLERY_ACCEPT = "image/jpeg,image/png,video/mp4,video/3gpp";
// Firefox records Ogg, Chrome/Edge WebM (the server turns it into Ogg), Safari MP4: all reach WhatsApp as voice notes.
const RECORDING_TYPES = ["audio/ogg;codecs=opus", "audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
const MAX_RECORDING_SECONDS = 300;

function extension(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot >= 0 ? name.slice(dot).toLowerCase() : "";
}

/** Why WhatsApp would refuse this file, before it is uploaded; the server checks again by the file's contents. */
export function fileProblem(file: File, media: MediaOptions): string {
  const ext = extension(file.name);
  if (ext === ".heic" || ext === ".heif") return `${file.name}: iPhone HEIC photos can't go on WhatsApp. Save it as JPG first.`;
  if (ext === ".mov") return `${file.name}: MOV videos can't go on WhatsApp. Save it as MP4 first.`;
  if (!media.extensions.includes(ext)) return `${file.name}: WhatsApp doesn't take ${ext || "this kind of"} files.`;
  const limit = IMAGE_EXTENSIONS.includes(ext) ? media.image_max_mb : media.max_mb;
  if (file.size > limit * 1048576) return `${file.name} is ${(file.size / 1048576).toFixed(1)} MB; WhatsApp takes up to ${limit} MB.`;
  return "";
}

function clock(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

/**
 * The WhatsApp tools under the message box (2026-11-04): documents, photos and videos (the phone's gallery opens on
 * a phone), a voice note recorded here, and a contact card. They only appear when a written WhatsApp could go --
 * inside 24 hours of the person's own last message -- because WhatsApp refuses the rest.
 */
export function WhatsAppTools({
  media,
  files,
  onFiles,
  busy,
  onSendRecording,
  onShareContact,
}: {
  media: MediaOptions;
  files: File[];
  onFiles: (files: File[], problem: string) => void;
  busy: boolean;
  onSendRecording: (blob: Blob, type: string) => Promise<boolean>;
  onShareContact: (contact: SharedContact) => Promise<boolean>;
}) {
  const docInput = useRef<HTMLInputElement>(null);
  const galleryInput = useRef<HTMLInputElement>(null);
  const [panel, setPanel] = useState<"" | "voice" | "contact">("");

  const add = (list: FileList | null) => {
    if (!list) return;
    const picked = [...files, ...Array.from(list)].slice(0, media.files_per_send);
    const problem = picked.map((f) => fileProblem(f, media)).find(Boolean) ?? "";
    const tooMany = files.length + list.length > media.files_per_send ? `Send at most ${media.files_per_send} files at a time.` : "";
    onFiles(picked.filter((f) => !fileProblem(f, media)), problem || tooMany);
  };

  const closeOnSuccess = async (sending: Promise<boolean>) => {
    const ok = await sending;
    if (ok) setPanel("");
    return ok;
  };

  const documents = media.extensions.filter((e) => !IMAGE_EXTENSIONS.includes(e) && ![".mp4", ".3gp"].includes(e)).join(",");

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5" aria-label="Send something else on WhatsApp">
        <ToolButton onClick={() => docInput.current?.click()} disabled={busy}>Document</ToolButton>
        <ToolButton onClick={() => galleryInput.current?.click()} disabled={busy}>Photos &amp; videos</ToolButton>
        <ToolButton onClick={() => setPanel(panel === "voice" ? "" : "voice")} active={panel === "voice"} disabled={busy}>Voice note</ToolButton>
        <ToolButton onClick={() => setPanel(panel === "contact" ? "" : "contact")} active={panel === "contact"} disabled={busy}>Contact</ToolButton>
        <input ref={docInput} type="file" multiple accept={documents} className="hidden" onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
        <input ref={galleryInput} type="file" multiple accept={GALLERY_ACCEPT} className="hidden" onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
      </div>

      {files.length > 0 && (
        <ul className="flex flex-wrap gap-1.5" aria-label="Files to send">
          {files.map((f, i) => (
            <li key={`${f.name}-${i}`} className="flex items-center gap-1.5 rounded-md border border-border bg-bg px-2 py-1 text-xs">
              <span className="max-w-[12rem] truncate">{f.name}</span>
              <span className="tabular-nums text-text-muted">{f.size >= 1048576 ? `${(f.size / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(f.size / 1024))} KB`}</span>
              <button type="button" aria-label={`Remove ${f.name}`} className="text-text-muted hover:text-danger" onClick={() => onFiles(files.filter((_, j) => j !== i), "")}>
                ×
              </button>
            </li>
          ))}
        </ul>
      )}

      {panel === "voice" && <Recorder busy={busy} onSend={(blob, type) => closeOnSuccess(onSendRecording(blob, type))} />}
      {panel === "contact" && <ContactForm busy={busy} onSend={(c) => closeOnSuccess(onShareContact(c))} />}
    </div>
  );
}

function ToolButton({ children, onClick, disabled, active }: { children: React.ReactNode; onClick: () => void; disabled?: boolean; active?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-pressed={active}
      className={`rounded-full border px-2.5 py-1 text-xs disabled:opacity-50 ${active ? "border-header bg-header text-white" : "border-border hover:bg-bg"}`}
    >
      {children}
    </button>
  );
}

function Recorder({ busy, onSend }: { busy: boolean; onSend: (blob: Blob, type: string) => Promise<boolean> }) {
  const [state, setState] = useState<"idle" | "recording" | "done">("idle");
  const [seconds, setSeconds] = useState(0);
  const [result, setResult] = useState<{ blob: Blob; url: string } | null>(null);
  const [problem, setProblem] = useState("");
  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopTimer = () => {
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
  };
  useEffect(() => () => {
    stopTimer();
    recorder.current?.stream.getTracks().forEach((t) => t.stop());
  }, []);
  useEffect(() => () => { if (result) URL.revokeObjectURL(result.url); }, [result]);
  useEffect(() => {
    if (state === "recording" && seconds >= MAX_RECORDING_SECONDS) recorder.current?.stop();
  }, [seconds, state]);

  const start = async () => {
    setProblem("");
    const type = typeof MediaRecorder !== "undefined" ? RECORDING_TYPES.find((t) => MediaRecorder.isTypeSupported(t)) : undefined;
    if (!type || !navigator.mediaDevices?.getUserMedia) {
      setProblem("This browser can't record sound here. Use Chrome, Edge, Firefox or Safari.");
      return;
    }
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setProblem("The microphone wasn't allowed. Allow it in the browser's address bar, then try again.");
      return;
    }
    chunks.current = [];
    const r = new MediaRecorder(stream, { mimeType: type });
    r.ondataavailable = (e) => e.data.size && chunks.current.push(e.data);
    r.onstop = () => {
      stopTimer();
      stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(chunks.current, { type: r.mimeType || type });
      setResult({ blob, url: URL.createObjectURL(blob) });
      setState("done");
    };
    recorder.current = r;
    r.start();
    setSeconds(0);
    setState("recording");
    timer.current = setInterval(() => setSeconds((s) => s + 1), 1000);
  };

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border border-border bg-bg p-2.5">
      {state === "idle" && <Button type="button" variant="outline" onClick={start} className="min-h-8 px-3 py-1 text-xs">Start recording</Button>}
      {state === "recording" && (
        <>
          <span className="flex items-center gap-1.5 text-xs font-medium text-danger" role="status">
            <span className="h-2 w-2 animate-pulse rounded-full bg-danger motion-reduce:animate-none" aria-hidden /> Recording {clock(seconds)}
          </span>
          <Button type="button" onClick={() => recorder.current?.stop()} className="min-h-8 px-3 py-1 text-xs">Stop</Button>
          <span className="text-[11px] text-text-muted">Up to {MAX_RECORDING_SECONDS / 60} minutes</span>
        </>
      )}
      {state === "done" && result && (
        <>
          <audio controls src={result.url} className="h-8 max-w-[16rem]" />
          <span className="text-xs tabular-nums text-text-muted">{clock(seconds)}</span>
          <Button type="button" disabled={busy} onClick={() => onSend(result.blob, result.blob.type)} className="min-h-8 px-3 py-1 text-xs">
            {busy ? "Sending…" : "Send voice note"}
          </Button>
          <button type="button" className="text-xs text-text-muted underline" onClick={() => { setResult(null); setState("idle"); }}>
            Record again
          </button>
        </>
      )}
      {problem && <p role="alert" className="w-full text-xs text-danger">{problem}</p>}
    </div>
  );
}

function ContactForm({ busy, onSend }: { busy: boolean; onSend: (c: SharedContact) => Promise<boolean> }) {
  const [c, setC] = useState<SharedContact>({ name: "", number: "", note: "" });
  return (
    <div className="space-y-2 rounded-md border border-border bg-bg p-2.5">
      <p className="text-xs text-text-muted">Sent as a short card; WhatsApp lets them tap the number to chat, call or save it.</p>
      <div className="flex flex-wrap gap-2">
        <input aria-label="Contact name" placeholder="Name" value={c.name} onChange={(e) => setC({ ...c, name: e.target.value })}
               className="min-w-0 flex-1 rounded-md border border-border bg-surface px-2 py-1.5 text-xs" />
        <input aria-label="Contact number" placeholder="+263 77 123 4567" value={c.number} inputMode="tel" onChange={(e) => setC({ ...c, number: e.target.value })}
               className="min-w-0 flex-1 rounded-md border border-border bg-surface px-2 py-1.5 text-xs" />
      </div>
      <input aria-label="Note" placeholder="Note (optional), e.g. their role" value={c.note} onChange={(e) => setC({ ...c, note: e.target.value })}
             className="w-full rounded-md border border-border bg-surface px-2 py-1.5 text-xs" />
      <Button type="button" disabled={busy || !c.name.trim() || c.number.replace(/\D/g, "").length < 7} onClick={() => onSend(c)} className="min-h-8 px-3 py-1 text-xs">
        {busy ? "Sending…" : "Send contact"}
      </Button>
    </div>
  );
}
