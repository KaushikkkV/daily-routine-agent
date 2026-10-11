"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Brain, ChevronDown, Sparkles, Terminal } from "lucide-react";
import { cn } from "@/lib/utils";

interface ThoughtAccordionProps {
  id?: string;
  thought?: string | null;
  className?: string;
  defaultOpen?: boolean;
}

export const ThoughtAccordion: React.FC<ThoughtAccordionProps> = ({
  id,
  thought,
  className = "",
  defaultOpen = false,
}) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  if (!thought || !thought.trim()) {
    return null;
  }

  // Split into reasoning blocks if multiple thoughts/steps exist
  const thoughtLines = thought
    .split("\n\n")
    .map((s) => s.trim())
    .filter(Boolean);

  return (
    <div
      id={id}
      className={cn(
        "my-2.5 overflow-hidden rounded-xl border border-indigo-900/40 bg-zinc-950/80 shadow-sm transition-all duration-200",
        isOpen && "border-indigo-500/40 ring-1 ring-indigo-500/20",
        className
      )}
    >
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex w-full items-center justify-between px-3.5 py-2.5 text-left text-xs text-indigo-300/90 transition-colors hover:bg-indigo-950/30"
      >
        <div className="flex items-center gap-2">
          <div className="flex h-5 w-5 items-center justify-center rounded-md bg-indigo-500/20 text-indigo-400">
            <Brain className="h-3 w-3 animate-pulse" />
          </div>
          <span className="font-medium tracking-wide">
            Reasoning Process ({thoughtLines.length} step{thoughtLines.length > 1 ? "s" : ""})
          </span>
          <span className="rounded-full bg-indigo-500/10 px-2 py-0.5 text-[10px] text-indigo-400">
            ReAct Trace
          </span>
        </div>
        <motion.div
          animate={{ rotate: isOpen ? 180 : 0 }}
          transition={{ duration: 0.2 }}
        >
          <ChevronDown className="h-3.5 w-3.5 text-indigo-400" />
        </motion.div>
      </button>

      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: "easeInOut" }}
          >
            <div className="border-t border-indigo-950/60 bg-zinc-950/90 px-3.5 py-3 text-xs leading-relaxed text-zinc-300">
              <div className="space-y-2 font-mono text-[11px]">
                {thoughtLines.map((line, idx) => (
                  <div
                    key={idx}
                    className="flex items-start gap-2 rounded-lg bg-zinc-900/60 p-2 text-zinc-300 border border-zinc-800/60"
                  >
                    <Terminal className="mt-0.5 h-3 w-3 shrink-0 text-indigo-400" />
                    <span className="whitespace-pre-wrap">{line}</span>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default ThoughtAccordion;
