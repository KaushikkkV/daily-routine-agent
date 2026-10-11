"use client";

import React, { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Bot, User, Sparkles, RefreshCw, MessageSquare, Clock, Calendar as CalendarIcon, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ThoughtAccordion } from "./ThoughtAccordion";
import { BlurText } from "@/components/effects/BlurText";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { format } from "date-fns";
import { Calendar as CalendarComponent } from "@/components/ui/calendar";

export interface ChatMessageItem {
  id: string;
  role: "user" | "assistant";
  content: string;
  thought?: string | null;
  timestamp: string;
  isNew?: boolean;
  actionChips?: string[];
  requiresDateSelection?: boolean;
  uiAction?: string | null;
  defaultTask?: string | null;
}

interface ChatPaneProps {
  messages: ChatMessageItem[];
  onSendMessage: (msg: string) => Promise<void>;
  isLoading: boolean;
  sessionId: string;
  onResetSession: () => void;
  focusTrigger?: number;
  onDateChange?: (dateStr: string) => void;
}

function getLabelFromUserPrompt(prompt?: string): string {
  if (!prompt) return "Meeting";
  const p = prompt.trim();
  const lower = p.toLowerCase();
  if (lower.includes("gym") || lower.includes("workout")) return "Gym Session";
  if (lower.includes("dinner")) return "Dinner";
  if (lower.includes("lunch")) return "Lunch Preparation";
  if (lower.includes("breakfast")) return "Breakfast";
  if (lower.includes("call")) return "Call";
  if (lower.includes("sync")) return "Sync";
  if (lower.includes("meet")) return "Meeting";
  if (lower.includes("coffee")) return "Coffee Break";
  if (lower.includes("dentist")) return "Dentist Appointment";
  if (lower.includes("doctor")) return "Doctor Appointment";
  const cleaned = p
    .replace(/^(?:setup|set\s+up|schedule|plan|book|i\s+(?:wanna|want\s+to|need\s+to|have\s+to)\s+(?:go\s+to)?)\s+(?:a\s+)?/i, "")
    .replace(/\s+(?:tomorrow|today|next\s+week|this\s+week)$/i, "")
    .trim();
  if (cleaned.length > 0 && cleaned.length < 30) {
    return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
  }
  return "Meeting";
}

const DURATION_PRESETS = [15, 30, 45, 60];

interface InlineDatePickerCardProps {
  initialTitle?: string;
  onConfirm: (payload: { title: string; dateStr: string; timeStr: string; durationMinutes: number }) => void;
  disabled?: boolean;
}

