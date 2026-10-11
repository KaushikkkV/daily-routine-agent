/**
 * Client-Side Calendar Export Suite & Cognitive Analytics Utility.
 * 
 * Provides:
 * 1. RFC 5545 compliant iCalendar (.ics) generation and browser download.
 * 2. One-click Google Calendar template link generation.
 * 3. Cognitive health and focus balance calculation with edge-case protection.
 */

import { TimeBlock, TaskItem } from "./api";

/**
 * Flexible Schedule Block contract to handle any client/backend attribute naming
 * variations (e.g. start_time vs startTime, label vs title vs task, is_buffer vs category).
 */
export type FlexibleTimeBlock = TimeBlock | {
  start_time?: string;
  startTime?: string;
  end_time?: string;
  endTime?: string;
  label?: string;
  title?: string;
  task?: string;
  task_id?: string | null;
  taskId?: string | null;
  is_buffer?: boolean;
  isBuffer?: boolean;
  category?: string;
  type?: string;
  [key: string]: any;
};

/**
 * Accessor: retrieves safe start time string (defaults to "09:00").
 */
export function getBlockStartTime(block?: FlexibleTimeBlock | null): string {
  if (!block) return "09:00";
  return block.start_time || (block as any).startTime || "09:00";
}

/**
 * Accessor: retrieves safe end time string (defaults to "10:00").
 */
export function getBlockEndTime(block?: FlexibleTimeBlock | null): string {
  if (!block) return "10:00";
  return block.end_time || (block as any).endTime || "10:00";
}

/**
 * Accessor: retrieves safe block label/title.
 */
export function getBlockLabel(block?: FlexibleTimeBlock | null): string {
  if (!block) return "Focus Block";
  return (
    block.label ||
    (block as any).title ||
    (block as any).task ||
    (isBlockBuffer(block) ? "Cognitive Slack" : "Focus Block")
  );
}

/**
 * Accessor: determines if a block represents a buffer/slack interval.
 */
export function isBlockBuffer(block?: FlexibleTimeBlock | null): boolean {
  if (!block) return false;
  if (typeof block.is_buffer === "boolean") return block.is_buffer;
  if (typeof (block as any).isBuffer === "boolean") return (block as any).isBuffer;
  if (typeof (block as any).category === "string" && (block as any).category.toLowerCase().includes("buffer")) return true;
  if (typeof (block as any).type === "string" && (block as any).type.toLowerCase().includes("buffer")) return true;
  return false;
}

/**
 * Escapes text for RFC 5545 iCalendar values.
 */
export function escapeICS(str?: string | null): string {
  if (!str) return "";
  return String(str)
    .replace(/\\/g, "\\\\")
    .replace(/;/g, "\\;")
    .replace(/,/g, "\\,")
    .replace(/\r?\n/g, "\\n");
}

/**
 * Parses time strings like "09:00", "09:00:00", "9:30 AM", or full ISO strings
 * into a Date object on the specified target date (defaults to today).
 * Guaranteed to never return NaN Date.
 */
export function parseTimeToDate(timeStr?: string | null, targetDate?: string | null): Date {
  const now = new Date();

  // 1. Resolve calendar date base safely
  let year = now.getFullYear();
  let month = now.getMonth();
  let day = now.getDate();

  if (targetDate && typeof targetDate === "string") {
    const cleanDate = targetDate.includes("T") ? targetDate.slice(0, 10) : targetDate;
    const dateParts = cleanDate.split("-");
    if (dateParts.length >= 3) {
      const py = parseInt(dateParts[0], 10);
      const pm = parseInt(dateParts[1], 10);
      const pd = parseInt(dateParts[2], 10);
      if (!isNaN(py) && py > 1900 && py < 2100) year = py;
      if (!isNaN(pm) && pm >= 1 && pm <= 12) month = pm - 1;
      if (!isNaN(pd) && pd >= 1 && pd <= 31) day = pd;
    }
  }

  // 2. Default fallback if timeStr is missing or invalid
  if (!timeStr || typeof timeStr !== "string" || !timeStr.trim()) {
    return new Date(year, month, day, 9, 0, 0);
  }

  const cleanTime = timeStr.trim();

  // Full ISO timestamp support
  if (cleanTime.includes("T") || cleanTime.includes("Z")) {
    const d = new Date(cleanTime);
    if (!isNaN(d.getTime())) return d;
  }

  const isPM = /pm/i.test(cleanTime);
  const isAM = /am/i.test(cleanTime);
  const stripped = cleanTime.replace(/(am|pm)/gi, "").trim();
  const parts = stripped.split(":");

  let hours = parseInt(parts[0] || "9", 10);
  let minutes = parseInt(parts[1] || "0", 10);
  let seconds = parseInt(parts[2] || "0", 10);

  if (isNaN(hours)) hours = 9;
  if (isNaN(minutes)) minutes = 0;
  if (isNaN(seconds)) seconds = 0;

  if (isPM && hours < 12) hours += 12;
  if (isAM && hours === 12) hours = 0;

  hours = Math.max(0, Math.min(23, hours));
  minutes = Math.max(0, Math.min(59, minutes));
  seconds = Math.max(0, Math.min(59, seconds));

  const result = new Date(year, month, day, hours, minutes, seconds);
  return isNaN(result.getTime()) ? now : result;
}

