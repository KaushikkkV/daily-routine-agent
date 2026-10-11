"use client";

import React, { useRef } from "react";
import { motion, useScroll, useTransform } from "framer-motion";
import { Ferrofluid } from "@/components/effects/Ferrofluid";
import { BlurText } from "@/components/effects/BlurText";
import { BorderGlow } from "@/components/effects/BorderGlow";
import { Button } from "@/components/ui/button";
import { ArrowRight, Sparkles, ShieldCheck } from "lucide-react";

interface HeroSectionProps {
  onLaunchWorkspace: () => void;
  onOpenTutorial: () => void;
}

export const HeroSection: React.FC<HeroSectionProps> = ({
  onLaunchWorkspace,
  onOpenTutorial,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);

  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end start"],
  });

  const heroOpacity = useTransform(scrollYProgress, [0, 0.8], [1, 0]);
  const heroY = useTransform(scrollYProgress, [0, 0.8], [0, -60]);

  return (
    <div
      ref={containerRef}
      className="relative h-screen w-full overflow-hidden bg-zinc-950 text-zinc-100 flex flex-col justify-between"
    >
      {/* Layer 1: Ferrofluid Canvas (z-0) */}
      <div className="absolute inset-0 z-0 h-full w-full pointer-events-none">
        <Ferrofluid
          fluidColor="#09090b"
          glowColor="#6366f1"
          speed={1.0}
          viscosity={0.8}
          className="h-full w-full"
        />
      </div>

      {/* Top Navbar */}
      <header className="relative z-20 flex h-16 w-full items-center justify-between px-6 sm:px-10">
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
            onClick={onLaunchWorkspace}
            className="bg-indigo-600 text-xs text-white shadow-md shadow-indigo-600/30 hover:bg-indigo-500"
          >
            Workspace
            <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
          </Button>
        </div>
      </header>

      {/* Layer 2: Hero Text & Action Suite (z-20) */}
      <motion.div
        className="relative z-20 flex flex-1 items-center justify-center p-6 sm:p-12 pointer-events-auto"
        style={{
          opacity: heroOpacity,
          y: heroY,
        }}
      >
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

          {/* Action Suite - Focused Single CTA */}
          <div className="mt-10 flex items-center justify-center">
            {/* Launch Workspace (with BorderGlow) */}
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
                onClick={onLaunchWorkspace}
                className="w-full sm:w-auto bg-indigo-600 hover:bg-indigo-500 text-white font-semibold shadow-xl shadow-indigo-600/30 px-8 py-3.5 text-base flex items-center justify-center gap-2.5 rounded-[inherit] transition-all hover:scale-[1.02] active:scale-[0.98]"
              >
                <span>Launch Workspace</span>
                <ArrowRight className="h-4 w-4" />
              </Button>
            </BorderGlow>
          </div>
        </div>
      </motion.div>
    </div>
  );
};

export default HeroSection;
