"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Sparkles,
  ChevronRight,
  ChevronLeft,
  X,
  Check,
  Brain,
  MessageSquare,
  Activity,
  ShieldCheck,
  Download,
} from "lucide-react";
import { Button } from "@/components/ui/button";

export interface TourStep {
  id: string;
  target: string;
  fallbackTarget?: string;
  title: string;
  description: string;
  icon?: React.ReactNode;
  preferredPlacement?: "top" | "bottom" | "left" | "right";
}

export const TOUR_STEPS: TourStep[] = [
  {
    id: "step-1-input",
    target: "#chat-input-area",
    fallbackTarget: "#chat-pane-root",
    title: "1. Zero-Friction Input",
    description:
      "Type raw, unstructured natural language (e.g., 'Draft RFC 90m, gym 45m, groceries 30m'). You don't need to micromanage start times or calculate math.",
    icon: <MessageSquare className="h-4 w-4 text-indigo-400" />,
    preferredPlacement: "top",
  },
  {
    id: "step-2-reasoning",
    target: "#reasoning-trace-accordion",
    fallbackTarget: "#chat-messages-container",
    title: "2. ReAct Loop & Guardrails",
    description:
      "Inspect the agent's internal thought process, tool execution, and guardrail validations in real time before actions are committed.",
    icon: <Brain className="h-4 w-4 text-indigo-400" />,
    preferredPlacement: "bottom",
  },
  {
    id: "step-3-cognitive-balance",
    target: "#cognitive-balance-strip",
    fallbackTarget: "#schedule-board-header",
    title: "3. Cognitive Buffer Protection",
    description:
      "The agent strictly enforces recovery gaps between high-intensity focus blocks to prevent cognitive fatigue. The balance meter monitors your day's sustainability.",
    icon: <Activity className="h-4 w-4 text-indigo-400" />,
    preferredPlacement: "bottom",
  },
  {
    id: "step-4-confirmation",
    target: "#schedule-confirmation-banner",
    fallbackTarget: "#schedule-main-area",
    title: "4. Human-in-the-Loop Confirmation",
    description:
      "Schedules remain in draft state until you click 'Approve & Save to Storage'. You maintain total control before any routine is written to disk.",
    icon: <ShieldCheck className="h-4 w-4 text-emerald-400" />,
    preferredPlacement: "bottom",
  },
  {
    id: "step-5-audit-export",
    target: "#timeline-controls-header",
    fallbackTarget: "#schedule-board-header",
    title: "5. Audit History & Export",
    description:
      "Every change creates a versioned snapshot allowing instant one-click rollback. When satisfied, export directly to .ics or Google Calendar.",
    icon: <Download className="h-4 w-4 text-indigo-400" />,
    preferredPlacement: "bottom",
  },
];

interface CutoutRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

interface TooltipCoords {
  top: number;
  left: number;
  width: number;
}

interface WorkspaceTourProps {
  isOpen: boolean;
  onClose: () => void;
  onComplete?: () => void;
  steps?: TourStep[];
}