const InlineDatePickerCard: React.FC<InlineDatePickerCardProps> = ({
  initialTitle = "Meeting",
  onConfirm,
  disabled = false,
}) => {
  const [taskTitle, setTaskTitle] = useState<string>(initialTitle || "Meeting");
  const [selectedDate, setSelectedDate] = useState<Date | undefined>(undefined);
  const [selectedHour, setSelectedHour] = useState<string>("09");
  const [selectedMinute, setSelectedMinute] = useState<string>("00");
  const [selectedPeriod, setSelectedPeriod] = useState<"AM" | "PM">("AM");
  const [selectedDuration, setSelectedDuration] = useState<number>(30);
  const [isSubmitted, setIsSubmitted] = useState<boolean>(false);

  useEffect(() => {
    if (initialTitle) {
      setTaskTitle(initialTitle);
      if (initialTitle.toLowerCase().includes("gym") || initialTitle.toLowerCase().includes("workout")) {
        setSelectedDuration(45);
      }
    }
  }, [initialTitle]);

  useEffect(() => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    setSelectedDate(tomorrow);
  }, []);

  const formattedDisplay = selectedDate ? format(selectedDate, "MMM d, yyyy") : "Selected Date";

  const handleConfirm = () => {
    if (!selectedDate || disabled || isSubmitted) return;
    setIsSubmitted(true);
    const isoString = format(selectedDate, "yyyy-MM-dd");
    const formattedTime = `${selectedHour}:${selectedMinute} ${selectedPeriod}`;
    onConfirm({
      title: taskTitle.trim() || "Meeting",
      dateStr: isoString,
      timeStr: formattedTime,
      durationMinutes: selectedDuration,
    });
  };

  return (
    <div className="mt-3 overflow-hidden rounded-xl border border-indigo-500/30 bg-zinc-950/90 p-3 shadow-md shadow-indigo-950/30">
      {/* Header: Displays editable task title */}
      <div className="flex items-center justify-between pb-2 mb-2 border-b border-zinc-800/80 gap-2">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-indigo-600/20 text-indigo-400 border border-indigo-500/30">
            <CalendarIcon className="h-3.5 w-3.5" />
          </div>
          <input
            type="text"
            value={taskTitle}
            disabled={disabled || isSubmitted}
            onChange={(e) => setTaskTitle(e.target.value)}
            placeholder="Task Title..."
            className="text-xs font-semibold text-zinc-100 bg-zinc-900/60 border border-zinc-800/80 rounded-md px-2 py-0.5 focus:border-indigo-500 focus:outline-none w-full max-w-[210px] truncate"
          />
        </div>
        {isSubmitted ? (
          <span className="flex items-center gap-1 text-[11px] font-medium text-emerald-400 shrink-0">
            <CheckCircle2 className="h-3 w-3" /> Scheduled
          </span>
        ) : (
          <span className="text-[11px] text-zinc-400 font-mono shrink-0">
            {selectedDate ? format(selectedDate, "EEE, MMM d") : "Pick Date"}
          </span>
        )}
      </div>

      {/* Mini Calendar mode="single" */}
      <div className="flex justify-center my-1">
        <CalendarComponent
          mode="single"
          selected={selectedDate}
          onSelect={(d) => {
            if (d && !isSubmitted) setSelectedDate(d);
          }}
          disabled={disabled || isSubmitted}
          className="rounded-lg border border-zinc-800/80 bg-zinc-900/60 p-2 scale-95 origin-center"
        />
      </div>

      {/* Time Row: Hour & Minute Dropdowns + Segmented AM / PM Toggle */}
      <div className="mt-2.5 pt-2 border-t border-zinc-800/80">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-[11px] font-medium text-zinc-400 flex items-center gap-1">
            <Clock className="h-3 w-3 text-indigo-400" /> Start Time:
          </span>
          <span className="text-[11px] font-mono text-indigo-300 font-semibold">
            {selectedHour}:{selectedMinute} {selectedPeriod}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {/* Hour dropdown */}
          <div className="flex items-center gap-1 bg-zinc-900 border border-zinc-800 rounded-lg px-2 py-1">
            <span className="text-[10px] text-zinc-500 uppercase font-mono">Hr</span>
            <select
              value={selectedHour}
              disabled={disabled || isSubmitted}
              onChange={(e) => setSelectedHour(e.target.value)}
              className="bg-transparent text-xs text-zinc-200 font-mono focus:outline-none cursor-pointer"
            >
              {["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"].map((hr) => (
                <option key={hr} value={hr} className="bg-zinc-900 text-zinc-200">
                  {hr}
                </option>
              ))}
            </select>
          </div>

          {/* Minute dropdown */}
          <div className="flex items-center gap-1 bg-zinc-900 border border-zinc-800 rounded-lg px-2 py-1">
            <span className="text-[10px] text-zinc-500 uppercase font-mono">Min</span>
            <select
              value={selectedMinute}
              disabled={disabled || isSubmitted}
              onChange={(e) => setSelectedMinute(e.target.value)}
              className="bg-transparent text-xs text-zinc-200 font-mono focus:outline-none cursor-pointer"
            >
              {["00", "15", "30", "45"].map((mn) => (
                <option key={mn} value={mn} className="bg-zinc-900 text-zinc-200">
                  {mn}
                </option>
              ))}
            </select>
          </div>

          {/* Segmented AM / PM Toggle */}
          <div className="flex rounded-lg bg-zinc-900 border border-zinc-800 p-0.5 ml-auto">
            <button
              type="button"
              disabled={disabled || isSubmitted}
              onClick={() => setSelectedPeriod("AM")}
              className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-all ${
                selectedPeriod === "AM"
                  ? "bg-indigo-600 text-white shadow-sm shadow-indigo-600/30"
                  : "text-zinc-400 hover:text-zinc-200"
              } disabled:opacity-50`}
            >
              AM
            </button>
            <button
              type="button"
              disabled={disabled || isSubmitted}
              onClick={() => setSelectedPeriod("PM")}
              className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-all ${
                selectedPeriod === "PM"
                  ? "bg-indigo-600 text-white shadow-sm shadow-indigo-600/30"
                  : "text-zinc-400 hover:text-zinc-200"
              } disabled:opacity-50`}
            >
              PM
            </button>
          </div>
        </div>
      </div>

      {/* Duration Presets */}
      <div className="mt-2.5 pt-2 border-t border-zinc-800/80">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-[11px] font-medium text-zinc-400 flex items-center gap-1">
            <Clock className="h-3 w-3 text-indigo-400" /> Duration Preset:
          </span>
          <span className="text-[11px] font-mono text-indigo-300 font-semibold">{selectedDuration}m</span>
        </div>
        <div className="grid grid-cols-4 gap-1.5">
          {DURATION_PRESETS.map((dur) => (
            <button
              key={dur}
              type="button"
              disabled={disabled || isSubmitted}
              onClick={() => setSelectedDuration(dur)}
              className={`h-7 rounded-lg text-xs font-mono font-medium transition-all ${
                selectedDuration === dur
                  ? "bg-indigo-600 text-white border border-indigo-400 shadow-sm shadow-indigo-600/40"
                  : "bg-zinc-900/80 text-zinc-400 border border-zinc-800 hover:border-zinc-700 hover:text-zinc-200"
              } disabled:opacity-50`}
            >
              [{dur}m]
            </button>
          ))}
        </div>
      </div>

      {/* CTA Confirm button */}
      <Button
        type="button"
        disabled={!selectedDate || disabled || isSubmitted}
        onClick={handleConfirm}
        className="w-full mt-3 h-8 text-xs font-medium bg-indigo-600 hover:bg-indigo-500 text-white shadow-sm shadow-indigo-600/30 gap-1.5 rounded-lg active:scale-[0.99] disabled:opacity-50"
      >
        {isSubmitted ? (
          <>
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-300" />
            Confirmed for {formattedDisplay} at {selectedHour}:{selectedMinute} {selectedPeriod}
          </>
        ) : (
          <>
            Confirm Slot for {formattedDisplay} at {selectedHour}:{selectedMinute} {selectedPeriod} →
          </>
        )}
      </Button>
    </div>
  );
};

