"use client";

import React, { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Bot, User, Sparkles, RefreshCw, MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ThoughtAccordion } from "./ThoughtAccordion";
import { BlurText } from "@/components/effects/BlurText";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export interface ChatMessageItem {
  id: string;
  role: "user" | "assistant";
  content: string;
  thought?: string | null;
  timestamp: string;
  isNew?: boolean;
}

interface ChatPaneProps {
  messages: ChatMessageItem[];
  onSendMessage: (msg: string) => Promise<void>;
  isLoading: boolean;
  sessionId: string;
  onResetSession: () => void;
  focusTrigger?: number;
}

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
}) => {
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

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
    <div className="flex h-full flex-col bg-zinc-950 text-zinc-100">
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
            <p className="text-[11px] text-zinc-400 font-mono truncate max-w-[180px]">
              {sessionId}
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
      <ScrollArea className="flex-1 p-4">
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
              {messages.map((msg) => (
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
                      <ThoughtAccordion thought={msg.thought} defaultOpen={false} />
                    )}

                    {/* Conversational Text */}
                    <div className="break-words">
                      {msg.role === "assistant" ? (
                        <div className="prose prose-invert prose-sm max-w-none">
                          <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            components={{
                              table: ({ ...props }) => (
                                <div className="my-2.5 w-full overflow-x-auto rounded-lg border border-zinc-800">
                                  <table className="w-full text-left text-xs" {...props} />
                                </div>
                              ),
                              thead: ({ ...props }) => (
                                <thead className="bg-zinc-800/60" {...props} />
                              ),
                              th: ({ ...props }) => (
                                <th
                                  className="border-b border-zinc-800 px-3 py-2 font-medium text-zinc-200"
                                  {...props}
                                />
                              ),
                              td: ({ ...props }) => (
                                <td
                                  className="border-b border-zinc-800/50 px-3 py-2 text-zinc-300"
                                  {...props}
                                />
                              ),
                              p: ({ ...props }) => (
                                <p className="my-1 leading-relaxed" {...props} />
                              ),
                              ul: ({ ...props }) => (
                                <ul className="my-2 ml-4 list-disc space-y-1 text-zinc-300" {...props} />
                              ),
                              ol: ({ ...props }) => (
                                <ol className="my-2 ml-4 list-decimal space-y-1 text-zinc-300" {...props} />
                              ),
                              li: ({ ...props }) => (
                                <li className="leading-relaxed" {...props} />
                              ),
                              strong: ({ ...props }) => (
                                <strong className="font-semibold text-zinc-100" {...props} />
                              ),
                              code: ({ ...props }) => (
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
      <div className="border-t border-zinc-800/50 bg-zinc-950/70 px-4 py-2">
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
      <div className="border-t border-zinc-800/80 bg-zinc-900/50 p-4 backdrop-blur-md">
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
