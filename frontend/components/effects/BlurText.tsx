"use client";

import React, { useRef, useEffect, useState } from "react";
import { motion, TargetAndTransition } from "framer-motion";

interface BlurTextProps {
  text?: string;
  delay?: number;
  className?: string;
  animateBy?: "words" | "letters";
  direction?: "top" | "bottom";
  threshold?: number;
  rootMargin?: string;
  animationFrom?: TargetAndTransition;
  animationTo?: TargetAndTransition[];
  easing?: string;
  onAnimationComplete?: () => void;
}

export const BlurText: React.FC<BlurTextProps> = ({
  text = "",
  delay = 50,
  className = "",
  animateBy = "words",
  direction = "top",
  threshold = 0.1,
  rootMargin = "0px",
  animationFrom,
  animationTo,
  easing = "easeOut",
  onAnimationComplete,
}) => {
  const elements = animateBy === "words" ? text.split(" ") : text.split("");
  const [inView, setInView] = useState(false);
  const ref = useRef<HTMLParagraphElement>(null);
  const animatedCount = useRef(0);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          if (ref.current) {
            observer.unobserve(ref.current);
          }
        }
      },
      { threshold, rootMargin }
    );

    if (ref.current) {
      observer.observe(ref.current);
    }

    return () => observer.disconnect();
  }, [threshold, rootMargin]);

  const defaultFrom: TargetAndTransition =
    direction === "top"
      ? { filter: "blur(10px)", opacity: 0, y: -15 }
      : { filter: "blur(10px)", opacity: 0, y: 15 };

  const defaultTo: TargetAndTransition[] = [
    {
      filter: "blur(4px)",
      opacity: 0.6,
      y: direction === "top" ? 4 : -4,
    },
    {
      filter: "blur(0px)",
      opacity: 1,
      y: 0,
    },
  ];

  const fromSnapshot = animationFrom || defaultFrom;
  const toSnapshots = animationTo || defaultTo;

  return (
    <p ref={ref} className={`inline-block ${className}`}>
      {elements.map((segment, index) => (
        <motion.span
          key={index}
          initial={fromSnapshot}
          animate={inView ? toSnapshots[toSnapshots.length - 1] : fromSnapshot}
          transition={{
            duration: 0.35,
            delay: (index * delay) / 1000,
            ease: "easeOut",
          }}
          onAnimationComplete={() => {
            animatedCount.current += 1;
            if (animatedCount.current === elements.length && onAnimationComplete) {
              onAnimationComplete();
            }
          }}
          className="inline-block whitespace-pre"
        >
          {segment}
          {animateBy === "words" && index < elements.length - 1 && " "}
        </motion.span>
      ))}
    </p>
  );
};

export default BlurText;