export const WorkspaceTour: React.FC<WorkspaceTourProps> = ({
  isOpen,
  onClose,
  onComplete,
  steps = TOUR_STEPS,
}) => {
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(0);
  const [cutout, setCutout] = useState<CutoutRect>({
    x: 0,
    y: 0,
    width: 0,
    height: 0,
  });
  const [tooltipPos, setTooltipPos] = useState<TooltipCoords>({
    top: 0,
    left: 0,
    width: 380,
  });
  const [isMeasuring, setIsMeasuring] = useState<boolean>(true);

  const currentStep = steps[currentStepIndex] || steps[0];
  const totalSteps = steps.length;

  // Measure and recalculate spotlight bounding rect
  const updateSpotlightPosition = useCallback(() => {
    if (!isOpen || typeof window === "undefined") return;

    let targetEl: Element | null = null;
    if (currentStep.target) {
      targetEl = document.querySelector(currentStep.target);
    }
    if (!targetEl && currentStep.fallbackTarget) {
      targetEl = document.querySelector(currentStep.fallbackTarget);
    }

    const padding = 8;
    const windowW = window.innerWidth;
    const windowH = window.innerHeight;

    let targetRect: DOMRect;
    if (targetEl) {
      targetRect = targetEl.getBoundingClientRect();
      // Ensure target is brought gently into view
      try {
        targetEl.scrollIntoView({
          behavior: "smooth",
          block: "nearest",
          inline: "nearest",
        });
      } catch {
        // ignore
      }
    } else {
      // Graceful fallback to centered region
      targetRect = {
        left: windowW / 2 - 200,
        top: windowH / 2 - 120,
        width: 400,
        height: 240,
        right: windowW / 2 + 200,
        bottom: windowH / 2 + 120,
        x: windowW / 2 - 200,
        y: windowH / 2 - 120,
        toJSON: () => {},
      };
    }

    const newCutout: CutoutRect = {
      x: Math.max(0, targetRect.left - padding),
      y: Math.max(0, targetRect.top - padding),
      width: Math.min(windowW, targetRect.width + padding * 2),
      height: Math.min(windowH, targetRect.height + padding * 2),
    };
    setCutout(newCutout);

    // Compute intelligent tooltip coordinates
    const tooltipWidth = Math.min(380, windowW - 32);
    const estimatedHeight = 220;
    const spacing = 16;
    const placement = currentStep.preferredPlacement || "bottom";

    let calculatedTop = 0;
    let calculatedLeft = newCutout.x + (newCutout.width - tooltipWidth) / 2;

    if (placement === "top") {
      calculatedTop = newCutout.y - estimatedHeight - spacing;
      if (calculatedTop < 16) {
        // Flip to bottom if clipping top
        calculatedTop = newCutout.y + newCutout.height + spacing;
      }
    } else {
      // "bottom"
      calculatedTop = newCutout.y + newCutout.height + spacing;
      if (calculatedTop + estimatedHeight > windowH - 16) {
        // Flip to top if clipping bottom
        calculatedTop = newCutout.y - estimatedHeight - spacing;
      }
    }

    // Viewport clamping
    const clampedLeft = Math.max(
      16,
      Math.min(windowW - tooltipWidth - 16, calculatedLeft)
    );
    const clampedTop = Math.max(
      16,
      Math.min(windowH - estimatedHeight - 16, calculatedTop)
    );

    setTooltipPos({
      top: clampedTop,
      left: clampedLeft,
      width: tooltipWidth,
    });
    setIsMeasuring(false);
  }, [isOpen, currentStep]);

  // Recalculate on mount, step change, resize, and scroll
  useEffect(() => {
    if (!isOpen) {
      setCurrentStepIndex(0);
      return;
    }

    setIsMeasuring(true);
    // Initial measure
    updateSpotlightPosition();

    // Short delayed check to allow smooth scroll settle
    const timer = setTimeout(updateSpotlightPosition, 100);

    const handleResizeOrScroll = () => {
      updateSpotlightPosition();
    };

    window.addEventListener("resize", handleResizeOrScroll);
    window.addEventListener("scroll", handleResizeOrScroll, true);

    return () => {
      clearTimeout(timer);
      window.removeEventListener("resize", handleResizeOrScroll);
      window.removeEventListener("scroll", handleResizeOrScroll, true);
    };
  }, [isOpen, currentStepIndex, updateSpotlightPosition]);

  // Keyboard navigation: Escape to close, arrows to advance/back
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        handleDismiss();
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        handleNext();
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        handleBack();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, currentStepIndex]);

  const handleNext = () => {
    if (currentStepIndex < totalSteps - 1) {
      setCurrentStepIndex((prev) => prev + 1);
    } else {
      handleComplete();
    }
  };

  const handleBack = () => {
    if (currentStepIndex > 0) {
      setCurrentStepIndex((prev) => prev - 1);
    }
  };

  const handleDismiss = () => {
    onClose();
  };

  const handleComplete = () => {
    onClose();
    if (onComplete) {
      onComplete();
    }
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-[9990] overflow-hidden select-none pointer-events-auto">
        {/* 1. Fullscreen SVG Cutout Mask (Dims page except spotlighted element) */}
        <svg className="fixed inset-0 h-full w-full pointer-events-none z-[9991]">
          <defs>
            <mask id="tour-spotlight-mask">
              {/* White area retains full dark backdrop */}
              <rect x="0" y="0" width="100%" height="100%" fill="white" />
              {/* Black cutout punches hole revealing live component */}
              <motion.rect
                animate={{
                  x: cutout.x,
                  y: cutout.y,
                  width: cutout.width,
                  height: cutout.height,
                  rx: 14,
                }}
                transition={{
                  type: "spring",
                  damping: 28,
                  stiffness: 280,
                }}
                fill="black"
              />
            </mask>
          </defs>
          {/* Dimmed backdrop layer with backdrop-blur */}
          <rect
            x="0"
            y="0"
            width="100%"
            height="100%"
            fill="rgba(0, 0, 0, 0.78)"
            mask="url(#tour-spotlight-mask)"
            className="pointer-events-auto"
            onClick={handleNext}
          />
        </svg>

        {/* 2. Vibrant Spotlight Border & Glow Frame */}
        <motion.div
          animate={{
            left: cutout.x,
            top: cutout.y,
            width: cutout.width,
            height: cutout.height,
          }}
          transition={{
            type: "spring",
            damping: 28,
            stiffness: 280,
          }}
          className="fixed z-[9992] pointer-events-none rounded-xl border border-indigo-400/70 ring-2 ring-indigo-500/80 shadow-[0_0_35px_rgba(99,102,241,0.4)]"
        />

        {/* 3. Interactive Tour Tooltip Popover Card */}
        <motion.div
          key={currentStep.id}
          initial={{ opacity: 0, scale: 0.95, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 10 }}
          transition={{ duration: 0.22, ease: "easeOut" }}
          style={{
            top: tooltipPos.top,
            left: tooltipPos.left,
            width: tooltipPos.width,
          }}
          className="fixed z-[9995] rounded-2xl border border-zinc-800 bg-zinc-900/95 p-5 text-zinc-100 shadow-2xl backdrop-blur-2xl ring-1 ring-zinc-700/50"
        >
          {/* Header Bar */}
          <div className="flex items-center justify-between pb-3 border-b border-zinc-800/80">
            <div className="flex items-center gap-2">
              <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-indigo-500/20 text-indigo-400">
                {currentStep.icon || <Sparkles className="h-3.5 w-3.5" />}
              </div>
              <span className="rounded-full bg-indigo-500/15 border border-indigo-500/30 px-2.5 py-0.5 text-[11px] font-mono font-medium text-indigo-300">
                Step {currentStepIndex + 1} of {totalSteps}
              </span>
            </div>

            <button
              onClick={handleDismiss}
              className="rounded-lg p-1 text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-200"
              title="Close Tour (Esc)"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Title & Body Description */}
          <div className="my-3.5 space-y-1.5">
            <h3 className="text-sm sm:text-base font-bold tracking-tight text-white flex items-center gap-2">
              {currentStep.title}
            </h3>
            <p className="text-xs leading-relaxed text-zinc-300">
              {currentStep.description}
            </p>
          </div>

          {/* Step Progress Dots Indicator */}
          <div className="flex items-center gap-1.5 py-2">
            {steps.map((s, idx) => (
              <div
                key={s.id}
                onClick={() => setCurrentStepIndex(idx)}
                className={`h-1.5 rounded-full cursor-pointer transition-all duration-300 ${
                  idx === currentStepIndex
                    ? "w-6 bg-indigo-500"
                    : idx < currentStepIndex
                    ? "w-2 bg-indigo-500/50 hover:bg-indigo-400"
                    : "w-2 bg-zinc-700 hover:bg-zinc-600"
                }`}
                title={`Jump to Step ${idx + 1}`}
              />
            ))}
          </div>

          {/* Footer Controls & Navigation */}
          <div className="mt-2 flex items-center justify-between pt-2">
            <button
              type="button"
              onClick={handleDismiss}
              className="text-xs text-zinc-400 hover:text-zinc-200 underline-offset-4 hover:underline"
            >
              Skip Tour
            </button>

            <div className="flex items-center gap-2">
              {currentStepIndex > 0 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleBack}
                  className="h-8 px-2.5 text-xs text-zinc-300 border-zinc-700 hover:bg-zinc-800"
                >
                  <ChevronLeft className="h-3.5 w-3.5 mr-0.5" />
                  Back
                </Button>
              )}

              <Button
                size="sm"
                onClick={handleNext}
                className="h-8 px-3.5 text-xs bg-indigo-600 hover:bg-indigo-500 text-white shadow-md shadow-indigo-600/30 font-medium flex items-center gap-1"
              >
                <span>
                  {currentStepIndex === totalSteps - 1
                    ? "Get Started"
                    : "Next"}
                </span>
                {currentStepIndex === totalSteps - 1 ? (
                  <Check className="h-3.5 w-3.5" />
                ) : (
                  <ChevronRight className="h-3.5 w-3.5" />
                )}
              </Button>
            </div>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};

export default WorkspaceTour;