/**
 * Formats a Date object to local floating time string: YYYYMMDDTHHmmss
 * RFC 5545 compliant (zero NaN guarantee).
 */
export function formatToLocalString(date?: Date | null): string {
  const safeDate = !date || isNaN(date.getTime()) ? new Date() : date;
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    safeDate.getFullYear() +
    pad(safeDate.getMonth() + 1) +
    pad(safeDate.getDate()) +
    "T" +
    pad(safeDate.getHours()) +
    pad(safeDate.getMinutes()) +
    pad(safeDate.getSeconds())
  );
}

/**
 * Formats a Date object to UTC string: YYYYMMDDTHHmmssZ
 * RFC 5545 compliant (zero NaN guarantee).
 */
export function formatToUTCString(date?: Date | null): string {
  const safeDate = !date || isNaN(date.getTime()) ? new Date() : date;
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    safeDate.getUTCFullYear() +
    pad(safeDate.getUTCMonth() + 1) +
    pad(safeDate.getUTCDate()) +
    "T" +
    pad(safeDate.getUTCHours()) +
    pad(safeDate.getUTCMinutes()) +
    pad(safeDate.getUTCSeconds()) +
    "Z"
  );
}

/**
 * Calculates duration in minutes between start_time and end_time.
 */
export function getBlockDurationMinutes(
  block?: FlexibleTimeBlock | null,
  targetDate?: string | null
): number {
  if (!block) return 0;
  try {
    const startTimeStr = getBlockStartTime(block);
    const endTimeStr = getBlockEndTime(block);
    const start = parseTimeToDate(startTimeStr, targetDate);
    const end = parseTimeToDate(endTimeStr, targetDate);
    const diff = Math.round((end.getTime() - start.getTime()) / 60000);
    return diff > 0 ? diff : 0;
  } catch {
    return 0;
  }
}

/**
 * Generates an RFC 5545 compliant .ics string for all blocks.
 * Features:
 * - Proper VCALENDAR and VEVENT structure.
 * - UTC DTSTAMP per RFC 5545 §3.8.7.2.
 * - Chronological DTSTART/DTEND validation (guarantees DTEND > DTSTART).
 * - Transparent availability for buffer intervals, opaque for focus blocks.
 */
export function generateICS(
  blocks?: FlexibleTimeBlock[] | null,
  targetDate?: string | null
): string {
  if (!blocks || !Array.isArray(blocks) || blocks.length === 0) return "";

  // RFC 5545 requires DTSTAMP to be in UTC
  const dtstamp = formatToUTCString(new Date());

  const events = blocks.map((rawBlock, idx) => {
    const block = rawBlock || {};
    const startTimeStr = getBlockStartTime(block);
    const endTimeStr = getBlockEndTime(block);
    const isBuffer = isBlockBuffer(block);
    const label = getBlockLabel(block);

    const start = parseTimeToDate(startTimeStr, targetDate);
    let end = parseTimeToDate(endTimeStr, targetDate);

    // RFC 5545 Chronology Guarantee: DTEND must be after DTSTART
    if (end.getTime() <= start.getTime()) {
      end = new Date(start.getTime() + 15 * 60 * 1000);
    }

    const dtStart = formatToLocalString(start);
    const dtEnd = formatToLocalString(end);

    const uid = `${Date.now()}-${idx}-${Math.random().toString(36).substring(2, 9)}@concierge.agent`;

    const summary = escapeICS(
      isBuffer
        ? `[Recovery Buffer] ${label}`
        : label
    );

    const description = escapeICS(
      isBuffer
        ? "Cognitive Recovery & Restoration Buffer scheduled by Daily Routine Concierge to mitigate mental fatigue."
        : `Focus Time Block scheduled by Daily Routine Concierge.\nTime: ${startTimeStr} - ${endTimeStr}`
    );

    const categories = isBuffer
      ? "Buffer,Recovery,Health"
      : "Focus,Deep Work,Concierge Schedule";

    const lines = [
      "BEGIN:VEVENT",
      `UID:${uid}`,
      `DTSTAMP:${dtstamp}`,
      `DTSTART:${dtStart}`,
      `DTEND:${dtEnd}`,
      `SUMMARY:${summary}`,
      `DESCRIPTION:${description}`,
      `CATEGORIES:${categories}`,
      "STATUS:CONFIRMED",
      isBuffer ? "TRANSP:TRANSPARENT" : "TRANSP:OPAQUE",
      "END:VEVENT",
    ];

    return lines.join("\r\n");
  });

  const calendar = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Daily Routine Concierge//AI Scheduling Agent//EN",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    ...events,
    "END:VCALENDAR",
  ];

  return calendar.join("\r\n");
}

