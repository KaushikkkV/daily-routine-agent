"use client";

import React from "react";
import { motion } from "framer-motion";
import {
  Clock,
  Coffee,
  Sparkles,
  Zap,
  Activity,
  CheckCircle2,
  AlertCircle,
  ShieldAlert,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { BorderGlow } from "@/components/effects/BorderGlow";
import { TimeBlock, TaskItem } from "@/lib/api";

interface ScheduleBlockCardProps {
  block: TimeBlock;
  task?: TaskItem;
  isPendingApproval?: boolean;
}

export const ScheduleBlockCard: React.FC<ScheduleBlockCardProps> = ({
  block,
  task,
  isPendingApproval = false,
}) => {
  // Format times (e.g. "09:00:00" -> "09:00")
  const formatTime = (t: string) => {
    if (!t) return "";
    const parts = t.split(":");
    return parts.length >= 2 ? `${parts[0]}:${parts[1]}` : t;
  };

  const startTimeStr = formatTime(block.start_time);
  const endTimeStr = formatTime(block.end_time);

  // Calculate approximate duration in minutes
  const getMinutes = () => {
    if (task?.estimated_minutes) return task.estimated_minutes;
    try {
      const [sh, sm] = startTimeStr.split(":").map(Number);
      const [eh, em] = endTimeStr.split(":").map(Number);
      return eh * 60 + em - (sh * 60 + sm);
    } catch {
      return 0;
    }
  };
  const durationMinutes = getMinutes();

  // Energy & Category Styling
  const isBuffer = block.is_buffer;
  const category = task?.category || (isBuffer ? "Buffer" : "Task");

  type BadgeVariantType =
    | "default"
    | "buffer"
    | "deepWork"
    | "shallow"
    | "health"
    | "critical"
    | "secondary"
    | "destructive"
    | "outline";

  let cardAccent: {
    badgeVariant: BadgeVariantType;
    borderGlowColor: string;
    icon: React.ComponentType<{ className?: string }>;
    bgGradient: string;
    labelColor: string;
    glowActive: boolean;
  } = {
    badgeVariant: "default",
    borderGlowColor: "#6366f1",
    icon: Zap,
    bgGradient: "from-zinc-900 to-zinc-950",
    labelColor: "text-zinc-100",
    glowActive: false,
  };

  if (isBuffer) {
    cardAccent = {
      badgeVariant: "buffer",
      borderGlowColor: "#10b981", // emerald
      icon: Coffee,
      bgGradient: "from-emerald-950/20 to-zinc-950/60",
      labelColor: "text-emerald-300",
      glowActive: isPendingApproval,
    };
  } else if (category === "Deep Work") {
    cardAccent = {
      badgeVariant: "deepWork",
      borderGlowColor: "#8b5cf6", // violet / indigo
      icon: Zap,
      bgGradient: "from-indigo-950/30 via-zinc-900/60 to-zinc-950",
      labelColor: "text-indigo-200",
      glowActive: isPendingApproval,
    };
  } else if (category === "Health") {
    cardAccent = {
      badgeVariant: "health",
      borderGlowColor: "#06b6d4", // cyan
      icon: Activity,
      bgGradient: "from-cyan-950/25 to-zinc-950/60",
      labelColor: "text-cyan-200",
      glowActive: isPendingApproval,
    };
  } else if (category === "Shallow Work" || category === "Errands") {
    cardAccent = {
      badgeVariant: "shallow",
      borderGlowColor: "#f59e0b", // amber
      icon: Sparkles,
      bgGradient: "from-amber-950/20 to-zinc-950/60",
      labelColor: "text-amber-200",
      glowActive: isPendingApproval,
    };
  }

  const IconComponent = cardAccent.icon;

  const cardInner = (
    <div
      className={`flex items-start justify-between p-4 rounded-xl border border-zinc-800/80 bg-gradient-to-r ${cardAccent.bgGradient} transition-all duration-300 hover:border-zinc-700`}
    >
      {/* Left Column: Time & Icon */}
      <div className="flex items-start gap-3.5">
        <div
          className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border ${
            isBuffer
              ? "bg-emerald-500/15 border-emerald-500/30 text-emerald-400"
              : category === "Deep Work"
              ? "bg-indigo-500/15 border-indigo-500/30 text-indigo-400"
              : "bg-zinc-800/80 border-zinc-700/60 text-zinc-300"
          }`}
        >
          <IconComponent className="h-5 w-5" />
        </div>

        <div>
          {/* Timeslot and Duration */}
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-semibold tracking-tight text-zinc-300 flex items-center gap-1">
              <Clock className="h-3 w-3 text-zinc-500" />
              {startTimeStr} - {endTimeStr}
            </span>
            {durationMinutes > 0 && (
              <span className="text-[11px] font-mono text-zinc-500">
                ({durationMinutes}m)
              </span>
            )}
          </div>

          {/* Block Title / Label */}
          <h4 className={`mt-1 text-sm font-semibold tracking-tight ${cardAccent.labelColor}`}>
            {block.label}
          </h4>

          {/* Additional details / notes */}
          {isBuffer ? (
            <p className="mt-0.5 text-xs text-emerald-400/80 font-medium">
              Mandatory recovery slack to reset cognitive depletion
            </p>
          ) : (
            <div className="mt-1 flex items-center gap-2">
              <Badge variant={cardAccent.badgeVariant}>{category}</Badge>
              {task?.priority && (
                <span
                  className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full border ${
                    task.priority === "Critical"
                      ? "bg-rose-500/20 text-rose-300 border-rose-500/40 animate-pulse"
                      : task.priority === "High"
                      ? "bg-amber-500/20 text-amber-300 border-amber-500/40"
                      : "bg-zinc-800 text-zinc-400 border-zinc-700"
                  }`}
                >
                  {task.priority} Priority
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Right Column: Status or Pending Pill */}
      <div className="shrink-0 text-right">
        {isPendingApproval ? (
          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-400 bg-amber-500/10 px-2.5 py-1 rounded-full border border-amber-500/30">
            <AlertCircle className="h-3 w-3" />
            Draft
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-400/90 bg-emerald-500/10 px-2.5 py-1 rounded-full border border-emerald-500/20">
            <CheckCircle2 className="h-3 w-3" />
            Committed
          </span>
        )}
      </div>
    </div>
  );

  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{
        type: "spring",
        stiffness: 300,
        damping: 25,
      }}
      className="w-full"
    >
      {isPendingApproval ? (
        <BorderGlow
          glowColor={cardAccent.borderGlowColor}
          glowOpacity={0.6}
          borderRadius={14}
          active={true}
        >
          {cardInner}
        </BorderGlow>
      ) : (
        cardInner
      )}
    </motion.div>
  );
};

export default ScheduleBlockCard;
