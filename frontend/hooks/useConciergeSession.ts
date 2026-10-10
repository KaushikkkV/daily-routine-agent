"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  DailySchedule,
  ScheduleVersion,
  checkBackendHealth,
  sendChatMessage,
  getSchedule,
  approveSchedule,
  rollbackSchedule,
} from "@/lib/api";
import { ChatMessageItem } from "@/components/chat/ChatPane";
import { useToast } from "@/components/ui/toast";

export interface UseConciergeSessionReturn {
  sessionId: string;
  messages: ChatMessageItem[];
  schedule: DailySchedule | null;
  currentVersionId: number;
  versionHistory: ScheduleVersion[];
  pendingApproval: boolean;
  isLoading: boolean;
  isApproving: boolean;
  isRollingBack: boolean;
  backendOnline: boolean | null;
  sendMessage: (text: string) => Promise<void>;
  approve: () => Promise<void>;
  rollback: (versionId: number) => Promise<void>;
  resetSession: () => void;
  refreshSchedule: () => Promise<void>;
}

export function useConciergeSession(): UseConciergeSessionReturn {
  const [sessionId, setSessionId] = useState<string>("session_concierge_01");
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [schedule, setSchedule] = useState<DailySchedule | null>(null);
  const [currentVersionId, setCurrentVersionId] = useState<number>(0);
  const [versionHistory, setVersionHistory] = useState<ScheduleVersion[]>([]);
  const [pendingApproval, setPendingApproval] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isApproving, setIsApproving] = useState<boolean>(false);
  const [isRollingBack, setIsRollingBack] = useState<boolean>(false);
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);

  const toast = useToast();
  const isInitialized = useRef(false);

  // 1. Session initialization from localStorage
  useEffect(() => {
    if (typeof window === "undefined" || isInitialized.current) return;
    isInitialized.current = true;

    const savedSid = localStorage.getItem("concierge_session_id");
    if (savedSid) {
      setSessionId(savedSid);
    } else {
      const generated = `session_${Math.random().toString(36).substring(2, 9)}`;
      localStorage.setItem("concierge_session_id", generated);
      setSessionId(generated);
    }
  }, []);

  // 2. Fetch existing session state from backend
  const refreshSchedule = useCallback(async () => {
    if (!sessionId) return;
    try {
      const isHealthy = await checkBackendHealth();
      setBackendOnline(isHealthy);

      if (isHealthy) {
        const schedData = await getSchedule(sessionId);
        if (schedData) {
          if (schedData.schedule) setSchedule(schedData.schedule);
          setCurrentVersionId(schedData.current_version_id || 0);
          setVersionHistory(schedData.version_history || []);
        }
      }
    } catch {
      setBackendOnline(false);
    }
  }, [sessionId]);

  useEffect(() => {
    if (sessionId) {
      refreshSchedule();
    }
  }, [sessionId, refreshSchedule]);

  // 3. Populate initial welcoming concierge message
  useEffect(() => {
    if (messages.length === 0) {
      setMessages([
        {
          id: "welcome-1",
          role: "assistant",
          content:
            "Welcome! I am your Daily Routine & Task Concierge.\n\nType your tasks or brain dump below (e.g., 'Draft RFC 90m high priority, gym 45m, buy groceries 30m'). I will parse your commitments, pack non-overlapping chronological blocks with mandatory recovery buffers, and await your confirmation before saving.",
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          thought:
            "Concierge ReAct loop initialized. Energy-first chronobiology and recovery buffer safeguards active.",
          isNew: false,
        },
      ]);
    }
  }, [messages.length]);

  // 4. Send Message via ReAct execution turn
  const sendMessage = useCallback(
    async (userText: string) => {
      if (!userText.trim() || isLoading) return;

      const userMsg: ChatMessageItem = {
        id: `user-${Date.now()}`,
        role: "user",
        content: userText,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };

      setMessages((prev) => [...prev, userMsg]);
      setIsLoading(true);

      try {
        const res = await sendChatMessage(sessionId, userText);

        const assistantMsg: ChatMessageItem = {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: res.reply,
          thought: res.thought,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          isNew: true,
        };

        setMessages((prev) => [...prev, assistantMsg]);
        setCurrentVersionId(res.current_version_id);
        setPendingApproval(res.pending_approval);

        if (res.schedule) {
          setSchedule(res.schedule);
        }

        // Pull full audit trail snapshots
        try {
          const latestSchedule = await getSchedule(sessionId);
          if (latestSchedule?.version_history) {
            setVersionHistory(latestSchedule.version_history);
          }
        } catch {
          // Non-critical background sync
        }

        setBackendOnline(true);
      } catch (err: unknown) {
        const errorMsg =
          err instanceof Error
            ? err.message
            : "Error communicating with Concierge backend.";

        setMessages((prev) => [
          ...prev,
          {
            id: `error-${Date.now()}`,
            role: "assistant",
            content: `⚠️ Error: ${errorMsg}\n\nPlease verify that the FastAPI server is running with 'python api.py' on port 8000.`,
            timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          },
        ]);

        toast.error(
          "API Connection Error",
          "Ensure FastAPI backend is running on http://localhost:8000."
        );
        setBackendOnline(false);
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId, isLoading, toast]
  );

  // 5. Approve pending draft schedule
  const approve = useCallback(async () => {
    if (!sessionId || isApproving) return;
    setIsApproving(true);

    try {
      const res = await approveSchedule(sessionId);
      setPendingApproval(false);
      setCurrentVersionId(res.current_version_id);
      if (res.schedule) setSchedule(res.schedule);
      if (res.version_history) setVersionHistory(res.version_history);

      setMessages((prev) => [
        ...prev,
        {
          id: `approval-${Date.now()}`,
          role: "assistant",
          content: `✅ **Schedule Approved & Committed!**\nSnapshot persisted to storage as Version **v${res.current_version_id}**.`,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          thought: `Persistence gate satisfied: user clicked approve button; committed snapshot v${res.current_version_id}.`,
          isNew: true,
        },
      ]);

      toast.success(
        "Schedule Approved",
        `Snapshot committed to storage as Version v${res.current_version_id}.`
      );
    } catch (err: unknown) {
      const errorMsg =
        err instanceof Error ? err.message : "Failed to commit schedule.";
      toast.error("Approval Failed", errorMsg);
    } finally {
      setIsApproving(false);
    }
  }, [sessionId, isApproving, toast]);

  // 6. Rollback schedule to target snapshot
  const rollback = useCallback(
    async (targetVersionId: number) => {
      if (!sessionId || isRollingBack) return;
      setIsRollingBack(true);

      try {
        const res = await rollbackSchedule(sessionId, targetVersionId);
        setCurrentVersionId(res.restored_version_id);
        if (res.schedule) setSchedule(res.schedule);
        if (res.version_history) setVersionHistory(res.version_history);
        setPendingApproval(false);

        setMessages((prev) => [
          ...prev,
          {
            id: `rollback-${Date.now()}`,
            role: "assistant",
            content: `⏪ **Schedule Reverted!** Successfully restored active schedule to snapshot **v${targetVersionId}**.`,
            timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
            thought: `Revert tool executed: active_schedule restored from version ${targetVersionId} snapshot.`,
            isNew: true,
          },
        ]);

        toast.info(
          "Schedule Restored",
          `Successfully rolled back active schedule to snapshot v${targetVersionId}.`
        );
      } catch (err: unknown) {
        const errorMsg =
          err instanceof Error ? err.message : "Failed to restore version.";
        toast.error("Rollback Failed", errorMsg);
      } finally {
        setIsRollingBack(false);
      }
    },
    [sessionId, isRollingBack, toast]
  );

  // 7. Reset session to fresh state
  const resetSession = useCallback(() => {
    const newSid = `session_${Math.random().toString(36).substring(2, 9)}`;
    if (typeof window !== "undefined") {
      localStorage.setItem("concierge_session_id", newSid);
    }
    setSessionId(newSid);
    setMessages([]);
    setSchedule(null);
    setCurrentVersionId(0);
    setVersionHistory([]);
    setPendingApproval(false);
    toast.info("New Session Started", `Session initialized: ${newSid}`);
  }, [toast]);

  return {
    sessionId,
    messages,
    schedule,
    currentVersionId,
    versionHistory,
    pendingApproval,
    isLoading,
    isApproving,
    isRollingBack,
    backendOnline,
    sendMessage,
    approve,
    rollback,
    resetSession,
    refreshSchedule,
  };
}
