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
  Send,
  Home,
  Settings,
  LogOut,
  Trash,
  Volume2,
  VolumeX,
  Play,
  Pause,
} from "lucide-react";
import { IconUserBolt } from "@tabler/icons-react";
import { useUser, SignOutButton } from "@clerk/nextjs";
import Link from "next/link";

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
  audioUrl?: string;
  isAudioLoading?: boolean;
  autoPlay?: boolean;
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
    } catch { }

    return { event, data };
  });

  return { events, rest };
}

function tryExtractResponseFromSupervisorJSON(jsonText: string): string | null {
  try {
    const obj = JSON.parse(jsonText);
    if (obj && typeof obj.response === "string") return obj.response;
  } catch { }
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
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="rounded-2xl border border-neutral-200/50 dark:border-neutral-800/50 bg-white/40 dark:bg-neutral-900/40 backdrop-blur-md p-4 transition-all hover:bg-white/60 dark:hover:bg-neutral-900/60 shadow-sm overflow-hidden group">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className="p-2 rounded-xl bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400 group-hover:scale-110 transition-transform">
            <Wrench size={16} />
          </div>
          <div className="min-w-0">
            <div className="text-sm font-semibold text-neutral-900 dark:text-neutral-100 truncate">
              {name}
            </div>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {tools.length === 0 ? (
                preview ? (
                  <ToolChip label="Message" />
                ) : (
                  <span className="text-[11px] text-neutral-500/80 dark:text-neutral-400/80">Silent Process</span>
                )
              ) : (
                tools.map((t) => <ToolChip key={t} label={toolLabel(t)} />)
              )}
            </div>
          </div>
        </div>

        <button
          onClick={() => setIsOpen(!isOpen)}
          className="shrink-0 p-1.5 rounded-lg hover:bg-neutral-200/50 dark:hover:bg-neutral-800/50 transition-colors text-neutral-500 dark:text-neutral-400"
        >
          {isOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
      </div>

      {isOpen && (
        <div className="mt-4 animate-in fade-in slide-in-from-top-2 duration-300">
          {preview ? (
            <div className="rounded-xl border border-neutral-200/50 dark:border-neutral-800/50 bg-white/50 dark:bg-neutral-950/20 p-4">
              <div className="text-[11px] uppercase tracking-wider font-bold text-neutral-400 dark:text-neutral-500 mb-3 flex items-center gap-2">
                <ArrowUpFromDot size={12} />
                Execution Output
              </div>
              <div className="text-sm leading-relaxed text-neutral-800 dark:text-neutral-200">
                <Markdown text={preview} />
              </div>
            </div>
          ) : (
            <div className="text-xs text-neutral-500/70 italic p-2">Executed silently without visible output.</div>
          )}
        </div>
      )}
    </div>
  );
}

function VoiceMessage({ url, autoPlay = false }: { url: string; autoPlay?: boolean }) {
  const [isPlaying, setIsPlaying] = useState(autoPlay);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (autoPlay && audioRef.current) {
      audioRef.current.play().catch((e) => console.error("Auto-play failed:", e));
    }
  }, [autoPlay]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const updateProgress = () => {
      setProgress((audio.currentTime / audio.duration) * 100);
    };

    const handleEnded = () => {
      setIsPlaying(false);
      setProgress(0);
    };

    audio.addEventListener("timeupdate", updateProgress);
    audio.addEventListener("ended", handleEnded);
    return () => {
      audio.removeEventListener("timeupdate", updateProgress);
      audio.removeEventListener("ended", handleEnded);
    };
  }, []);

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play();
    }
    setIsPlaying(!isPlaying);
  };

  return (
    <div className="flex items-center gap-4 bg-neutral-100 dark:bg-neutral-800/50 p-4 rounded-2xl border border-neutral-200 dark:border-neutral-700/50 w-full max-w-sm group">
      <audio ref={audioRef} src={url} className="hidden" />
      <button
        onClick={togglePlay}
        className="w-10 h-10 rounded-full bg-neutral-900 dark:bg-neutral-100 flex items-center justify-center text-white dark:text-neutral-900 transition-transform hover:scale-105 active:scale-95"
      >
        {isPlaying ? <Pause size={20} /> : <Play size={20} className="ml-0.5" />}
      </button>
      <div className="flex-1 space-y-2">
        <div className="h-1.5 w-full bg-neutral-200 dark:bg-neutral-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-neutral-900 dark:bg-neutral-100 transition-all duration-100"
            style={{ width: `${progress}%` }}
          />
        </div>
        <div className="flex justify-between text-[10px] text-neutral-500 font-medium">
          <span>{isPlaying ? "Playing..." : "Voice Message"}</span>
          <span>ElevenLabs</span>
        </div>
      </div>
    </div>
  );
}

