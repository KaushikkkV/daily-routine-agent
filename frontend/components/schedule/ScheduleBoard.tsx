"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Calendar,
  History,
  RotateCcw,
  Check,
  AlertTriangle,
  Clock,
  Zap,
  Coffee,
  CheckCircle,
  Sparkles,
  ChevronDown,
  Edit3,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { BorderGlow } from "@/components/effects/BorderGlow";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
} from "@/components/ui/dropdown-menu";
import { ScheduleBlockCard } from "./ScheduleBlockCard";
import { DailySchedule, ScheduleVersion, TaskItem } from "@/lib/api";

interface ScheduleBoardProps {
  schedule?: DailySchedule | null;
  currentVersionId: number;
  versionHistory: ScheduleVersion[];
  pendingApproval: boolean;
  onApprove: () => Promise<void>;
  onRollback: (versionId: number) => Promise<void>;
  onAdjustSchedule?: () => void;
  isApproving: boolean;
  isRollingBack: boolean;
}

export const ScheduleBoard: React.FC<ScheduleBoardProps> = ({
  schedule,
  currentVersionId,
  versionHistory,
  pendingApproval,
  onApprove,
  onRollback,
  onAdjustSchedule,
  isApproving,
  isRollingBack,
}) => {
  // Compute summary stats
  const blocks = schedule?.time_blocks || [];
  const tasks = schedule?.tasks_allocated || [];
  const bufferMins = schedule?.buffer_time_minutes || 0;

  const deepWorkMins = tasks
    .filter((t) => t.category === "Deep Work")
    .reduce((acc, t) => acc + (t.estimated_minutes || 0), 0);

  const totalWorkMins = tasks.reduce(
    (acc, t) => acc + (t.estimated_minutes || 0),
    0
  );

  const taskMap = new Map<string, TaskItem>();
  tasks.forEach((t) => {
    taskMap.set(t.id, t);
    taskMap.set(t.title.toLowerCase(), t);
  });

  return (
    <div className="flex h-full flex-col bg-zinc-950 text-zinc-100">
      {/* Header with high stacking context */}
      <div className="relative z-30 flex h-14 shrink-0 items-center justify-between border-b border-zinc-800/80 px-5 bg-zinc-900/40 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600/20 text-indigo-400 ring-1 ring-indigo-500/30">
            <Calendar className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-sm font-semibold tracking-tight text-zinc-100 flex items-center gap-2">
              Timeline Agenda
              {schedule?.date && (
                <span className="text-xs font-mono font-normal text-zinc-400">
                  [{schedule.date}]
                </span>
              )}
            </h2>
          </div>
        </div>

        {/* Version Badge & History Controls */}
        <div className="flex items-center gap-2">
          <BorderGlow
            glowColor={pendingApproval ? "#f59e0b" : "#6366f1"}
            glowOpacity={0.6}
            borderRadius={20}
            active={pendingApproval}
            className="rounded-full"
          >
            <div className="flex items-center gap-1.5 px-3 py-1 bg-zinc-900 rounded-full border border-zinc-800 text-xs font-mono">
              <span className="text-zinc-400">Ver:</span>
              <span className={pendingApproval ? "text-amber-400 font-bold" : "text-indigo-400 font-bold"}>
                v{currentVersionId}
              </span>
              {pendingApproval && (
                <span className="h-1.5 w-1.5 rounded-full bg-amber-400 animate-ping" />
              )}
            </div>
          </BorderGlow>

          {/* Version History Dropdown with Root DOM Portal & z-[100] */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="h-8 gap-1.5 text-xs text-zinc-300 border-zinc-800 hover:bg-zinc-800"
              >
                <History className="h-3.5 w-3.5 text-zinc-400" />
                Snapshots ({versionHistory.length})
                <ChevronDown className="h-3 w-3 text-zinc-500" />
              </Button>
            </DropdownMenuTrigger>

            <DropdownMenuContent
              align="end"
              sideOffset={4}
              className="w-80 p-2 z-[100] border-zinc-800 bg-zinc-900/95 shadow-2xl backdrop-blur-md"
            >
              <div className="px-2 py-1.5 text-xs font-semibold text-zinc-400 border-b border-zinc-800/80 flex items-center justify-between">
                <span>Audit Trail Snapshots</span>
                <span className="text-[10px] font-mono text-zinc-500">Monotonic IDs</span>
              </div>

              <div className="mt-1.5 max-h-60 overflow-y-auto space-y-1.5 scrollbar-thin">
                {versionHistory.length === 0 ? (
                  <p className="p-3 text-center text-xs text-zinc-500">
                    No saved version snapshots yet.
                  </p>
                ) : (
                  versionHistory.map((ver) => (
                    <div
                      key={ver.version_id}
                      className={`flex items-center justify-between rounded-lg p-2 text-xs transition-colors ${
                        ver.version_id === currentVersionId
                          ? "bg-indigo-950/40 border border-indigo-500/30 text-indigo-200"
                          : "hover:bg-zinc-800 text-zinc-300"
                      }`}
                    >
                      <div className="min-w-0 pr-2">
                        <div className="flex items-center gap-1.5">
                          <span className="font-mono font-bold text-indigo-400">
                            v{ver.version_id}
                          </span>
                          <span className="text-[10px] text-zinc-500 truncate max-w-[130px]">
                            {new Date(ver.timestamp).toLocaleTimeString([], {
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </span>
                        </div>
                        <p className="truncate text-[11px] text-zinc-400 mt-0.5">
                          {ver.change_summary}
                        </p>
                      </div>

                      {ver.version_id !== currentVersionId && (
                        <Button
                          variant="rollback"
                          size="sm"
                          disabled={isRollingBack}
                          onClick={async (e) => {
                            e.stopPropagation();
                            await onRollback(ver.version_id);
                          }}
                          className="h-7 px-2 text-[11px] shrink-0"
                        >
                          <RotateCcw className="h-3 w-3 mr-1" />
                          Revert
                        </Button>
                      )}
                    </div>
                  ))
                )}
              </div>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Main Content Area */}
      <ScrollArea className="flex-1 p-5">
        {/* Pending Approval Gate Alert Banner */}
        <AnimatePresence>
          {pendingApproval && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="mb-5"
            >
              <BorderGlow
                glowColor="#f59e0b"
                glowOpacity={0.7}
                borderRadius={16}
                active={true}
              >
                <div className="p-4 bg-gradient-to-r from-amber-950/40 via-zinc-900 to-zinc-950 border border-amber-500/40 rounded-2xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-lg shadow-amber-500/5">
                  <div className="flex items-start gap-3">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-amber-500/20 text-amber-400 border border-amber-500/30">
                      <AlertTriangle className="h-5 w-5" />
                    </div>
                    <div>
                      <h4 className="text-sm font-semibold text-amber-200">
                        Draft Schedule Awaiting Confirmation
                      </h4>
                      <p className="text-xs text-zinc-400 mt-0.5">
                        Storage persistence gate active. Please review the layout and approve to commit snapshot.
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={onAdjustSchedule}
                      className="h-9 px-3 text-xs text-zinc-300 border-zinc-700/80 hover:bg-zinc-800"
                    >
                      <Edit3 className="h-3.5 w-3.5 mr-1" />
                      Adjust Schedule
                    </Button>
                    <Button
                      variant="approve"
                      size="sm"
                      disabled={isApproving}
                      onClick={onApprove}
                      className="h-9 px-4 gap-1.5 font-medium shadow-md shadow-emerald-600/30"
                    >
                      <Check className="h-4 w-4" />
                      {isApproving ? "Saving..." : "Approve & Save to Storage"}
                    </Button>
                  </div>
                </div>
              </BorderGlow>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Aggregated Cognitive Load & Energy Metrics */}
        {schedule && blocks.length > 0 && (
          <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/50 p-3 backdrop-blur-sm">
              <div className="flex items-center gap-1.5 text-xs text-zinc-400">
                <Zap className="h-3.5 w-3.5 text-indigo-400" />
                <span>Deep Work</span>
              </div>
              <p className="mt-1 text-lg font-bold tracking-tight text-indigo-300 font-mono">
                {deepWorkMins}m
              </p>
            </div>

            <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/50 p-3 backdrop-blur-sm">
              <div className="flex items-center gap-1.5 text-xs text-zinc-400">
                <Coffee className="h-3.5 w-3.5 text-emerald-400" />
                <span>Recovery Slack</span>
              </div>
              <p className="mt-1 text-lg font-bold tracking-tight text-emerald-300 font-mono">
                {bufferMins}m
              </p>
            </div>

            <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/50 p-3 backdrop-blur-sm">
              <div className="flex items-center gap-1.5 text-xs text-zinc-400">
                <Clock className="h-3.5 w-3.5 text-amber-400" />
                <span>Total Work</span>
              </div>
              <p className="mt-1 text-lg font-bold tracking-tight text-zinc-200 font-mono">
                {totalWorkMins}m
              </p>
            </div>

            <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/50 p-3 backdrop-blur-sm">
              <div className="flex items-center gap-1.5 text-xs text-zinc-400">
                <CheckCircle className="h-3.5 w-3.5 text-cyan-400" />
                <span>Tasks Planned</span>
              </div>
              <p className="mt-1 text-lg font-bold tracking-tight text-zinc-200 font-mono">
                {tasks.length}
              </p>
            </div>
          </div>
        )}

        {/* Schedule Time Blocks Timeline */}
        {blocks.length === 0 ? (
          <div className="flex min-h-[340px] flex-col items-center justify-center rounded-2xl border border-dashed border-zinc-800 p-8 text-center text-zinc-500">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-zinc-900 text-zinc-600 border border-zinc-800 mb-3 shadow-inner">
              <Calendar className="h-7 w-7" />
            </div>
            <h3 className="text-sm font-semibold text-zinc-300">
              No Schedule Active
            </h3>
            <p className="mt-1 max-w-sm text-xs text-zinc-500">
              Type your commitments in the chat on the left (e.g. &ldquo;Draft RFC 90m high priority, gym 45m&rdquo;).
              The agent will pack energy-balanced blocks with automatic recovery buffers.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            <AnimatePresence>
              {blocks.map((block, idx) => {
                // Find matching task by task_id or label
                const mappedTask =
                  (block.task_id && taskMap.get(block.task_id)) ||
                  taskMap.get(block.label.toLowerCase()) ||
                  tasks.find((t) => block.label.toLowerCase().includes(t.title.toLowerCase()));

                return (
                  <ScheduleBlockCard
                    key={`${block.start_time}-${block.end_time}-${idx}`}
                    block={block}
                    task={mappedTask}
                    isPendingApproval={pendingApproval}
                  />
                );
              })}
            </AnimatePresence>
          </div>
        )}
      </ScrollArea>
    </div>
  );
};

export default ScheduleBoard;
