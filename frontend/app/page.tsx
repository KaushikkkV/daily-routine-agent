"use client";

import React, { useState } from "react";
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from "@/components/ui/resizable";
import { ChatPane } from "@/components/chat/ChatPane";
import { ScheduleBoard } from "@/components/schedule/ScheduleBoard";
import { useConciergeSession } from "@/hooks/useConciergeSession";
import { ShieldCheck, Server } from "lucide-react";

export default function DashboardPage() {
  const {
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
  } = useConciergeSession();

  const [focusTrigger, setFocusTrigger] = useState<number>(0);

  const handleAdjustSchedule = () => {
    setFocusTrigger((prev) => prev + 1);
  };

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-zinc-950 font-sans text-zinc-100">
      {/* Top Navbar */}
      <header className="flex h-12 shrink-0 items-center justify-between border-b border-zinc-800/80 bg-zinc-900/60 px-5 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-600 text-white shadow-sm shadow-indigo-600/30">
            <ShieldCheck className="h-4 w-4" />
          </div>
          <div className="flex items-center gap-2">
            <h1 className="text-sm font-bold tracking-tight text-zinc-100">
              Daily Routine &amp; Task Concierge
            </h1>
            <span className="hidden sm:inline-block rounded-md bg-indigo-500/10 px-2 py-0.5 text-[10px] font-medium text-indigo-400 border border-indigo-500/20">
              ReAct + Guardrails Cockpit
            </span>
          </div>
        </div>

        {/* Backend Status Indicator */}
        <div className="flex items-center gap-2">
          <div
            className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-mono border ${
              backendOnline === true
                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                : backendOnline === false
                ? "border-rose-500/30 bg-rose-500/10 text-rose-300"
                : "border-zinc-700 bg-zinc-800 text-zinc-400"
            }`}
          >
            <Server className="h-3 w-3" />
            <span>
              {backendOnline === true
                ? "API Connected (:8000)"
                : backendOnline === false
                ? "API Offline (python api.py)"
                : "Connecting..."}
            </span>
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                backendOnline === true
                  ? "bg-emerald-400 animate-pulse"
                  : backendOnline === false
                  ? "bg-rose-400"
                  : "bg-zinc-500"
              }`}
            />
          </div>
        </div>
      </header>

      {/* Dual-Panel Cockpit (Resizable Split Screen) */}
      <main className="flex-1 overflow-hidden">
        <ResizablePanelGroup direction="horizontal" className="h-full w-full">
          {/* Left Panel: Conversation Thread & Thought Drawer */}
          <ResizablePanel defaultSize={45} minSize={30} maxSize={65}>
            <ChatPane
              messages={messages}
              onSendMessage={sendMessage}
              isLoading={isLoading}
              sessionId={sessionId}
              onResetSession={resetSession}
              focusTrigger={focusTrigger}
            />
          </ResizablePanel>

          {/* Resizable Divider Handle */}
          <ResizableHandle withHandle />

          {/* Right Panel: Interactive Visual Schedule Board */}
          <ResizablePanel defaultSize={55} minSize={35} maxSize={70}>
            <ScheduleBoard
              schedule={schedule}
              currentVersionId={currentVersionId}
              versionHistory={versionHistory}
              pendingApproval={pendingApproval}
              onApprove={approve}
              onRollback={rollback}
              onAdjustSchedule={handleAdjustSchedule}
              isApproving={isApproving}
              isRollingBack={isRollingBack}
            />
          </ResizablePanel>
        </ResizablePanelGroup>
      </main>
    </div>
  );
}