/**
 * Triggers a client-side Blob download of the .ics calendar file.
 * Handles temporary anchor creation and asynchronous object URL revocation.
 */
export function downloadICS(
  blocks?: FlexibleTimeBlock[] | null,
  targetDate?: string | null,
  filename = "concierge-schedule.ics"
): void {
  if (!blocks || !Array.isArray(blocks) || blocks.length === 0) return;
  if (typeof window === "undefined" || typeof document === "undefined") return;

  const icsData = generateICS(blocks, targetDate);
  if (!icsData) return;

  let url = "";
  try {
    const blob = new Blob([icsData], { type: "text/calendar;charset=utf-8" });
    url = URL.createObjectURL(blob);

    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", filename);
    link.style.display = "none";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  } catch (err) {
    console.error("Failed to trigger calendar download:", err);
  } finally {
    if (url) {
      setTimeout(() => {
        try {
          URL.revokeObjectURL(url);
        } catch {
          // ignore
        }
      }, 1000);
    }
  }
}

/**
 * Returns the primary focus block (first non-buffer task or first item).
 */
export function getPrimaryFocusBlock(
  blocks?: FlexibleTimeBlock[] | null
): FlexibleTimeBlock | undefined {
  if (!blocks || !Array.isArray(blocks) || blocks.length === 0) return undefined;
  // Prioritize first non-buffer block
  return blocks.find((b) => !isBlockBuffer(b)) || blocks[0];
}

/**
 * Generates a one-click Google Calendar TEMPLATE URL for an individual block.
 * Uses safe local time formatting and URLSearchParams encoding.
 */
export function getGoogleCalendarUrl(
  block?: FlexibleTimeBlock | null,
  targetDate?: string | null
): string {
  if (!block) return "https://calendar.google.com/calendar/render";

  const startTimeStr = getBlockStartTime(block);
  const endTimeStr = getBlockEndTime(block);
  const isBuffer = isBlockBuffer(block);
  const label = getBlockLabel(block);

  const start = parseTimeToDate(startTimeStr, targetDate);
  let end = parseTimeToDate(endTimeStr, targetDate);

  if (end.getTime() <= start.getTime()) {
    end = new Date(start.getTime() + 15 * 60 * 1000);
  }

  const startStr = formatToLocalString(start);
  const endStr = formatToLocalString(end);

  const title = isBuffer
    ? `[Recovery Buffer] ${label}`
    : label;

  const details = isBuffer
    ? "Cognitive Recovery & Restoration Buffer scheduled by Daily Routine Concierge."
    : `Deep Focus Block scheduled by Daily Routine Concierge (${startTimeStr} - ${endTimeStr}).`;

  const params = new URLSearchParams({
    action: "TEMPLATE",
    text: title,
    dates: `${startStr}/${endStr}`,
    details: details,
  });

  return `https://calendar.google.com/calendar/render?${params.toString()}`;
}

export interface CognitiveHealthMetrics {
  deepWorkMinutes: number;
  deepWorkHoursFormatted: string;
  bufferMinutes: number;
  bufferMinutesFormatted: string;
  totalWorkMinutes: number;
  healthScore: number;
  isOptimal: boolean;
  badgeLabel: string;
  badgeVariant: "optimal" | "risk";
  complianceReason: string;
}

/**
 * Computes deep work hours, recovery buffer compliance, and fatigue risk score.
 * Safely guards against missing blocks, malformed dates, and empty task records.
 */
