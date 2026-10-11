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
  Download,
  Activity,
  ShieldCheck,
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
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { ScheduleBlockCard } from "./ScheduleBlockCard";
import { DailySchedule, ScheduleVersion, TaskItem } from "@/lib/api";
import {
  downloadICS,
  getGoogleCalendarUrl,
  getPrimaryFocusBlock,
  calculateCognitiveHealth,
} from "@/lib/calendarExport";
import { Calendar as CalendarComponent } from "@/components/ui/calendar";
import { Popover, PopoverTrigger, PopoverContent } from "@/components/ui/popover";
import { format } from "date-fns";

interface ScheduleBoardProps {
  schedule?: DailySchedule | null;
  currentVersionId: number;
  versionHistory: ScheduleVersion[];
  pendingApproval: boolean;
  onApprove: () => Promise<void>;
  onRollback: (versionId: number) => Promise<void>;
  onAdjustSchedule?: () => void;
  onDateChange?: (dateStr: string) => void;
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
  onDateChange,
  isApproving,
  isRollingBack,
}) => {
  const [selectedDate, setSelectedDate] = useState<Date | undefined>(undefined);
  const [isDatePickerOpen, setIsDatePickerOpen] = useState(false);

  // Sync selectedDate with schedule.date or client mount
  React.useEffect(() => {
    if (schedule?.date) {
      try {
        const [y, m, d] = schedule.date.split("-").map(Number);
        setSelectedDate(new Date(y, m - 1, d));
      } catch {
        setSelectedDate(new Date());
      }
    } else {
      setSelectedDate(new Date());
    }
  }, [schedule?.date]);

  const handleSelectDate = (date: Date | undefined) => {
    setSelectedDate(date);
    setIsDatePickerOpen(false);
    if (date) {
      const isoString = format(date, "yyyy-MM-dd");
      onDateChange?.(isoString);
    }
  };

  // Compute summary stats & cognitive metrics
  const blocks = schedule?.time_blocks || (schedule as any)?.blocks || [];
  const tasks = schedule?.tasks_allocated || [];
  const bufferMins = schedule?.buffer_time_minutes || 0;

  const cognitiveMetrics = calculateCognitiveHealth(blocks, tasks, schedule?.date);

  const deepWorkMins = tasks
    .filter((t) => t.category === "Deep Work")
    .reduce((acc, t) => acc + (t.estimated_minutes || 0), 0);

  const taskMap = new Map<string, TaskItem>();
  tasks.forEach((t) => {
    taskMap.set(t.id, t);
    taskMap.set(t.title.toLowerCase(), t);
  });

  const WORK_CATEGORIES = [
    "deep_work",
    "deep work",
    "shallow_work",
    "shallow work",
    "work",
    "errand",
    "errands",
    "meeting",
    "task",
  ];

  const totalWorkMins = blocks
    .filter((b) => {
      if (b.is_buffer) return false;
      const mappedTask =
        (b.task_id && taskMap.get(b.task_id)) ||
        taskMap.get(b.label.toLowerCase()) ||
        tasks.find((t) => b.label.toLowerCase().includes(t.title.toLowerCase()));

      const cat = ((b as any).category || mappedTask?.category || "")
        .toLowerCase()
        .replace(/[\s-]+/g, "_");

      const label = (b.label || "").toLowerCase();
      if (
        cat.includes("rest") ||
        cat.includes("sleep") ||
        cat.includes("health") ||
        cat.includes("fitness") ||
        /sleep|rest|nap|wind[\s-]?down|bedtime/i.test(label)
      ) {
        return false;
      }

      return WORK_CATEGORIES.some((wc) => cat.includes(wc) || cat === wc);
    })
    .reduce((acc, b) => {
      const mappedTask =
        (b.task_id && taskMap.get(b.task_id)) ||
        taskMap.get(b.label.toLowerCase());

      const duration =
        (b as any).duration_minutes ||
        (b as any).duration ||
        mappedTask?.estimated_minutes ||
        0;

      if (duration > 0) return acc + duration;

      try {
        const [sh, sm] = (b.start_time || "09:00").split(":").map(Number);
        const [eh, em] = (b.end_time || "10:00").split(":").map(Number);
        return acc + Math.max(0, eh * 60 + em - (sh * 60 + sm));
      } catch {
        return acc;
      }
    }, 0);

  return (
    <div id="schedule-board-container" className="flex h-full flex-col bg-zinc-950 text-zinc-100">
      {/* 1. Header with high stacking context */}
      <div id="schedule-board-header" className="relative z-30 flex h-14 shrink-0 items-center justify-between border-b border-zinc-800/80 px-5 bg-zinc-900/40 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600/20 text-indigo-400 ring-1 ring-indigo-500/30">
            <Calendar className="h-4 w-4" />
          </div>
          <div className="flex items-center gap-2.5">
            <h2 className="text-sm font-semibold tracking-tight text-zinc-100">
              Timeline Agenda
            </h2>
            <Popover open={isDatePickerOpen} onOpenChange={setIsDatePickerOpen}>
              <PopoverTrigger asChild>
                <Button
                  id="date-picker-button"
                  variant="outline"
                  size="sm"
                  className="h-7 gap-1.5 px-2.5 text-xs font-mono font-medium text-zinc-300 border-zinc-800 bg-zinc-900/80 hover:bg-zinc-800 hover:text-white transition-all shadow-sm"
                  title="Select schedule date"
                >
                  <Calendar className="h-3.5 w-3.5 text-indigo-400" />
                  <span>
                    {selectedDate
                      ? format(selectedDate, "yyyy-MM-dd")
                      : schedule?.date || "Pick Date"}
                  </span>
                  <ChevronDown className="h-3 w-3 text-zinc-500" />
                </Button>
              </PopoverTrigger>
              <PopoverContent align="start" className="w-auto p-1 z-50">
                <CalendarComponent
                  mode="single"
                  selected={selectedDate}
                  onSelect={handleSelectDate}
                />
              </PopoverContent>
            </Popover>
          </div>
        </div>

        {/* Version Badge, History Controls & Export Suite */}
        <div id="timeline-controls-header" className="flex items-center gap-2">
          {/* Version Badge */}
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

          {/* Calendar Export Suite Dropdown */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                disabled={!blocks || blocks.length === 0}
                className="h-8 gap-1.5 text-xs text-zinc-300 border-zinc-800 hover:bg-zinc-800 disabled:opacity-40 disabled:cursor-not-allowed"
                title={!blocks || blocks.length === 0 ? "Generate a schedule first to enable export" : "Export Schedule to Calendar"}
              >
                <Download className="h-3.5 w-3.5 text-indigo-400" />
                <span>Export</span>
                <ChevronDown className="h-3 w-3 text-zinc-500" />
              </Button>
            </DropdownMenuTrigger>

            <DropdownMenuContent
              align="end"
              sideOffset={4}
              className="w-64 p-1.5 z-[100] border-zinc-800 bg-zinc-900/95 shadow-2xl backdrop-blur-md"
            >
              <DropdownMenuLabel className="text-[11px] font-mono text-zinc-400 px-2 py-1 flex items-center justify-between">
                <span>Calendar Export Suite</span>
                <span className="text-[10px] text-zinc-500 font-normal">Client-Side</span>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />

              <DropdownMenuItem
                disabled={!blocks || blocks.length === 0}
                onClick={() => downloadICS(blocks, schedule?.date)}
                className="gap-2.5 px-2.5 py-2 text-xs text-zinc-200 hover:text-white cursor-pointer"
              >
                <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-indigo-600/20 text-indigo-400">
                  <Download className="h-3.5 w-3.5" />
                </div>
                <div className="flex flex-col text-left">
                  <span className="font-medium">Download iCal / Outlook (.ics)</span>
                  <span className="text-[10px] text-zinc-400">Full timeline with buffers</span>
                </div>
              </DropdownMenuItem>

              <DropdownMenuItem
                disabled={!blocks || blocks.length === 0}
                onClick={() => {
                  const primaryBlock = getPrimaryFocusBlock(blocks);
                  if (primaryBlock) {
                    const url = getGoogleCalendarUrl(primaryBlock, schedule?.date);
                    window.open(url, "_blank", "noopener,noreferrer");
                  }
                }}
                className="gap-2.5 px-2.5 py-2 text-xs text-zinc-200 hover:text-white cursor-pointer mt-0.5"
              >
                <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-emerald-600/20 text-emerald-400">
                  <Calendar className="h-3.5 w-3.5" />
                </div>
                <div className="flex flex-col text-left">
                  <span className="font-medium">Add to Google Calendar</span>
                  <span className="text-[10px] text-zinc-400">Primary focus block link</span>
                </div>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* 2. Cognitive Health & Balance Analytics Strip */}
      <div id="cognitive-balance-strip" className="shrink-0 border-b border-zinc-800/60 bg-zinc-900/30 px-4 sm:px-5 py-2.5 backdrop-blur-sm flex flex-wrap items-center justify-between gap-2.5">
        <div className="flex flex-wrap items-center gap-2 sm:gap-3">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-zinc-300">
            <Activity className="h-3.5 w-3.5 text-indigo-400 shrink-0" />
            <span className="hidden sm:inline">Cognitive Balance:</span>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {/* Deep Work Focus Hours */}
            <div className="inline-flex items-center gap-1.5 rounded-lg border border-indigo-500/20 bg-indigo-500/10 px-2.5 py-1 text-xs font-medium text-indigo-300 font-mono">
              <Zap className="h-3 w-3 text-indigo-400 shrink-0" />
              <span>{cognitiveMetrics.deepWorkHoursFormatted}</span>
            </div>

            {/* Cognitive Buffers */}
            <div className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-300 font-mono">
              <Coffee className="h-3 w-3 text-emerald-400 shrink-0" />
              <span>{cognitiveMetrics.bufferMinutesFormatted}</span>
            </div>
          </div>
        </div>

        {/* Health Score Badge */}
        <div className="flex items-center gap-2 shrink-0">
          {cognitiveMetrics.badgeVariant === "optimal" ? (
            <Badge
              variant="outline"
              className="bg-emerald-500/10 text-emerald-300 border-emerald-500/30 gap-1.5 px-2.5 py-0.5 text-xs font-medium cursor-help"
              title={cognitiveMetrics.complianceReason}
            >
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
              <span>{cognitiveMetrics.badgeLabel}</span>
            </Badge>
          ) : (
            <Badge
              variant="outline"
              className="bg-amber-500/10 text-amber-300 border-amber-500/30 gap-1.5 px-2.5 py-0.5 text-xs font-medium cursor-help"
              title={cognitiveMetrics.complianceReason}
            >
              <AlertTriangle className="h-3.5 w-3.5 text-amber-400 shrink-0" />
              <span>{cognitiveMetrics.badgeLabel}</span>
            </Badge>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      <ScrollArea id="schedule-main-area" className="flex-1 p-5">
        {/* Pending Approval Gate Alert Banner */}
        <AnimatePresence>
          {pendingApproval && (
            <motion.div
              id="schedule-confirmation-banner"
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