export default function NewChat() {
  // If you ALWAYS want English transcription, set this to "en"
  // Otherwise leave null for auto-detect.
  const VOICE_LANGUAGE_HINT: string | null = null; // e.g. "en"



  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  // Sidebar
  const [processOpen, setProcessOpen] = useState(false);
  const [activeSteps, setActiveSteps] = useState<string[]>([]);

  // Review UI
  const [reviewMode, setReviewMode] = useState<"approve" | "change" | null>(null);
  const [reviewText, setReviewText] = useState("");
  const [audioResponseEnabled, setAudioResponseEnabled] = useState(false);

  // Voice UI
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordedChunksRef = useRef<BlobPart[]>([]);

  // Refs
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const { user, isLoaded } = useUser();
  const threadIdRef = useRef<string>("default_thread");
  const activeAssistantIdRef = useRef<string | null>(null);

  const canSend = useMemo(() => input.trim().length > 0 && !isStreaming, [input, isStreaming]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (messages.length > 0) setTimeout(() => inputRef.current?.focus(), 50);
  }, [messages.length]);

  // Click outside to close dropdown
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Fetch History on Mount
  useEffect(() => {
    if (!isLoaded || !user) return;

    // Set thread ID to user ID for persistence
    threadIdRef.current = user.id;

    async function fetchHistory() {
      try {
        const res = await fetch(`/api/chat/history?thread_id=${threadIdRef.current}`);
        if (!res.ok) return;
        const history = await res.json();
        if (Array.isArray(history) && history.length > 0) {
          const mapped: ChatMessage[] = history.map((msg: any) => {
            let content = msg.content;
            let activity: any = { agents: [] };

            if (msg.role === "assistant") {
              // If it's a JSON from supervisor, extract fields
              try {
                // Find potential JSON boundaries
                const start = msg.content.indexOf("{");
                const end = msg.content.lastIndexOf("}");

                if (start !== -1 && end !== -1 && end > start) {
                  const jsonStr = msg.content.substring(start, end + 1);
                  const parsed = JSON.parse(jsonStr);
                  if (parsed && typeof parsed.response === "string") {
                    content = parsed.response;
                    if (parsed.thoughts) {
                      activity.supervisorThoughts = parsed.thoughts;
                    }
                  }
                }
              } catch (e) {
                // Not a valid JSON or parsing failed, keep as is
              }
            }

            return {
              id: uid(), // generate a temp ID for frontend 
              role: msg.role === "user" ? "user" : "assistant",
              content: content,
              detailsOpen: false,
              activity: activity
            };
          });

          // Group consecutive assistant messages
          const grouped: ChatMessage[] = [];
          for (const msg of mapped) {
            const last = grouped[grouped.length - 1];
            if (last && last.role === "assistant" && msg.role === "assistant") {
              // Merge into the previous assistant message
              if (!last.activity) last.activity = { agents: [] };

              // Add the previous content as a sub-step if it was an intermediate thought/action
              if (last.content && last.content !== "—") {
                last.activity.agents.push({
                  agent: "Process Step",
                  tools: [],
                  preview: last.content
                });
              }

              // Update content to the most recent one
              last.content = msg.content;
              if (msg.activity?.supervisorThoughts) {
                last.activity.supervisorThoughts = msg.activity.supervisorThoughts;
              }
              if (msg.activity?.agents) {
                last.activity.agents.push(...msg.activity.agents);
              }
            } else {
              grouped.push(msg);
            }
          }

          setMessages(grouped);
        }
      } catch (e) {
        console.error("Failed to fetch history", e);
      }
    }
    fetchHistory();
  }, [isLoaded, user]);

  async function handleNewChat() {
    if (!user) return;
    try {
      const res = await fetch("/api/chat/clear", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ thread_id: user.id }),
      });
      if (res.ok) {
        setMessages([]);
        setInput("");
        // Reset any other relevant state if needed
      }
    } catch (e) {
      console.error("Failed to clear history", e);
    }
  }

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

    const res = await fetch(`/api/audio/transcribe`, {
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

  async function playAudioResponse(text: string) {
    if (!text || text.length < 2) return;
    try {
      const res = await fetch("/api/audio/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!res.ok) return;
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      return url;
    } catch (e) {
      console.error("Failed to fetch audio response", e);
      return null;
    }
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
      // Removed !st.usedTool check to allow text-only agents
      if (!st.finalized) {
        st.previewFinal = makeAgentPreview(st.buffer);
        st.finalized = true;
      }
    };

    const rebuildActivity = () => {
      const agents: AgentActivity[] = [];
      for (const a of agentOrder) {
        const st = agentState.get(a);
        if (!st) continue;
        const preview = st.finalized ? st.previewFinal : makeAgentPreview(st.buffer);
        // We only skip if there's absolutely no content and no tools
        if (!preview && st.tools.size === 0) continue;

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
              const st = ensureAgent(agent);
              st.started = true;
              // Add to order immediately so it shows up even if no tools are used
              if (!agentOrder.includes(agent)) {
                agentOrder.push(agent);
              }
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
              st.tools.add(tool);
              st.usedTool = true;
              if (!agentOrder.includes(agent)) agentOrder.push(agent);

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
              // Removed !st.usedTool check to allow capturing text logic
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
            break; // Break the stream loop on interrupt to avoid read errors
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

            if (audioResponseEnabled && extractedResponse) {
              setMessages((prev) =>
                prev.map((m) => (m.id === attachToAssistantId ? { ...m, isAudioLoading: true } : m))
              );

              playAudioResponse(extractedResponse).then((url) => {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === attachToAssistantId
                      ? { ...m, audioUrl: url ?? undefined, isAudioLoading: false, autoPlay: !!url }
                      : m
                  )
                );
              });
            }
            continue;
          }
        }
      }
    } catch (e: any) {
      const aborted = e?.name === "AbortError";
      if (!aborted) {
        console.warn(e);
        setMessages((prev) =>
          prev.map((m) => {
            // Only show streaming error if there is no interrupt or response content.
            // On interrupt, the backend closes the stream, so connection errors are expected.
            if (m.id === attachToAssistantId && !m.interrupt && !m.content) {
              return { ...m, content: "⚠️ Something went wrong while streaming." };
            }
            return m;
          })
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
      isAudioLoading: audioResponseEnabled,
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
    <div className="min-h-screen relative overflow-hidden">
      {/* GLOBAL PROFILE DROPDOWN */}
      <div className="fixed top-6 right-6 z-[60]" ref={dropdownRef}>
        <button
          onClick={() => setMenuOpen(!menuOpen)}
          className="w-12 h-12 rounded-2xl overflow-hidden border-2 border-white/20 dark:border-white/5 shadow-2xl transition-all hover:scale-105 active:scale-95"
        >
          {user?.imageUrl ? (
            <img src={user.imageUrl} alt="Profile" className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full bg-neutral-200 dark:bg-neutral-800 flex items-center justify-center">
              <IconUserBolt size={24} className="text-neutral-500" />
            </div>
          )}
        </button>

        {menuOpen && (
          <div className="absolute top-14 right-0 w-48 rounded-2xl border border-white/20 dark:border-white/5 bg-white/60 dark:bg-neutral-900/60 backdrop-blur-2xl shadow-2xl py-2 animate-in fade-in zoom-in-95 duration-200">
            <Link
              href="/"
              onClick={() => setMenuOpen(false)}
              className="flex items-center gap-3 px-4 py-2.5 text-sm font-medium text-neutral-600 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
            >
              <Home size={18} />
              Home
            </Link>

            <Link
              href="/profile"
              onClick={() => setMenuOpen(false)}
              className="flex items-center gap-3 px-4 py-2.5 text-sm font-medium text-neutral-600 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
            >
              <Settings size={18} />
              Settings
            </Link>

            <button
              onClick={() => {
                void handleNewChat();
                setMenuOpen(false);
              }}
              className="flex items-center gap-3 px-4 py-2.5 text-sm font-medium text-neutral-600 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors w-full text-left"
            >
              <Trash size={18} />
              Clear Chat
            </button>

            <div className="h-px bg-neutral-200 dark:bg-neutral-800 mx-2 my-1" />

            <SignOutButton redirectUrl="/">
              <button
                className="flex items-center gap-3 px-4 py-2.5 text-sm font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors w-full text-left"
              >
                <LogOut size={18} />
                Sign Out
              </button>
            </SignOutButton>
          </div>
        )}
      </div>

      {/* HERO VIEW */}
      {messages.length === 0 && (
        <BackgroundLines className="relative flex min-h-[90vh] items-center justify-center">
          <div className="w-full h-full flex flex-col items-center justify-center relative -top-[10%] px-4">
            <div className="mb-10 flex flex-col items-center gap-6 animate-in fade-in zoom-in duration-1000">
              <div className="w-20 h-20 rounded-3xl bg-neutral-900 dark:bg-white flex items-center justify-center shadow-2xl relative">
                <div className="absolute inset-0 bg-neutral-900 dark:bg-white rounded-3xl blur-2xl opacity-20 animate-pulse"></div>
                <Brain size={44} className="text-white dark:text-neutral-900 relative z-10" />
              </div>
              <h2 className="text-4xl md:text-5xl lg:text-6xl font-black tracking-tighter text-center bg-clip-text text-transparent bg-gradient-to-b from-neutral-950 to-neutral-600 dark:from-white dark:to-neutral-500">
                AIPËR
              </h2>
              <p className="text-neutral-500 dark:text-neutral-400 font-medium tracking-wide text-lg">Your intelligent autonomous workspace.</p>
            </div>

            <div className="px-5 rounded-[2rem] border border-neutral-200 dark:border-neutral-800 py-2 flex items-center justify-center gap-3 bg-white/40 dark:bg-neutral-900/40 backdrop-blur-xl shadow-sm group transition-all hover:bg-white/60 dark:hover:bg-neutral-900/60">
              <input
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onKeyDown}
                type="text"
                placeholder="Message AIPËR..."
                className="w-72 md:w-96 lg:w-[600px] py-3 border-none bg-transparent text-neutral-900 dark:text-neutral-100 focus:outline-none text-lg"
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
                onClick={() => setAudioResponseEnabled(!audioResponseEnabled)}
                title={audioResponseEnabled ? "Disable Audio Response" : "Enable Audio Response"}
                className={`p-2 rounded-xl transition-all duration-300 ${audioResponseEnabled
                  ? "bg-blue-500/20 text-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.3)]"
                  : "bg-neutral-100 dark:bg-neutral-800 text-neutral-500 hover:bg-neutral-200 dark:hover:bg-neutral-700"
                  }`}
              >
                {audioResponseEnabled ? <Volume2 size={20} /> : <VolumeX size={20} />}
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
        <div className="flex flex-col h-screen overflow-hidden">
          <div className="flex-1 overflow-y-auto px-4 pt-12 pb-40 space-y-8 scroll-smooth no-scrollbar">
            <div className="max-w-4xl mx-auto space-y-10">
              {messages.map((m) => (
                <div key={m.id} className="space-y-2">
                  {m.role === "user" && (
                    <div className="flex justify-end pr-2">
                      <div className="max-w-[80%] rounded-3xl rounded-br-none px-6 py-4 bg-gradient-to-br from-neutral-800 to-neutral-700 text-white transition-transform hover:scale-[1.01] shadow-sm">
                        <div className="text-[15px] leading-relaxed font-medium">
                          {m.content}
                        </div>
                      </div>
                    </div>
                  )}

                  {m.role === "assistant" && (
                    <div className="flex justify-start">
                      <div className="max-w-[90%] w-full rounded-3xl rounded-bl-none px-6 py-5 bg-white/40 dark:bg-neutral-900/40 backdrop-blur-xl text-neutral-900 dark:text-neutral-100 border border-white/20 dark:border-white/5 transition-all hover:bg-white/50 dark:hover:bg-neutral-900/50">
                        <div className="flex items-center justify-between gap-4 mb-4">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-neutral-800 to-neutral-600 flex items-center justify-center shadow-lg">
                              <Brain size={16} className="text-white" />
                            </div>
                            <span className="text-sm font-bold tracking-tight opacity-90">AIPËR</span>
                          </div>

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
                          {m.audioUrl ? (
                            <VoiceMessage url={m.audioUrl} autoPlay={m.autoPlay} />
                          ) : (m.isAudioLoading || (isStreaming && audioResponseEnabled && m.id === activeAssistantIdRef.current)) ? (
                            <div className="flex items-center gap-3 bg-neutral-100 dark:bg-neutral-800/50 p-4 rounded-2xl border border-neutral-200 dark:border-neutral-700/50 w-full max-w-sm">
                              <div className="w-10 h-10 rounded-full bg-neutral-200 dark:bg-neutral-700 animate-pulse" />
                              <div className="flex-1 space-y-2">
                                <div className="h-1.5 w-full bg-neutral-200 dark:bg-neutral-700 rounded-full overflow-hidden" />
                                <div className="text-[10px] text-neutral-500 animate-pulse">
                                  {isStreaming ? "Thinking..." : "Generating voice..."}
                                </div>
                              </div>
                            </div>
                          ) : m.content ? (
                            <Markdown text={m.content} />
                          ) : isStreaming ? (
                            <span className="text-sm text-neutral-500 dark:text-neutral-400" />
                          ) : (
                            <span className="text-sm text-neutral-500 dark:text-neutral-400">—</span>
                          )}
                        </div>

                        {m.audioUrl && m.content && (
                          <div className="mt-4 pt-4 border-t border-neutral-200 dark:border-neutral-800">
                            <button
                              onClick={() => {
                                setMessages(prev => prev.map(msg => msg.id === m.id ? { ...msg, detailsOpen: !msg.detailsOpen } : msg))
                              }}
                              className="text-xs text-neutral-500 hover:text-neutral-700 dark:hover:text-neutral-300 transition-colors flex items-center gap-1"
                            >
                              Show Transcript {m.detailsOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                            </button>
                            {m.detailsOpen && (
                              <div className="mt-2 text-sm opacity-60">
                                <Markdown text={m.content} />
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
              <div ref={bottomRef} />
            </div>

            {/* Bottom Input Area */}
            <div className="fixed bottom-0 left-0 right-0 p-6 pointer-events-none">
              <div className="max-w-4xl mx-auto pointer-events-auto">
                <div className="group relative">
                  <div className="absolute -inset-1 bg-gradient-to-r from-neutral-200 to-neutral-300 dark:from-neutral-800 dark:to-neutral-700 rounded-[2.5rem] blur opacity-25 group-hover:opacity-40 transition duration-1000 group-hover:duration-200"></div>
                  <div className="relative px-4 py-2 rounded-[2rem] border border-neutral-200/50 dark:border-neutral-800/50 bg-white/70 dark:bg-neutral-900/80 backdrop-blur-2xl shadow-2xl flex items-center gap-3">
                    <input
                      ref={inputRef}
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      onKeyDown={onKeyDown}
                      type="text"
                      placeholder="Message AIPËR..."
                      className="w-full py-4 px-2 border-none bg-transparent text-neutral-900 dark:text-neutral-100 placeholder:text-neutral-400 dark:placeholder:text-neutral-500 focus:outline-none text-[15px]"
                      disabled={isStreaming}
                    />

                    <div className="flex items-center gap-2 pr-1">
                      {/* MIC BUTTON */}
                      <button
                        type="button"
                        onClick={() => (isRecording ? stopRecording() : void startRecording())}
                        disabled={isStreaming || isTranscribing}
                        className={[
                          "w-11 h-11 rounded-full flex items-center justify-center transition-all duration-300 border",
                          isRecording
                            ? "bg-red-500 border-red-400 text-white animate-pulse shadow-lg shadow-red-500/30"
                            : "bg-neutral-100 dark:bg-neutral-800 border-neutral-200 dark:border-neutral-700 text-neutral-600 dark:text-neutral-400 hover:bg-neutral-200 dark:hover:bg-neutral-700",
                          isStreaming || isTranscribing ? "opacity-40" : "",
                        ].join(" ")}
                      >
                        {isTranscribing ? (
                          <Loader2 size={20} className="animate-spin" />
                        ) : isRecording ? (
                          <MicOff size={20} />
                        ) : (
                          <Mic size={20} />
                        )}
                      </button>

                      <button
                        type="button"
                        onClick={() => setAudioResponseEnabled(!audioResponseEnabled)}
                        title={audioResponseEnabled ? "Disable Audio Response" : "Enable Audio Response"}
                        className={`w-11 h-11 rounded-full flex items-center justify-center transition-all duration-300 border ${audioResponseEnabled
                          ? "bg-blue-500/20 border-blue-400 text-blue-500 shadow-lg shadow-blue-500/20"
                          : "bg-neutral-100 dark:bg-neutral-800 border-neutral-200 dark:border-neutral-700 text-neutral-600 dark:text-neutral-400 hover:bg-neutral-200 dark:hover:bg-neutral-700"
                          }`}
                      >
                        {audioResponseEnabled ? <Volume2 size={20} /> : <VolumeX size={20} />}
                      </button>

                      {!isStreaming ? (
                        <button
                          onClick={() => void sendNewQuestion()}
                          disabled={!canSend}
                          className={[
                            "w-11 h-11 rounded-full flex items-center justify-center transition-all duration-300",
                            canSend
                              ? "bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 shadow-lg hover:scale-105 active:scale-95"
                              : "bg-neutral-100 dark:bg-neutral-800 text-neutral-400 dark:text-neutral-600",
                          ].join(" ")}
                        >
                          <ArrowUpFromDot size={22} />
                        </button>
                      ) : (
                        <button
                          onClick={stop}
                          className="w-11 h-11 rounded-full bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 flex items-center justify-center transition-all shadow-lg hover:scale-105"
                        >
                          <Square size={18} fill="currentColor" />
                        </button>
                      )}
                    </div>
                  </div>
                </div>

                {(isRecording || isTranscribing) && (
                  <div className="mt-3 text-center">
                    <span className="text-[11px] font-bold uppercase tracking-widest text-neutral-400 dark:text-neutral-600 animate-pulse">
                      {isTranscribing ? "Transcribing Engine Active…" : "Recording Audio Stream…"}
                    </span>
                  </div>
                )}
              </div>
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
