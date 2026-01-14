"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import { BackgroundLines } from "@/components/ui/background-lines";
import {
  ArrowUpFromDot,
  Square,
  X,
  ChevronDown,
  ChevronUp,
  Brain,
  Wrench,
  Mic,
  MicOff,
  Loader2,
} from "lucide-react";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type SSEMessage = { event?: string; data?: any };

type InterruptPayload = {
  type: "review_required";
  payload: string;
};

type AgentActivity = {
  agent: string;
  tools: string[];
  preview: string;
};

type MessageActivity = {
  supervisorThoughts?: string;
  agents: AgentActivity[];
};

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  processSteps?: string[];
  detailsOpen?: boolean;
  interrupt?: InterruptPayload | null;
  activity?: MessageActivity;
};

function uid() {
  return Math.random().toString(16).slice(2) + Date.now().toString(16);
}

function safeJsonParse(x: any) {
  try {
    return typeof x === "string" ? JSON.parse(x) : x;
  } catch {
    return x;
  }
}

function parseSSE(buffer: string) {
  const normalized = buffer.replace(/\r\n/g, "\n");
  const parts = normalized.split("\n\n");
  const complete = parts.slice(0, -1);
  const rest = parts[parts.length - 1];

  const events: SSEMessage[] = complete.map((block) => {
    let event = "";
    const dataLines: string[] = [];

    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
    }

    const dataStr = dataLines.join("\n");
    let data: any = dataStr;
    try {
      data = JSON.parse(dataStr);
    } catch {}

    return { event, data };
  });

  return { events, rest };
}

function tryExtractResponseFromSupervisorJSON(jsonText: string): string | null {
  try {
    const obj = JSON.parse(jsonText);
    if (obj && typeof obj.response === "string") return obj.response;
  } catch {}
  return null;
}

function extractResponseFieldIncremental(jsonSoFar: string): string | null {
  const m = jsonSoFar.match(/"response"\s*:\s*"((?:\\.|[^"\\])*)/);
  if (!m) return null;
  const raw = m[1];
  try {
    return JSON.parse(`"${raw}"`);
  } catch {
    return raw;
  }
}

function extractThoughtsFieldIncremental(jsonSoFar: string): string | null {
  const m = jsonSoFar.match(/"thoughts"\s*:\s*"((?:\\.|[^"\\])*)/);
  if (!m) return null;
  const raw = m[1];
  try {
    return JSON.parse(`"${raw}"`);
  } catch {
    return raw;
  }
}

function prettyAgentName(agent: string) {
  return agent.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function normalizeOneLine(s: string) {
  return String(s).replace(/\s+/g, " ").trim();
}

function clampText(s: string, max = 240) {
  const t = normalizeOneLine(s);
  if (t.length <= max) return t;
  return t.slice(0, max).trimEnd() + "…";
}

function toolLabel(tool: string) {
  const t = (tool ?? "").trim();
  if (!t) return "";
  return t.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function cleanToolName(tool: string) {
  return (tool ?? "").trim();
}

function makeAgentPreview(raw: string) {
  if (!raw) return "";
  let t = String(raw);
  t = t.replace(/#{2,}\s+/g, "");
  t = t.replace(/\n{3,}/g, "\n\n").trim();
  if (t.length > 900) t = t.slice(0, 900).trimEnd() + "…";
  return t;
}

function dedupKeepOrder(arr: string[]) {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const x of arr) {
    const v = (x ?? "").trim();
    if (!v) continue;
    if (seen.has(v)) continue;
    seen.add(v);
    out.push(v);
  }
  return out;
}

function Markdown({ text }: { text: string }) {
  return (
    <div className="prose prose-neutral dark:prose-invert max-w-none prose-a:underline prose-a:underline-offset-2 prose-pre:bg-transparent prose-pre:p-0 prose-code:bg-neutral-100 dark:prose-code:bg-neutral-800 prose-code:px-1 prose-code:py-0.5 prose-code:rounded">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ node, ...props }) => <a {...props} target="_blank" rel="noreferrer" />,
          li: ({ node, ...props }) => <li {...props} className="my-1" />,
        }}
      >
        {text || ""}
      </ReactMarkdown>
    </div>
  );
}

