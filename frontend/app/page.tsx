"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Ferrofluid } from "@/components/effects/Ferrofluid";
import { BlurText } from "@/components/effects/BlurText";
import { BorderGlow } from "@/components/effects/BorderGlow";
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from "@/components/ui/resizable";
import { ChatPane } from "@/components/chat/ChatPane";
import { ScheduleBoard } from "@/components/schedule/ScheduleBoard";
import { TutorialModal } from "@/components/landing/TutorialModal";
import { WorkspaceTour } from "@/components/tour/WorkspaceTour";
import { useConciergeSession } from "@/hooks/useConciergeSession";
import { ShieldCheck, Server, Sparkles, ArrowRight, Home } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getApiBase } from "@/lib/api";

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
    setTargetDate,
  } = useConciergeSession();

  const [activeView, setActiveView] = useState<"landing" | "workspace">("landing");
  const [focusTrigger, setFocusTrigger] = useState<number>(0);
  const [isTutorialOpen, setIsTutorialOpen] = useState<boolean>(false);
  const [isTourOpen, setIsTourOpen] = useState<boolean>(false);

  // Sync view state with URL hash (#workspace)
  useEffect(() => {
    if (typeof window !== "undefined" && window.location.hash === "#workspace") {
      setActiveView("workspace");
    }

    const handleHashChange = () => {
      if (window.location.hash === "#workspace") {
        setActiveView("workspace");
      } else {
        setActiveView("landing");
      }
    };

    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  const handleAdjustSchedule = () => {
    setFocusTrigger((prev) => prev + 1);
  };

  const handleLaunchWorkspace = () => {
    setActiveView("workspace");
    if (typeof window !== "undefined") {
      window.location.hash = "workspace";
    }
  };

  const handleReturnToLanding = () => {
    setActiveView("landing");
    if (typeof window !== "undefined") {
      window.history.pushState(null, "", window.location.pathname);
    }
  };

  // Launch in-situ spotlight tour 800ms after entering workspace on first visit
  useEffect(() => {
    if (typeof window === "undefined") return;
    const tourCompleted = localStorage.getItem("concierge_tour_completed");
    if (activeView === "workspace" && tourCompleted !== "true") {
      const timer = setTimeout(() => {
        setIsTourOpen(true);
      }, 800);
      return () => clearTimeout(timer);
    }
  }, [activeView]);

  const handleCloseTour = () => {
    setIsTourOpen(false);
    if (typeof window !== "undefined") {
      localStorage.setItem("concierge_tour_completed", "true");
    }
  };

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-zinc-950 font-sans text-zinc-100 selection:bg-indigo-500/30 selection:text-indigo-200">
      <AnimatePresence mode="wait">
        {activeView === "landing" ? (
          /* ==================== 1. LANDING PAGE VIEW ==================== */
          <motion.div
            key="landing"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, scale: 0.98 }}
            transition={{ duration: 0.25 }}
            className="relative h-screen w-full overflow-hidden bg-zinc-950 text-zinc-100 flex flex-col justify-between"
          >
            {/* Interactive Ferrofluid Background Canvas (z-0) */}
            <div className="absolute inset-0 z-0 h-full w-full pointer-events-auto">
              <Ferrofluid
                fluidColor="#09090b"
                glowColor="#6366f1"
                speed={1.0}
                viscosity={0.8}
                className="h-full w-full"
              />
            </div>

            {/* Landing Top Navbar (z-20) */}
            <header className="relative z-20 flex h-16 w-full shrink-0 items-center justify-between px-6 sm:px-10">
              <div className="flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-indigo-600 shadow-md shadow-indigo-600/40 text-white">
                  <ShieldCheck className="h-5 w-5" />
                </div>
                <div>
                  <span className="text-sm font-bold tracking-tight text-zinc-100">
                    Daily Routine Concierge
                  </span>
                  <span className="ml-2 hidden rounded-md bg-indigo-500/10 px-2 py-0.5 text-[10px] font-medium text-indigo-400 border border-indigo-500/20 sm:inline-block">
                    AI Scheduling Agent
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <Button
                  variant="default"
                  size="sm"
                  onClick={handleLaunchWorkspace}
                  className="bg-indigo-600 text-xs text-white shadow-md shadow-indigo-600/30 hover:bg-indigo-500 flex items-center gap-1.5 px-3.5"
                >
                  <span>Workspace</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </Button>
              </div>
            </header>

            {/* Landing Hero Central Card (z-20) */}
            <div className="relative z-20 flex flex-1 items-center justify-center p-6 sm:p-12 pointer-events-auto">
              <div className="relative mx-auto w-full max-w-4xl text-center">
                {/* Title: "Welcome to Concierge Agent" */}
                <div className="mb-4">
                  <BlurText
                    text="Welcome to Concierge Agent"
                    className="text-4xl sm:text-6xl md:text-7xl font-extrabold tracking-tight text-white drop-shadow-xl"
                    delay={40}
                    animateBy="words"
                  />
                </div>

                {/* Subtitle */}
                <p className="mx-auto max-w-2xl text-base sm:text-lg text-zinc-300 leading-relaxed drop-shadow">
                  Autonomous schedule orchestration with cognitive recovery buffers. Zero interrogation.
                </p>

                {/* Primary Action Suite - Focused Single CTA */}
                <div className="mt-10 flex items-center justify-center">
                  <BorderGlow
                    glowColor="#6366f1"
                    glowOpacity={0.7}
                    glowRadius={200}
                    borderRadius={12}
                    animated={true}
                    active={true}
                    className="w-full sm:w-auto"
                  >
                    <Button
                      size="lg"
                      onClick={handleLaunchWorkspace}
                      className="w-full sm:w-auto bg-indigo-600 hover:bg-indigo-500 text-white font-semibold shadow-xl shadow-indigo-600/30 px-8 py-3.5 text-base flex items-center justify-center gap-2.5 rounded-[inherit] transition-all hover:scale-[1.02] active:scale-[0.98]"
                    >
                      <span>Launch Workspace</span>
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                  </BorderGlow>
                </div>
              </div>
            </div>

            {/* Landing Bottom Status Bar (z-20) */}
            <footer className="relative z-20 flex h-12 w-full shrink-0 items-center justify-between px-6 sm:px-10 text-[11px] text-zinc-500 font-mono">
              <span>Autonomous Task Orchestration • ReAct Engine</span>
              <span className="hidden sm:inline">Cognitive Recovery Buffers • Zero Interrogation</span>
            </footer>
          </motion.div>
        ) : (
          /* ==================== 2. WORKSPACE VIEW ==================== */
          <motion.div
            key="workspace"
            initial={{ opacity: 0, scale: 1.01 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="relative flex h-screen w-full flex-col overflow-hidden bg-zinc-950"
          >
            {/* Workspace Top Navbar */}
            <header className="flex h-12 shrink-0 items-center justify-between border-b border-zinc-800/80 bg-zinc-900/60 px-5 backdrop-blur-md">
              <div
                className="flex items-center gap-3 cursor-pointer group"
                onClick={handleReturnToLanding}
                title="Return to Landing Page"
              >
                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-600 text-white shadow-sm shadow-indigo-600/30 group-hover:bg-indigo-500 transition-colors">
                  <ShieldCheck className="h-4 w-4" />
                </div>
                <div className="flex items-center gap-2">
                  <h1 className="text-sm font-bold tracking-tight text-zinc-100 group-hover:text-indigo-200 transition-colors">
                    Daily Routine &amp; Task Concierge
                  </h1>
                  <span className="hidden sm:inline-block rounded-md bg-indigo-500/10 px-2 py-0.5 text-[10px] font-medium text-indigo-400 border border-indigo-500/20">
                    ReAct + Guardrails Cockpit
                  </span>
                </div>
              </div>

              {/* Right Action Suite & Status Indicator */}
              <div className="flex items-center gap-3">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleReturnToLanding}
                  className="h-7 px-2.5 text-xs text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800/60 hidden sm:flex items-center gap-1.5"
                  title="Return to Landing Page"
                >
                  <Home className="h-3.5 w-3.5 text-indigo-400" />
                  <span>Landing</span>
                </Button>

                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setIsTourOpen(true)}
                  className="h-7 text-xs text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800/60 hidden sm:flex items-center gap-1.5"
                  title="Launch Spotlight Onboarding Tour"
                >
                  <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
                  <span>Tour</span>
                </Button>

                {/* Backend Status Indicator */}
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
                      ? `API Connected (${getApiBase().includes("8001") ? ":8001" : ":8000"})`
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
                    onDateChange={setTargetDate}
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
                    onDateChange={setTargetDate}
                    isApproving={isApproving}
                    isRollingBack={isRollingBack}
                  />
                </ResizablePanel>
              </ResizablePanelGroup>
            </main>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Interactive Onboarding Walkthrough Tutorial Dialog */}
      <TutorialModal
        open={isTutorialOpen}
        onOpenChange={setIsTutorialOpen}
        onComplete={handleLaunchWorkspace}
      />

      {/* Interactive In-Situ Spotlight Onboarding Tour */}
      <WorkspaceTour
        isOpen={isTourOpen}
        onClose={handleCloseTour}
        onComplete={handleCloseTour}
      />
    </div>
  );
}