const SUGGESTIONS = [
  "Draft Architecture RFC 90m high priority, gym 45m, buy groceries 30m",
  "Standup meeting 30m, deep work coding 120m, client review 45m",
  "Yes, save it",
  "Rollback to version 1",
];

export const ChatPane: React.FC<ChatPaneProps> = ({
  messages,
  onSendMessage,
  isLoading,
  sessionId,
  onResetSession,
  focusTrigger = 0,
  onDateChange,
}) => {
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const handleActionChipClick = (chip: string, msgContent: string) => {
    // Extract habit task name if present, e.g. "What time would you prefer to schedule your Gym Session?"
    const match = msgContent.match(/schedule your ([^?]+)\?/i);
    const taskName = match ? match[1].trim() : "task";

    if (chip.toLowerCase().includes("specify time")) {
      setInput(`Schedule ${taskName} at `);
      inputRef.current?.focus();
      return;
    }

    const timeMatch = chip.match(/\((\d{1,2}:\d{2})\)/);
    if (timeMatch) {
      const timeStr = timeMatch[1];
      onSendMessage(`Schedule ${taskName} at ${timeStr} for 45m`);
    } else {
      onSendMessage(`Schedule ${taskName} at ${chip} for 45m`);
    }
  };

  const scrollToBottom = () => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  useEffect(() => {
    if (focusTrigger > 0) {
      inputRef.current?.focus();
    }
  }, [focusTrigger]);

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!input.trim() || isLoading) return;

    const messageText = input.trim();
    setInput("");
    await onSendMessage(messageText);
    inputRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div id="chat-pane-root" className="flex h-full flex-col bg-zinc-950 text-zinc-100">
      {/* Header */}
      <div className="flex h-14 shrink-0 items-center justify-between border-b border-zinc-800/80 px-4 bg-zinc-900/40 backdrop-blur-md">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600/20 text-indigo-400 ring-1 ring-indigo-500/30">
            <Bot className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-sm font-semibold tracking-tight text-zinc-100 flex items-center gap-1.5">
              Routine Concierge
              <span className="flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            </h2>
            <p className="text-[11px] text-zinc-400">
              Active Assistant
            </p>
          </div>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={onResetSession}
          className="h-8 gap-1.5 text-xs text-zinc-400 hover:text-zinc-200"
          title="Start fresh conversation"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          New Session
        </Button>
      </div>

      {/* Message List */}
      <ScrollArea id="chat-messages-container" className="flex-1 p-4">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center p-8 text-center text-zinc-500 min-h-[300px]">
            <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-zinc-900 text-indigo-400 border border-zinc-800 shadow-inner">
              <MessageSquare className="h-6 w-6" />
            </div>
            <h3 className="text-sm font-medium text-zinc-300">Daily Routine Assistant</h3>
            <p className="mt-1 max-w-xs text-xs text-zinc-500">
              Share natural-language to-dos, brain dumps, or routine notes. I will prioritize,
              schedule deep work with recovery buffers, and guard your energy.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            <AnimatePresence initial={false}>
              {messages.map((msg, idx) => (
                <motion.div
                  key={msg.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.25 }}
                  className={`flex gap-3 ${
                    msg.role === "user" ? "justify-end" : "justify-start"
                  }`}
                >
                  {msg.role === "assistant" && (
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-indigo-600/20 text-indigo-400 border border-indigo-500/30 mt-1">
                      <Sparkles className="h-3.5 w-3.5" />
                    </div>
                  )}

                  <div
                    className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed overflow-hidden break-words ${
                      msg.role === "user"
                        ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/20 rounded-tr-sm"
                        : "bg-zinc-900/90 text-zinc-200 border border-zinc-800 shadow-sm rounded-tl-sm"
                    }`}
                  >
                    {/* Collapsible Reasoning Drawer */}
                    {msg.role === "assistant" && msg.thought && (
                      <ThoughtAccordion
                        id={idx === 0 ? "reasoning-trace-accordion" : undefined}
                        thought={msg.thought}
                        defaultOpen={false}
                      />
                    )}

                    {/* Conversational Text */}
                    <div className="break-words">
                      {msg.role === "assistant" ? (
                        <div className="prose prose-invert prose-sm max-w-none">
                          <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            components={{
                              table: ({ node, ...props }) => (
                                <div className="my-2 w-full overflow-x-auto rounded-lg border border-border">
                                  <table className="w-full text-left text-xs" {...props} />
                                </div>
                              ),
                              th: ({ node, ...props }) => (
                                <th className="border-b bg-muted/60 px-3 py-2 font-medium text-zinc-200" {...props} />
                              ),
                              td: ({ node, ...props }) => (
                                <td className="border-b border-border/50 px-3 py-2 text-zinc-300" {...props} />
                              ),
                              thead: ({ node, ...props }) => (
                                <thead className="bg-muted/60" {...props} />
                              ),
                              p: ({ node, ...props }) => (
                                <p className="my-1 leading-relaxed" {...props} />
                              ),
                              ul: ({ node, ...props }) => (
                                <ul className="my-2 ml-4 list-disc space-y-1 text-zinc-300" {...props} />
                              ),
                              ol: ({ node, ...props }) => (
                                <ol className="my-2 ml-4 list-decimal space-y-1 text-zinc-300" {...props} />
                              ),
                              li: ({ node, ...props }) => (
                                <li className="leading-relaxed" {...props} />
                              ),
                              strong: ({ node, ...props }) => (
                                <strong className="font-semibold text-zinc-100" {...props} />
                              ),
                              code: ({ node, ...props }) => (
                                <code className="rounded bg-zinc-800 px-1.5 py-0.5 font-mono text-xs text-indigo-300" {...props} />
                              ),
                            }}
                          >
                            {msg.content}
                          </ReactMarkdown>
                        </div>
                      ) : (
                        <div className="whitespace-pre-wrap">{msg.content}</div>
                      )}
                    </div>

                    {/* Duration Quick-Chips when agent asks for duration/end window */}
                    {msg.role === "assistant" &&
                      /(?:specify the target end time or duration|target end time or duration|how much time|how long)/i.test(
                        msg.content
                      ) && (
                        <div className="mt-3 pt-2.5 border-t border-zinc-800/80">
                          <p className="text-[11px] font-medium text-zinc-400 mb-1.5 flex items-center gap-1.5">
                            <Clock className="h-3 w-3 text-indigo-400" />
                            Select duration to block:
                          </p>
                          <div className="flex flex-wrap gap-1.5">
                            {["15 mins", "30 mins", "45 mins", "60 mins"].map((durationChip) => (
                              <button
                                key={durationChip}
                                type="button"
                                disabled={isLoading}
                                onClick={() => onSendMessage(durationChip)}
                                className="inline-flex items-center rounded-lg border border-indigo-500/30 bg-indigo-950/40 px-2.5 py-1 text-xs font-mono font-medium text-indigo-200 transition-all hover:border-indigo-400 hover:bg-indigo-600 hover:text-white shadow-sm active:scale-95 disabled:opacity-50"
                              >
                                {durationChip}
                              </button>
                            ))}
                          </div>
                        </div>
                      )}

                    {/* Interactive Habit Clarification Action Chips */}
                    {msg.role === "assistant" && msg.actionChips && msg.actionChips.length > 0 && (
                      <div className="mt-3 pt-2.5 border-t border-zinc-800/80">
                        <p className="text-[11px] font-medium text-zinc-400 mb-1.5 flex items-center gap-1.5">
                          <Clock className="h-3 w-3 text-indigo-400" />
                          Preferred time recommendation:
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                          {msg.actionChips.map((chip) => (
                            <Button
                              key={chip}
                              variant="outline"
                              size="sm"
                              disabled={isLoading}
                              onClick={() => handleActionChipClick(chip, msg.content)}
                              className="h-7 text-xs font-medium border-indigo-500/30 bg-indigo-950/40 text-indigo-200 hover:bg-indigo-600 hover:text-white hover:border-indigo-400 transition-all active:scale-95 disabled:opacity-50"
                            >
                              {chip}
                            </Button>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Inline Generative Date-Picker Card with Time + AM/PM */}
                    {msg.role === "assistant" &&
                      (msg.requiresDateSelection || msg.uiAction === "show_date_time_picker") && (
                        <InlineDatePickerCard
                          initialTitle={msg.defaultTask || getLabelFromUserPrompt(idx > 0 ? messages[idx - 1]?.content : undefined)}
                          disabled={isLoading}
                          onConfirm={({ title, dateStr, timeStr, durationMinutes }) => {
                            onDateChange?.(dateStr);
                            onSendMessage(`Schedule ${title} on ${dateStr} at ${timeStr} for ${durationMinutes}m`);
                          }}
                        />
                      )}

                    <div
                      className={`mt-1.5 text-[10px] ${
                        msg.role === "user" ? "text-indigo-200/70" : "text-zinc-500"
                      }`}
                    >
                      {msg.timestamp}
                    </div>
                  </div>

                  {msg.role === "user" && (
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-zinc-800 text-zinc-300 border border-zinc-700/60 mt-1">
                      <User className="h-3.5 w-3.5" />
                    </div>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>

            {/* Thinking / Streaming Indicator */}
            {isLoading && (
              <motion.div
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex items-center gap-3 text-zinc-400 text-xs py-2"
              >
                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-600/20 text-indigo-400 border border-indigo-500/30">
                  <Bot className="h-3.5 w-3.5 animate-spin" />
                </div>
                <div className="flex items-center gap-1.5 rounded-full bg-zinc-900/90 px-3.5 py-1.5 border border-zinc-800">
                  <span className="flex h-1.5 w-1.5 rounded-full bg-indigo-400 animate-ping" />
                  <BlurText
                    text="Evaluating energy windows & scheduling..."
                    delay={35}
                    className="text-xs text-indigo-300/80 font-mono"
                  />
                </div>
              </motion.div>
            )}

            <div ref={bottomRef} />
          </div>
        )}
      </ScrollArea>

      {/* Suggestion Chips */}
      <div id="chat-suggestions-tray" className="border-t border-zinc-800/50 bg-zinc-950/70 px-4 py-2">
        <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-none">
          {SUGGESTIONS.map((chip, idx) => (
            <button
              key={idx}
              type="button"
              disabled={isLoading}
              onClick={() => onSendMessage(chip)}
              className="shrink-0 rounded-full border border-zinc-800/80 bg-zinc-900/60 px-3 py-1 text-xs text-zinc-400 transition-colors hover:border-indigo-500/40 hover:bg-zinc-800 hover:text-zinc-200 disabled:opacity-50"
            >
              {chip}
            </button>
          ))}
        </div>
      </div>

      {/* Input Bar */}
      <div id="chat-input-area" className="border-t border-zinc-800/80 bg-zinc-900/50 p-4 backdrop-blur-md">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <textarea
            ref={inputRef}
            rows={2}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            placeholder="Describe your tasks, meetings, or approval... (Press Enter to send)"
            className="flex-1 resize-none rounded-xl border border-zinc-800 bg-zinc-950/90 px-3.5 py-2.5 text-sm text-zinc-100 placeholder-zinc-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:opacity-50"
          />
          <Button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="h-auto px-4 rounded-xl shrink-0"
          >
            <Send className="h-4 w-4" />
          </Button>
        </form>
      </div>
    </div>
  );
};

export default ChatPane;