function ToolChip({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center rounded-full border border-neutral-200 dark:border-neutral-800 bg-white/70 dark:bg-neutral-950/30 px-2 py-0.5 text-[11px] text-neutral-700 dark:text-neutral-200">
      {label}
    </span>
  );
}

function AgentCard({ name, tools, preview }: { name: string; tools: string[]; preview: string }) {
  return (
    <div className="rounded-2xl border border-neutral-200 dark:border-neutral-800 bg-white/70 dark:bg-neutral-950/30 p-3 shadow-[0_1px_0_rgba(0,0,0,0.03)]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs font-semibold text-neutral-900 dark:text-neutral-100 truncate">
            {name}
          </div>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {tools.length === 0 ? (
              <span className="text-[11px] text-neutral-500 dark:text-neutral-400">No tools</span>
            ) : (
              tools.map((t) => <ToolChip key={t} label={toolLabel(t)} />)
            )}
          </div>
        </div>

        <div className="shrink-0 flex items-center gap-1 text-[11px] text-neutral-500 dark:text-neutral-400">
          <Wrench size={14} className="opacity-70" />
          <span>{tools.length}</span>
        </div>
      </div>

      {preview ? (
        <div className="mt-3 rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white/60 dark:bg-neutral-950/20 p-3">
          <div className="text-[11px] text-neutral-500 dark:text-neutral-400 mb-2">
            Agent output (preview)
          </div>
          <div className="text-sm leading-6">
            <Markdown text={preview} />
          </div>
        </div>
      ) : (
        <div className="mt-3 text-[11px] text-neutral-500 dark:text-neutral-400">No output captured.</div>
      )}
    </div>
  );
}