export function calculateCognitiveHealth(
  blocks?: FlexibleTimeBlock[] | null,
  tasks?: TaskItem[] | null,
  targetDate?: string | null
): CognitiveHealthMetrics {
  if (!blocks || !Array.isArray(blocks) || blocks.length === 0) {
    return {
      deepWorkMinutes: 0,
      deepWorkHoursFormatted: "0h Deep Work",
      bufferMinutes: 0,
      bufferMinutesFormatted: "0m Recovery",
      totalWorkMinutes: 0,
      healthScore: 100,
      isOptimal: true,
      badgeLabel: "Optimal Recovery (100%)",
      badgeVariant: "optimal",
      complianceReason: "No active commitments loaded.",
    };
  }

  // 1. Calculate deep work minutes from tasks or blocks
  let deepWorkMins = 0;
  if (tasks && Array.isArray(tasks) && tasks.length > 0) {
    const deepTasks = tasks.filter((t) => t && t.category === "Deep Work");
    if (deepTasks.length > 0) {
      deepWorkMins = deepTasks.reduce((acc, t) => acc + (t.estimated_minutes || 0), 0);
    }
  }

  // Fallback to non-buffer blocks if task categories aren't present
  if (deepWorkMins === 0) {
    deepWorkMins = blocks
      .filter((b) => !isBlockBuffer(b))
      .reduce((sum, b) => sum + getBlockDurationMinutes(b, targetDate), 0);
  }

  // 2. Calculate buffer minutes
  const bufferMins = blocks
    .filter((b) => isBlockBuffer(b))
    .reduce((sum, b) => sum + getBlockDurationMinutes(b, targetDate), 0);

  // 3. Total work minutes - strictly occupational & cognitive commitments
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
      if (isBlockBuffer(b)) return false;
      const cat = (
        (b as any).category ||
        (b as any).type ||
        (tasks && tasks.find((t) => t.id === b.task_id || t.title.toLowerCase() === getBlockLabel(b).toLowerCase())?.category) ||
        ""
      )
        .toLowerCase()
        .replace(/[\s-]+/g, "_");

      const label = getBlockLabel(b).toLowerCase();
      // Exclude rest, sleep, recovery, health, fitness routines
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
    .reduce((sum, b) => sum + getBlockDurationMinutes(b, targetDate), 0);

  // 4. Verify Cognitive Buffer Compliance:
  // Occupational focus blocks > 45m must have adjacent buffers (either immediately before or after).
  let qualifyingBlocksCount = 0;
  let bufferedQualifyingCount = 0;
  let hasMissingBufferOnLongBlock = false;

  blocks.forEach((block, idx) => {
    if (!isBlockBuffer(block)) {
      const label = getBlockLabel(block).toLowerCase();
      const cat = ((block as any).category || "").toLowerCase();
      const isRestOrSleep =
        cat.includes("rest") ||
        cat.includes("sleep") ||
        /sleep|rest|nap|wind[\s-]?down|bedtime/i.test(label);

      // Only occupational / focus blocks trigger cognitive recovery buffer requirement
      if (!isRestOrSleep) {
        const duration = getBlockDurationMinutes(block, targetDate);
        if (duration > 45) {
          qualifyingBlocksCount++;
          const prevIsBuffer = idx > 0 && isBlockBuffer(blocks[idx - 1]);
          const nextIsBuffer = idx < blocks.length - 1 && isBlockBuffer(blocks[idx + 1]);

          if (prevIsBuffer || nextIsBuffer) {
            bufferedQualifyingCount++;
          } else {
            hasMissingBufferOnLongBlock = true;
          }
        }
      }
    }
  });

  const isOptimal =
    qualifyingBlocksCount === 0
      ? bufferMins > 0 || totalWorkMins <= 45
      : !hasMissingBufferOnLongBlock && bufferMins >= 15;

  const deepWorkHoursFormatted =
    deepWorkMins >= 60
      ? `${(deepWorkMins / 60).toFixed(1)}h Deep Work`
      : `${deepWorkMins}m Deep Work`;

  const bufferMinutesFormatted = `${bufferMins}m Recovery`;

  const healthScore = qualifyingBlocksCount > 0
    ? Math.round((bufferedQualifyingCount / qualifyingBlocksCount) * 100)
    : isOptimal ? 100 : 70;

  return {
    deepWorkMinutes: deepWorkMins,
    deepWorkHoursFormatted,
    bufferMinutes: bufferMins,
    bufferMinutesFormatted,
    totalWorkMinutes: totalWorkMins,
    healthScore,
    isOptimal,
    badgeLabel: isOptimal ? "Optimal Recovery (100%)" : "High Fatigue Risk",
    badgeVariant: isOptimal ? "optimal" : "risk",
    complianceReason: isOptimal
      ? "All deep work blocks >45m have adjacent cognitive recovery buffers."
      : "Focus blocks >45m require adjacent cognitive buffer to avoid mental exhaustion.",
  };
}
