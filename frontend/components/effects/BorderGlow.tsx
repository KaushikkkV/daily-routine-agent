"use client";

import React, { useRef, useState, useEffect } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface BorderGlowProps {
  children: React.ReactNode;
  className?: string;
  glowColor?: string; // hex or rgb
  glowOpacity?: number;
  glowRadius?: number; // px
  borderRadius?: number; // px
  animated?: boolean;
  active?: boolean;
}

export const BorderGlow: React.FC<BorderGlowProps> = ({
  children,
  className = "",
  glowColor = "#6366f1", // Default indigo/violet
  glowOpacity = 0.5,
  glowRadius = 160,
  borderRadius = 16,
  animated = true,
  active = false,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({ x: -200, y: -200 });
  const [isHovered, setIsHovered] = useState(false);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    setPosition({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    });
  };

  return (
    <div
      ref={containerRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => {
        setIsHovered(false);
        setPosition({ x: -200, y: -200 });
      }}
      className={cn(
        "relative p-[1px] overflow-hidden transition-all duration-300",
        active && "ring-1 ring-amber-400/40 shadow-lg shadow-amber-500/10",
        className
      )}
      style={{
        borderRadius: `${borderRadius}px`,
      }}
    >
      {/* Background Glow Layer */}
      <div
        className="pointer-events-none absolute inset-0 transition-opacity duration-300"
        style={{
          opacity: isHovered || active ? glowOpacity : 0.15,
          background: `radial-gradient(${glowRadius}px circle at ${position.x}px ${position.y}px, ${glowColor}, transparent 70%)`,
        }}
      />

      {/* Optional Continuous Subtle Animated Aura if active */}
      {active && animated && (
        <motion.div
          className="pointer-events-none absolute inset-0 opacity-40"
          animate={{
            rotate: [0, 360],
          }}
          transition={{
            repeat: Infinity,
            duration: 8,
            ease: "linear",
          }}
          style={{
            background: `conic-gradient(from 0deg, transparent, ${glowColor}, transparent 60%)`,
          }}
        />
      )}

      {/* Inner Children Shell */}
      <div
        className="relative h-full w-full bg-zinc-950/95 backdrop-blur-md rounded-[inherit]"
        style={{
          borderRadius: `${Math.max(0, borderRadius - 1)}px`,
        }}
      >
        {children}
      </div>
    </div>
  );
};

export default BorderGlow;