export default function NewChat() {
  // If you ALWAYS want English transcription, set this to "en"
  // Otherwise leave null for auto-detect.
  const VOICE_LANGUAGE_HINT: string | null = null; // e.g. "en"

  const API_BASE = "http://backend:8000";

  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  // Sidebar
  const [processOpen, setProcessOpen] = useState(false);
  const [activeSteps, setActiveSteps] = useState<string[]>([]);

  // Review UI
  const [reviewText, setReviewText] = useState("");
  const [reviewMode, setReviewMode] = useState<"approve" | "change" | null>(null);

  // Voice UI
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordedChunksRef = useRef<BlobPart[]>([]);

  // Refs
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const threadIdRef = useRef<string>(uid());
  const activeAssistantIdRef = useRef<string | null>(null);

  const canSend = useMemo(() => input.trim().length > 0 && !isStreaming, [input, isStreaming]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (messages.length > 0) setTimeout(() => inputRef.current?.focus(), 50);
  }, [messages.length]);

  function stop() {
    abortRef.current?.abort();
  }

  function openProcess(steps: string[] | undefined) {
    setActiveSteps(steps ?? []);
    setProcessOpen(true);
  }

  function closeProcess() {
    setProcessOpen(false);
  }

  function toggleDetails(messageId: string) {
    setMessages((prev) => prev.map((m) => (m.id === messageId ? { ...m, detailsOpen: !m.detailsOpen } : m)));
  }

  async function transcribeWithBackend(file: Blob) {
    const fd = new FormData();
    fd.append("file", file, "recording.webm");
    if (VOICE_LANGUAGE_HINT) fd.append("language", VOICE_LANGUAGE_HINT);

    const res = await fetch(`${API_BASE}/audio/transcribe`, {
      method: "POST",
      body: fd,
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data?.error || `HTTP ${res.status}`);

    return {
      text: (data?.text as string) || "",
      language: (data?.language as string) || null,
    };
  }

  async function startRecording() {
    if (isRecording || isTranscribing || isStreaming) return;

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    recordedChunksRef.current = [];

    const mimeCandidates = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus"];
    const mimeType = mimeCandidates.find((m) => MediaRecorder.isTypeSupported(m)) || "";

    const mr = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    mediaRecorderRef.current = mr;

    mr.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) recordedChunksRef.current.push(e.data);
    };

    mr.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());

      const blob = new Blob(recordedChunksRef.current, { type: mr.mimeType || "audio/webm" });
      recordedChunksRef.current = [];

      if (!blob.size) return;

      try {
        setIsTranscribing(true);
        const { text } = await transcribeWithBackend(blob);

        const trimmed = (text || "").trim();
        if (!trimmed) return;

        // ✅ IMPORTANT: this is what you were missing:
        // send transcript as a real user message into the workflow
        await sendTextAsNewTurn(trimmed);
      } catch (e: any) {
        setMessages((prev) => [
          ...prev,
          { id: uid(), role: "assistant", content: `⚠️ Voice transcription failed: ${String(e?.message ?? e)}` },
        ]);
      } finally {
        setIsTranscribing(false);
      }
    };

    mr.start();
    setIsRecording(true);
  }

  function stopRecording() {
    if (!isRecording) return;
    setIsRecording(false);
    mediaRecorderRef.current?.stop();
  }

  async function streamTurn(opts: {
    message?: string;
    resume_action?: string;
    attachToAssistantId: string;
    createUserBubble: boolean;
  }) {
    const { message, resume_action, attachToAssistantId, createUserBubble } = opts;

    setIsStreaming(true);

    const processSteps: string[] = [];

    let inFinalSupervisorWindow = false;
    let finalSupervisorJsonBuffer = "";
    let extractedResponse = "";
    let extractedThoughts = "";

    const supervisorThoughtsRef = { value: "" };

    type AgentState = {
      agent: string;
      started: boolean;
      usedTool: boolean;
      tools: Set<string>;
      buffer: string;
      previewFinal: string;
      finalized: boolean;
    };

    const agentState = new Map<string, AgentState>();
    const agentOrder: string[] = [];
    let currentAgent: string | null = null;

    const ensureAgent = (agent: string) => {
      if (!agentState.has(agent)) {
        agentState.set(agent, {
          agent,
          started: false,
          usedTool: false,
          tools: new Set(),
          buffer: "",
          previewFinal: "",
          finalized: false,
        });
      }
      return agentState.get(agent)!;
    };

    const finalizeAgentIfNeeded = (agent: string) => {
      if (!agent || agent === "supervisor") return;
      const st = ensureAgent(agent);
      if (!st.usedTool) return;
      if (!st.finalized) {
        st.previewFinal = makeAgentPreview(st.buffer);
        st.finalized = true;
      }
    };

    const rebuildActivity = () => {
      const agents: AgentActivity[] = [];
      for (const a of agentOrder) {
        const st = agentState.get(a);
        if (!st || !st.usedTool) continue;
        const preview = st.finalized ? st.previewFinal : makeAgentPreview(st.buffer);
        agents.push({ agent: st.agent, tools: Array.from(st.tools), preview });
      }

      setMessages((prev) =>
        prev.map((m) =>
          m.id === attachToAssistantId
            ? { ...m, activity: { supervisorThoughts: supervisorThoughtsRef.value || undefined, agents } }
            : m
        )
      );
    };

    const setAssistantContent = (text: string) => {
      setMessages((prev) => prev.map((m) => (m.id === attachToAssistantId ? { ...m, content: text } : m)));
    };

    const setAssistantInterrupt = (interrupt: InterruptPayload | null) => {
      setMessages((prev) => prev.map((m) => (m.id === attachToAssistantId ? { ...m, interrupt } : m)));
    };

    const setAssistantProcess = (steps: string[]) => {
      setMessages((prev) => prev.map((m) => (m.id === attachToAssistantId ? { ...m, processSteps: steps } : m)));
    };

    // reset assistant bubble
    setMessages((prev) =>
      prev.map((m) =>
        m.id === attachToAssistantId
          ? {
              ...m,
              content: m.content ?? "",
              processSteps: m.processSteps ?? [],
              detailsOpen: m.detailsOpen ?? true,
              interrupt: null,
              activity: { agents: [] },
            }
          : m
      )
    );

    if (createUserBubble && message) {
      const userMsg: ChatMessage = { id: uid(), role: "user", content: message };
      setMessages((prev) => {
        const idx = prev.findIndex((x) => x.id === attachToAssistantId);
        if (idx === -1) return [...prev, userMsg];
        const copy = [...prev];
        copy.splice(idx, 0, userMsg);
        return copy;
      });
    }

    const ac = new AbortController();
    abortRef.current = ac;

    try {
      const res = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify({
          message: message ?? null,
          resume_action: resume_action ?? null,
          thread_id: threadIdRef.current,
        }),
        signal: ac.signal,
      });

      if (!res.ok || !res.body) throw new Error(`Stream failed: ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parsed = parseSSE(buffer);
        buffer = parsed.rest;

        for (const rawMsg of parsed.events) {
          const ev = rawMsg.event || "";
          const d = safeJsonParse(rawMsg.data);

          if (ev === "agent_start" && d?.agent) {
            const agent = String(d.agent);

            if (currentAgent && currentAgent !== agent) {
              finalizeAgentIfNeeded(currentAgent);
              rebuildActivity();
            }
            currentAgent = agent;

            if (agent === "supervisor") {
              processSteps.push("Supervisor started (planning)");
              inFinalSupervisorWindow = true;
              finalSupervisorJsonBuffer = "";
              extractedResponse = "";
              extractedThoughts = "";
              setAssistantContent("");
              rebuildActivity();
            } else {
              ensureAgent(agent).started = true;
              inFinalSupervisorWindow = false;
            }
            continue;
          }

          if (ev === "tool_call") {
            const agent = String(d?.agent ?? "unknown");
            const tool = cleanToolName(String(d?.tool ?? ""));
            if (!tool) continue;

            if (currentAgent && currentAgent !== agent) {
              finalizeAgentIfNeeded(currentAgent);
              currentAgent = agent;
            }

            if (agent === "supervisor") {
              processSteps.push(`Supervisor used tool "${toolLabel(tool)}"`);
            } else {
              const st = ensureAgent(agent);
              const before = st.tools.size;
              st.tools.add(tool);
              st.usedTool = true;
              if (before === 0) agentOrder.push(agent);

              processSteps.push(`${prettyAgentName(agent)} used tool "${toolLabel(tool)}"`);
              rebuildActivity();
            }
            continue;
          }

          if (ev === "token") {
            const agent = String(d?.agent ?? "unknown");
            const t = String(d?.text ?? "");

            if (agent === "supervisor" && inFinalSupervisorWindow) {
              finalSupervisorJsonBuffer += t;

              const maybeThoughts = extractThoughtsFieldIncremental(finalSupervisorJsonBuffer);
              if (maybeThoughts && maybeThoughts !== extractedThoughts) {
                extractedThoughts = maybeThoughts;
                supervisorThoughtsRef.value = extractedThoughts;
                rebuildActivity();
              }

              const maybeResponse = extractResponseFieldIncremental(finalSupervisorJsonBuffer);
              if (maybeResponse && maybeResponse !== extractedResponse) {
                extractedResponse = maybeResponse;
                setAssistantContent(extractedResponse);
              }
              continue;
            }

            if (agent && agent !== "supervisor") {
              const st = ensureAgent(agent);
              if (!st.usedTool) continue;
              st.buffer = (st.buffer + t).slice(-8000);
              if (st.buffer.length % 400 < 40) rebuildActivity();
            }
            continue;
          }

          if (ev === "interrupt") {
            const payload: InterruptPayload = {
              type: String(d?.type ?? "review_required") as "review_required",
              payload: String(d?.payload ?? ""),
            };

            if (currentAgent) finalizeAgentIfNeeded(currentAgent);
            rebuildActivity();

            setAssistantProcess(dedupKeepOrder(processSteps));
            setAssistantInterrupt(payload);

            setIsStreaming(false);
            abortRef.current = null;

            setReviewMode(null);
            setReviewText("");
            continue;
          }

          if (ev === "error") {
            const msg = String(d?.error ?? "Unknown error");
            setAssistantContent(`⚠️ ${clampText(msg, 300)}`);
            rebuildActivity();
            continue;
          }

          if (ev === "done") {
            if (currentAgent) finalizeAgentIfNeeded(currentAgent);

            if (!extractedResponse && finalSupervisorJsonBuffer) {
              const maybe = tryExtractResponseFromSupervisorJSON(finalSupervisorJsonBuffer);
              if (maybe) extractedResponse = maybe;
            }

            rebuildActivity();

            setMessages((prev) =>
              prev.map((m) =>
                m.id === attachToAssistantId
                  ? {
                      ...m,
                      content: extractedResponse || m.content || "—",
                      processSteps: dedupKeepOrder(processSteps),
                      interrupt: null,
                    }
                  : m
              )
            );
            continue;
          }
        }
      }
    } catch (e: any) {
      const aborted = e?.name === "AbortError";
      if (!aborted) {
        console.warn(e);
        setMessages((prev) =>
          prev.map((m) => (m.id === attachToAssistantId ? { ...m, content: "⚠️ Something went wrong while streaming." } : m))
        );
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  }

  async function sendTextAsNewTurn(text: string) {
    const question = (text || "").trim();
    if (!question || isStreaming) return;

    const assistantId = uid();
    activeAssistantIdRef.current = assistantId;

    const assistantMsg: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
      processSteps: [],
      detailsOpen: true,
      interrupt: null,
      activity: { agents: [] },
    };

    setMessages((prev) => [...prev, assistantMsg]);

    await streamTurn({
      message: question,
      resume_action: undefined,
      attachToAssistantId: assistantId,
      createUserBubble: true, // ✅ shows user bubble for transcript too
    });
  }

  async function sendNewQuestion() {
    await sendTextAsNewTurn(input);
    setInput("");
  }

  async function resumeFromInterrupt(actionText: string) {
    const assistantId = activeAssistantIdRef.current;
    if (!assistantId || isStreaming) return;

    await streamTurn({
      message: undefined,
      resume_action: actionText,
      attachToAssistantId: assistantId,
      createUserBubble: false,
    });
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void sendNewQuestion();
    }
  }

  return (
    <div className="min-h-screen relative">
      {/* HERO VIEW */}
      {messages.length === 0 && (
        <BackgroundLines className="relative flex min-h-screen items-center justify-center">
          <div className="w-full h-full flex flex-col items-center justify-center relative -top-[6%] px-4">
            <h2 className="bg-clip-text text-transparent text-center bg-gradient-to-b from-neutral-900 to-neutral-700 dark:from-neutral-600 dark:to-white text-xl md:text-2xl lg:text-4xl font-sans py-2 md:py-10 relative z-20 font-bold tracking-tight">
              What’s on the agenda today?
            </h2>

            <div className="px-3 rounded-full border border-neutral-300 dark:border-neutral-700 py-1 flex items-center justify-center gap-2 bg-white/80 dark:bg-neutral-900/60 backdrop-blur">
              <input
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onKeyDown}
                type="text"
                placeholder="Ask anything..."
                className="w-72 md:w-96 lg:w-[700px] rounded-full p-3 border-none bg-transparent text-neutral-900 dark:text-neutral-100 focus:outline-none"
                disabled={isStreaming}
              />

              {/* MIC BUTTON */}
              <button
                type="button"
                onClick={() => (isRecording ? stopRecording() : void startRecording())}
                disabled={isStreaming || isTranscribing}
                className={[
                  "w-10 h-10 rounded-full flex items-center justify-center transition-colors border",
                  isRecording
                    ? "bg-red-600 border-red-600 text-white"
                    : "bg-white/60 dark:bg-neutral-950/30 border-neutral-300 dark:border-neutral-700 hover:bg-neutral-100 dark:hover:bg-neutral-800",
                  isStreaming || isTranscribing ? "opacity-60 cursor-not-allowed" : "",
                ].join(" ")}
                aria-label="Voice"
                title={isRecording ? "Stop recording" : "Start recording"}
              >
                {isTranscribing ? (
                  <Loader2 size={18} className="animate-spin" />
                ) : isRecording ? (
                  <MicOff size={18} />
                ) : (
                  <Mic size={18} />
                )}
              </button>

              <button
                onClick={() => void sendNewQuestion()}
                disabled={!canSend}
                className={[
                  "w-10 h-10 rounded-full flex items-center justify-center transition-colors",
                  canSend ? "bg-neutral-900 hover:bg-neutral-700 cursor-pointer" : "bg-neutral-400 cursor-not-allowed",
                ].join(" ")}
                aria-label="Send"
              >
                <ArrowUpFromDot size={20} className="text-white" />
              </button>
            </div>

            {(isRecording || isTranscribing) && (
              <div className="mt-3 text-xs text-neutral-600 dark:text-neutral-300">
                {isTranscribing ? "Transcribing…" : "Recording… click mic again to stop."}
              </div>
            )}
          </div>
        </BackgroundLines>
      )}

      {/* CHAT VIEW */}
      {messages.length > 0 && (
        <div className="min-h-screen flex flex-col">
          <div className="flex-1 w-full max-w-4xl mx-auto px-4 py-8 space-y-4">
            {messages.map((m) => (
              <div key={m.id} className="space-y-2">
                {m.role === "user" && (
                  <div className="flex justify-end">
                    <div className="max-w-[85%] rounded-2xl px-4 py-3 bg-neutral-900 text-white shadow-sm">
                      <pre className="whitespace-pre-wrap font-sans m-0">{m.content}</pre>
                    </div>
                  </div>
                )}

                {m.role === "assistant" && (
                  <div className="flex justify-start">
                    <div className="max-w-[85%] w-full rounded-2xl px-4 py-3 bg-white/80 dark:bg-neutral-900/70 text-neutral-900 dark:text-neutral-100 border border-neutral-200/60 dark:border-neutral-800 shadow-[0_1px_0_rgba(0,0,0,0.03)]">
                      <div className="flex items-center justify-between gap-3 mb-2">
                        <span className="text-xs opacity-70">Assistant</span>

                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => toggleDetails(m.id)}
                            className="text-xs px-2 py-1 rounded-full border border-neutral-300 dark:border-neutral-700 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition flex items-center gap-1"
                          >
                            <span>Details</span>
                            {m.detailsOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                          </button>

                          <button
                            type="button"
                            onClick={() => openProcess(m.processSteps)}
                            className="text-xs px-2 py-1 rounded-full border border-neutral-300 dark:border-neutral-700 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition"
                          >
                            Process
                          </button>
                        </div>
                      </div>

                      {m.detailsOpen && (
                        <div className="mb-3 space-y-3">
                          <div className="rounded-2xl border border-neutral-200 dark:border-neutral-800 bg-white/60 dark:bg-neutral-950/40 p-3">
                            <div className="flex items-center justify-between mb-2">
                              <div className="flex items-center gap-2 text-xs text-neutral-600 dark:text-neutral-300">
                                {isStreaming ? (
                                  <>
                                    <span className="relative inline-flex h-2 w-2">
                                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-neutral-500 opacity-40"></span>
                                      <span className="relative inline-flex rounded-full h-2 w-2 bg-neutral-800 dark:bg-neutral-200"></span>
                                    </span>
                                    <span className="animate-pulse">Working…</span>
                                  </>
                                ) : (
                                  <>
                                    <span className="relative inline-flex rounded-full h-2 w-2 bg-neutral-400"></span>
                                    <span>Activity</span>
                                  </>
                                )}
                              </div>
                              <div className="text-[11px] text-neutral-500 dark:text-neutral-400">
                                Agent outputs + tools (clean)
                              </div>
                            </div>

                            {m.activity?.supervisorThoughts ? (
                              <div className="rounded-2xl border border-neutral-200 dark:border-neutral-800 bg-white/70 dark:bg-neutral-950/30 p-3 mb-3">
                                <div className="flex items-center gap-2 text-xs font-semibold text-neutral-900 dark:text-neutral-100">
                                  <Brain size={14} className="opacity-70" />
                                  Supervisor thoughts
                                </div>
                                <div className="mt-2 text-sm text-neutral-800 dark:text-neutral-200">
                                  {clampText(m.activity.supervisorThoughts, 420)}
                                </div>
                              </div>
                            ) : null}

                            {(m.activity?.agents?.length ?? 0) === 0 ? (
                              <div className="text-xs text-neutral-500 dark:text-neutral-400">
                                No sub-agent activity yet.
                              </div>
                            ) : (
                              <div className="grid grid-cols-1 gap-3">
                                {m.activity!.agents.map((a) => (
                                  <AgentCard
                                    key={a.agent}
                                    name={prettyAgentName(a.agent)}
                                    tools={a.tools}
                                    preview={a.preview}
                                  />
                                ))}
                              </div>
                            )}
                          </div>

                          {m.interrupt?.type === "review_required" && (
                            <div className="rounded-2xl border border-neutral-200 dark:border-neutral-800 bg-white/80 dark:bg-neutral-950/40 p-3">
                              <div className="text-xs font-semibold text-neutral-800 dark:text-neutral-100 mb-2">
                                Email approval required
                              </div>

                              <div className="text-xs text-neutral-600 dark:text-neutral-300 mb-2">
                                Review the draft below, then approve or request changes.
                              </div>

                              <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white/70 dark:bg-neutral-950/30 p-3 mb-3">
                                <Markdown text={m.interrupt.payload} />
                              </div>

                              <div className="flex flex-wrap gap-2 mb-2">
                                <button
                                  type="button"
                                  className={[
                                    "px-3 py-1.5 rounded-full text-xs border transition",
                                    reviewMode === "approve"
                                      ? "bg-neutral-900 text-white border-neutral-900"
                                      : "border-neutral-300 dark:border-neutral-700 hover:bg-neutral-100 dark:hover:bg-neutral-800",
                                  ].join(" ")}
                                  onClick={() => setReviewMode("approve")}
                                >
                                  Approve
                                </button>

                                <button
                                  type="button"
                                  className={[
                                    "px-3 py-1.5 rounded-full text-xs border transition",
                                    reviewMode === "change"
                                      ? "bg-neutral-900 text-white border-neutral-900"
                                      : "border-neutral-300 dark:border-neutral-700 hover:bg-neutral-100 dark:hover:bg-neutral-800",
                                  ].join(" ")}
                                  onClick={() => setReviewMode("change")}
                                >
                                  Request changes
                                </button>
                              </div>

                              {reviewMode === "change" && (
                                <textarea
                                  value={reviewText}
                                  onChange={(e) => setReviewText(e.target.value)}
                                  placeholder="Describe what to change (tone, subject, missing info, etc.)"
                                  className="w-full min-h-[90px] rounded-2xl border border-neutral-300 dark:border-neutral-700 bg-white/80 dark:bg-neutral-950/30 p-3 text-sm outline-none"
                                />
                              )}

                              <div className="flex justify-end mt-3">
                                <button
                                  type="button"
                                  disabled={
                                    isStreaming ||
                                    !reviewMode ||
                                    (reviewMode === "change" && reviewText.trim().length === 0)
                                  }
                                  onClick={() => {
                                    if (reviewMode === "approve") void resumeFromInterrupt("approved");
                                    else void resumeFromInterrupt(reviewText.trim());
                                  }}
                                  className={[
                                    "px-4 py-2 rounded-xl text-sm transition",
                                    isStreaming ||
                                    !reviewMode ||
                                    (reviewMode === "change" && reviewText.trim().length === 0)
                                      ? "bg-neutral-400 text-white cursor-not-allowed"
                                      : "bg-neutral-900 hover:bg-neutral-700 text-white",
                                  ].join(" ")}
                                >
                                  Submit
                                </button>
                              </div>
                            </div>
                          )}
                        </div>
                      )}

                      <div className="text-[15px] leading-6">
                        {m.content ? (
                          <Markdown text={m.content} />
                        ) : isStreaming ? (
                          <span className="text-sm text-neutral-500 dark:text-neutral-400" />
                        ) : (
                          <span className="text-sm text-neutral-500 dark:text-neutral-400">—</span>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
            <div ref={bottomRef} />
          </div>

          {/* Bottom Input */}
          <div className="sticky bottom-0 w-full bg-transparent px-4 pb-6">
            <div className="max-w-4xl mx-auto">
              <div className="px-3 rounded-full border border-neutral-300 dark:border-neutral-700 bg-white/80 dark:bg-neutral-900/60 backdrop-blur py-1 flex items-center gap-2">
                <input
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={onKeyDown}
                  type="text"
                  placeholder="Ask anything..."
                  className="w-full rounded-full p-3 border-none bg-transparent text-neutral-900 dark:text-neutral-100 focus:outline-none"
                  disabled={isStreaming}
                />

                {/* MIC BUTTON */}
                <button
                  type="button"
                  onClick={() => (isRecording ? stopRecording() : void startRecording())}
                  disabled={isStreaming || isTranscribing}
                  className={[
                    "w-10 h-10 rounded-full flex items-center justify-center transition-colors border",
                    isRecording
                      ? "bg-red-600 border-red-600 text-white"
                      : "bg-white/60 dark:bg-neutral-950/30 border-neutral-300 dark:border-neutral-700 hover:bg-neutral-100 dark:hover:bg-neutral-800",
                    isStreaming || isTranscribing ? "opacity-60 cursor-not-allowed" : "",
                  ].join(" ")}
                  aria-label="Voice"
                >
                  {isTranscribing ? (
                    <Loader2 size={18} className="animate-spin" />
                  ) : isRecording ? (
                    <MicOff size={18} />
                  ) : (
                    <Mic size={18} />
                  )}
                </button>

                {!isStreaming ? (
                  <button
                    onClick={() => void sendNewQuestion()}
                    disabled={!canSend}
                    className={[
                      "w-10 h-10 rounded-full flex items-center justify-center transition-colors",
                      canSend ? "bg-neutral-900 hover:bg-neutral-700 cursor-pointer" : "bg-neutral-400 cursor-not-allowed",
                    ].join(" ")}
                    aria-label="Send"
                  >
                    <ArrowUpFromDot size={20} className="text-white" />
                  </button>
                ) : (
                  <button
                    onClick={stop}
                    className="w-10 h-10 rounded-full bg-neutral-900 hover:bg-neutral-700 flex items-center justify-center transition-colors"
                    aria-label="Stop"
                  >
                    <Square size={18} className="text-white" />
                  </button>
                )}
              </div>

              {(isRecording || isTranscribing) && (
                <div className="mt-2 text-xs text-neutral-600 dark:text-neutral-300">
                  {isTranscribing ? "Transcribing…" : "Recording… click mic again to stop."}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* PROCESS SIDEBAR */}
      <div
        className={[
          "fixed top-0 right-0 h-full w-[90%] sm:w-[440px] bg-white dark:bg-neutral-950 border-l border-neutral-200 dark:border-neutral-800 shadow-xl z-50",
          "transform transition-transform duration-300 ease-out",
          processOpen ? "translate-x-0" : "translate-x-full",
        ].join(" ")}
      >
        <div className="h-full flex flex-col">
          <div className="p-4 border-b border-neutral-200 dark:border-neutral-800 flex items-center justify-between">
            <div>
              <div className="font-semibold text-neutral-900 dark:text-neutral-100">Process</div>
              <div className="text-xs text-neutral-500 dark:text-neutral-400">Minimal tool usage log</div>
            </div>
            <button
              onClick={closeProcess}
              className="p-2 rounded-lg hover:bg-neutral-100 dark:hover:bg-neutral-800 transition"
              aria-label="Close process sidebar"
            >
              <X size={18} className="text-neutral-700 dark:text-neutral-200" />
            </button>
          </div>

          <div className="p-4 overflow-auto flex-1">
            {activeSteps.length === 0 ? (
              <div className="text-sm text-neutral-600 dark:text-neutral-300">No process steps captured.</div>
            ) : (
              <ol className="space-y-2 text-sm text-neutral-800 dark:text-neutral-200">
                {dedupKeepOrder(activeSteps).map((s, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-neutral-400 tabular-nums w-6 text-right">{i + 1}.</span>
                    <span className="break-words max-w-[350px]">{s}</span>
                  </li>
                ))}
              </ol>
            )}
          </div>
        </div>
      </div>

      {processOpen && (
        <button onClick={closeProcess} className="fixed inset-0 bg-black/30 z-40" aria-label="Close sidebar backdrop" />
      )}
    </div>
  );
}
