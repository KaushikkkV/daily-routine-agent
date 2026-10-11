/**
 * Client service layer and TypeScript contracts for FastAPI Daily Routine Concierge.
 */

export interface TimeBlock {
  start_time: string;
  end_time: string;
  label: string;
  task_id?: string | null;
  is_buffer: boolean;
}

export type TaskCategory = "Deep Work" | "Shallow Work" | "Errands" | "Health" | "Rest";
export type TaskPriority = "Low" | "Medium" | "High" | "Critical" | "None";
export type TaskStatus = "Pending" | "In Progress" | "Completed" | "Cancelled" | "Deferred";

export interface TaskItem {
  id: string;
  title: string;
  category: TaskCategory;
  estimated_minutes: number;
  priority: TaskPriority;
  status: TaskStatus;
}

export interface DailySchedule {
  date: string;
  time_blocks: TimeBlock[];
  tasks_allocated: TaskItem[];
  buffer_time_minutes: number;
}

export interface ScheduleVersion {
  version_id: number;
  timestamp: string;
  change_summary: string;
  schedule_snapshot: DailySchedule;
}

export interface ChatRequest {
  session_id: string;
  message: string;
}

export interface ChatResponse {
  reply: string;
  thought?: string | null;
  current_version_id: number;
  pending_approval: boolean;
  schedule?: DailySchedule | null;
  action_chips?: string[];
  requires_date_selection?: boolean;
  ui_action?: string | null;
  default_task?: string | null;
}

export interface ScheduleResponse {
  session_id: string;
  current_version_id: number;
  schedule?: DailySchedule | null;
  version_history: ScheduleVersion[];
}

export interface RollbackRequest {
  target_version_id: number;
}

export interface RollbackResponse {
  success: boolean;
  message: string;
  restored_version_id: number;
  current_version_id: number;
  schedule?: DailySchedule | null;
  version_history: ScheduleVersion[];
}

export interface ApproveResponse {
  success: boolean;
  message: string;
  session_id: string;
  current_version_id: number;
  pending_approval: boolean;
  schedule?: DailySchedule | null;
  version_history: ScheduleVersion[];
}

let activeApiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const CANDIDATE_URLS = process.env.NEXT_PUBLIC_API_URL
  ? [process.env.NEXT_PUBLIC_API_URL]
  : [
      "http://localhost:8000",
      "http://127.0.0.1:8000",
      "http://localhost:8001",
      "http://127.0.0.1:8001",
    ];

export function getApiBase(): string {
  return activeApiBase;
}

export async function checkBackendHealth(): Promise<boolean> {
  // 1. First probe current activeApiBase
  try {
    const res = await fetch(`${activeApiBase}/api/health`, {
      method: "GET",
      cache: "no-store",
    });
    if (res.ok) return true;
  } catch {}

  // 2. If not reachable, auto-discover alternative ports (e.g. 8000 or 8001)
  for (const candidate of CANDIDATE_URLS) {
    if (candidate === activeApiBase) continue;
    try {
      const res = await fetch(`${candidate}/api/health`, {
        method: "GET",
        cache: "no-store",
      });
      if (res.ok) {
        activeApiBase = candidate;
        return true;
      }
    } catch {}
  }

  return false;
}

export async function sendChatMessage(
  sessionId: string,
  message: string
): Promise<ChatResponse> {
  const base = getApiBase();
  const res = await fetch(`${base}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message }),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Chat request failed with status ${res.status}`);
  }

  return res.json();
}

export async function getSchedule(sessionId: string): Promise<ScheduleResponse> {
  const base = getApiBase();
  const res = await fetch(`${base}/api/schedule/${encodeURIComponent(sessionId)}`, {
    method: "GET",
    cache: "no-store",
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to fetch schedule with status ${res.status}`);
  }

  return res.json();
}

export async function rollbackSchedule(
  sessionId: string,
  targetVersionId: number
): Promise<RollbackResponse> {
  const base = getApiBase();
  const res = await fetch(
    `${base}/api/schedule/${encodeURIComponent(sessionId)}/rollback`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_version_id: targetVersionId }),
    }
  );

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Rollback failed with status ${res.status}`);
  }

  return res.json();
}

export async function approveSchedule(sessionId: string): Promise<ApproveResponse> {
  const base = getApiBase();
  const res = await fetch(
    `${base}/api/schedule/${encodeURIComponent(sessionId)}/approve`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    }
  );

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Approval failed with status ${res.status}`);
  }

  return res.json();
}
