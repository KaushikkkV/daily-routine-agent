"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Sparkles,
  BrainCircuit,
  History,
  ArrowRight,
  ArrowLeft,
  CheckCircle2,
  Calendar,
  Layers,
  ShieldCheck,
  Zap,
} from "lucide-react";

interface TutorialModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onComplete?: () => void;
}

interface StepData {
  badge: string;
  badgeVariant: "default" | "secondary" | "deepWork" | "buffer" | "shallow" | "health";
  title: string;
  subtitle: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  accentColor: string;
  interactivePreview: React.ReactNode;
  bulletPoints: string[];
}

export const TutorialModal: React.FC<TutorialModalProps> = ({
  open,
  onOpenChange,
  onComplete,
}) => {
  const [currentStep, setCurrentStep] = useState<number>(0);

  const steps: StepData[] = [
    {
      badge: "Step 1 of 3: Pragmatic Parsing",
      badgeVariant: "deepWork",
      title: "Dump your tasks",
      subtitle: "Deterministic Execution. Zero Interrogation.",
      description:
        "Input freeform to-do lists, voice transcripts, or messy notes without micromanaging minute-by-minute details. The Concierge automatically normalizes titles, infers reasonable durations, and assigns default priorities.",
      icon: Sparkles,
      accentColor: "#6366f1", // Indigo
      bulletPoints: [
        "Routine errands automatically assume 15-30m defaults.",
        "Zero friction: No endless questions for routine minor tasks.",
        "Deterministic normalization into validated task objects.",
      ],
      interactivePreview: (
        <div className="rounded-xl border border-indigo-500/20 bg-indigo-950/20 p-4 font-mono text-xs text-zinc-300">
          <div className="flex items-center gap-2 text-indigo-400 font-semibold mb-2">
            <Sparkles className="h-3.5 w-3.5" />
            <span>Natural Language Ingestion</span>
          </div>
          <div className="rounded-lg bg-zinc-900/90 p-2.5 text-zinc-400 border border-zinc-800">
            &quot;Draft system architecture RFC 90m high priority, gym workout, groceries between 9am and 2pm.&quot;
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="rounded-md bg-indigo-500/20 px-2 py-0.5 text-[11px] text-indigo-300 border border-indigo-500/30">
              ⚡ Deep Work: 90m (High)
            </span>
            <span className="rounded-md bg-cyan-500/20 px-2 py-0.5 text-[11px] text-cyan-300 border border-cyan-500/30">
              🏃 Gym Workout: 45m (Normal)
            </span>
            <span className="rounded-md bg-amber-500/20 px-2 py-0.5 text-[11px] text-amber-300 border border-amber-500/30">
              🛒 Groceries: 30m (Normal)
            </span>
          </div>
        </div>
      ),
    },
    {
      badge: "Step 2 of 3: Energy-First Scheduling",
      badgeVariant: "buffer",
      title: "Autonomous buffers",
      subtitle: "Autonomous Chronobiology & Rest Safeguards",
      description:
        "Deep work drains mental stamina. The agent's ReAct loop schedules high-focus blocks in early peak energy hours, and mandatorily sandwiches each sprint with a 10-minute cognitive recovery buffer to protect you from burnout.",
      icon: BrainCircuit,
      accentColor: "#10b981", // Emerald
      bulletPoints: [
        "Morning slots prioritized for Deep Work & Critical objectives.",
        "Mandatory 10-minute recovery slack following deep work sprints.",
        "Multi-turn ReAct ceiling supports up to 10 reasoning iterations.",
      ],
      interactivePreview: (
        <div className="rounded-xl border border-emerald-500/20 bg-emerald-950/20 p-4 font-mono text-xs text-zinc-300">
          <div className="flex items-center gap-2 text-emerald-400 font-semibold mb-2">
            <Zap className="h-3.5 w-3.5" />
            <span>Interactive Timeline Blocks</span>
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between rounded-lg border border-indigo-500/30 bg-indigo-900/30 px-3 py-2 text-indigo-200">
              <span className="font-sans font-medium text-xs">09:00 - 10:30 • Draft System Architecture RFC</span>
              <span className="text-[10px] bg-indigo-500/30 px-1.5 py-0.5 rounded text-indigo-300">Deep Work (90m)</span>
            </div>
            <div className="flex items-center justify-between rounded-lg border border-emerald-500/40 bg-emerald-900/30 px-3 py-1.5 text-emerald-300">
              <span className="font-sans text-xs flex items-center gap-1.5 font-medium">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                10:30 - 10:40 • Deep Work Recovery Buffer
              </span>
              <span className="text-[10px] bg-emerald-500/30 px-1.5 py-0.5 rounded text-emerald-200">Recovery Slack</span>
            </div>
          </div>
        </div>
      ),
    },
    {
      badge: "Step 3 of 3: State Safety & Snapshots",
      badgeVariant: "shallow",
      title: "Snapshots & Rollback",
      subtitle: "Event-Sourced Versioning & Storage Confirmation",
      description:
        "Every approved change or rearrangement increments the schedule's immutable version ID. You can inspect previous versions and perform an instant 1-click rollback with full conversational memory preserved.",
      icon: History,
      accentColor: "#f59e0b", // Amber
      bulletPoints: [
        "Strict boundary: Storage persistence requires explicit user confirmation.",
        "1-click version rollback via revert_schedule_to_version.",
        "ACID session persistence backed by local SQLite storage.",
      ],
      interactivePreview: (
        <div className="rounded-xl border border-amber-500/20 bg-amber-950/20 p-4 font-mono text-xs text-zinc-300">
          <div className="flex items-center justify-between text-amber-400 font-semibold mb-2">
            <div className="flex items-center gap-2">
              <Layers className="h-3.5 w-3.5" />
              <span>Version Snapshot Timeline</span>
            </div>
            <span className="rounded bg-amber-500/20 px-1.5 py-0.5 text-[10px] text-amber-300 border border-amber-500/30">
              v2 (Active)
            </span>
          </div>
          <div className="flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-900/90 p-2.5 text-xs text-zinc-300">
            <span>v1: Initial 3 tasks scheduled</span>
            <Button
              size="sm"
              variant="outline"
              className="h-6 text-[10px] border-amber-500/30 bg-amber-500/10 text-amber-300 hover:bg-amber-500/20"
            >
              <History className="h-3 w-3 mr-1" />
              Revert to v1
            </Button>
          </div>
        </div>
      ),
    },
  ];

  const handleNext = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep((prev) => prev + 1);
    } else {
      onOpenChange(false);
      onComplete?.();
    }
  };

  const handlePrev = () => {
    if (currentStep > 0) {
      setCurrentStep((prev) => prev - 1);
    }
  };

  const step = steps[currentStep];
  const StepIcon = step.icon;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl border-zinc-800 bg-zinc-950/95 p-6 backdrop-blur-2xl">
        <DialogHeader>
          <div className="flex items-center justify-between pr-6">
            <Badge variant={step.badgeVariant}>{step.badge}</Badge>
            {/* Step Indicators */}
            <div className="flex items-center gap-1.5">
              {steps.map((_, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => setCurrentStep(idx)}
                  className={`h-1.5 rounded-full transition-all duration-300 ${
                    idx === currentStep
                      ? "w-6 bg-indigo-500"
                      : "w-2 bg-zinc-700 hover:bg-zinc-600"
                  }`}
                  aria-label={`Jump to step ${idx + 1}`}
                />
              ))}
            </div>
          </div>

          <div className="mt-3 flex items-center gap-3">
            <div
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-white shadow-lg"
              style={{
                backgroundColor: step.accentColor,
                boxShadow: `0 4px 14px ${step.accentColor}33`,
              }}
            >
              <StepIcon className="h-5 w-5" />
            </div>
            <div>
              <DialogTitle className="text-xl font-bold tracking-tight text-zinc-100">
                {step.title}
              </DialogTitle>
              <p className="text-xs font-medium text-zinc-400">{step.subtitle}</p>
            </div>
          </div>
        </DialogHeader>

        {/* Step Body */}
        <div className="mt-4 space-y-4">
          <AnimatePresence mode="wait">
            <motion.div
              key={currentStep}
              initial={{ opacity: 0, x: 15 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -15 }}
              transition={{ duration: 0.2 }}
              className="space-y-4"
            >
              <DialogDescription>{step.description}</DialogDescription>

              {/* Interactive Visual Card */}
              {step.interactivePreview}

              {/* Bullet highlights */}
              <ul className="space-y-1.5 pt-1 text-xs text-zinc-300">
                {step.bulletPoints.map((bullet, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <CheckCircle2 className="h-3.5 w-3.5 mt-0.5 text-emerald-400 shrink-0" />
                    <span>{bullet}</span>
                  </li>
                ))}
              </ul>
            </motion.div>
          </AnimatePresence>
        </div>

        {/* Footer Navigation */}
        <DialogFooter className="mt-6 flex flex-row items-center justify-between border-t border-zinc-800/80 pt-4 sm:justify-between">
          <Button
            variant="ghost"
            size="sm"
            onClick={handlePrev}
            disabled={currentStep === 0}
            className="text-xs text-zinc-400 hover:text-zinc-200"
          >
            <ArrowLeft className="h-3.5 w-3.5 mr-1.5" />
            Back
          </Button>

          <div className="flex items-center gap-2">
            {currentStep < steps.length - 1 ? (
              <Button
                variant="default"
                size="sm"
                onClick={handleNext}
                className="bg-indigo-600 hover:bg-indigo-500 text-white shadow-md shadow-indigo-600/30 text-xs px-4"
              >
                Next Step
                <ArrowRight className="h-3.5 w-3.5 ml-1.5" />
              </Button>
            ) : (
              <Button
                variant="default"
                size="sm"
                onClick={handleNext}
                className="bg-emerald-600 hover:bg-emerald-500 text-white shadow-md shadow-emerald-600/30 text-xs px-4"
              >
                Launch Workspace
                <CheckCircle2 className="h-3.5 w-3.5 ml-1.5" />
              </Button>
            )}
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default TutorialModal;
