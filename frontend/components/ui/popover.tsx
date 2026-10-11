"use client";

import * as React from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

interface PopoverContextType {
  open: boolean;
  setOpen: (open: boolean) => void;
  triggerRef: React.RefObject<HTMLButtonElement | null>;
}

const PopoverContext = React.createContext<PopoverContextType | undefined>(undefined);

function usePopover() {
  const context = React.useContext(PopoverContext);
  if (!context) {
    throw new Error("Popover compound components must be used within <Popover />");
  }
  return context;
}

export interface PopoverProps {
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  children: React.ReactNode;
}

export const Popover: React.FC<PopoverProps> = ({
  open: controlledOpen,
  defaultOpen = false,
  onOpenChange,
  children,
}) => {
  const [uncontrolledOpen, setUncontrolledOpen] = React.useState(defaultOpen);
  const isControlled = controlledOpen !== undefined;
  const open = isControlled ? controlledOpen : uncontrolledOpen;
  const triggerRef = React.useRef<HTMLButtonElement | null>(null);

  const setOpen = React.useCallback(
    (nextOpen: boolean) => {
      if (!isControlled) {
        setUncontrolledOpen(nextOpen);
      }
      onOpenChange?.(nextOpen);
    },
    [isControlled, onOpenChange]
  );

  return (
    <PopoverContext.Provider value={{ open, setOpen, triggerRef }}>
      {children}
    </PopoverContext.Provider>
  );
};

export interface PopoverTriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  asChild?: boolean;
}

export const PopoverTrigger = React.forwardRef<HTMLButtonElement, PopoverTriggerProps>(
  ({ asChild, children, onClick, className, ...props }, ref) => {
    const { open, setOpen, triggerRef } = usePopover();

    const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
      onClick?.(e);
      setOpen(!open);
    };

    const combinedRef = (node: HTMLButtonElement | null) => {
      triggerRef.current = node;
      if (typeof ref === "function") ref(node);
      else if (ref) (ref as React.MutableRefObject<HTMLButtonElement | null>).current = node;
    };

    if (asChild && React.isValidElement(children)) {
      return React.cloneElement(children as React.ReactElement<any>, {
        ref: combinedRef,
        onClick: (e: React.MouseEvent<HTMLButtonElement>) => {
          (children.props as any)?.onClick?.(e);
          handleClick(e);
        },
        "aria-expanded": open,
      });
    }

    return (
      <button
        ref={combinedRef}
        type="button"
        onClick={handleClick}
        aria-expanded={open}
        className={className}
        {...props}
      >
        {children}
      </button>
    );
  }
);
PopoverTrigger.displayName = "PopoverTrigger";

export interface PopoverContentProps extends React.HTMLAttributes<HTMLDivElement> {
  align?: "start" | "center" | "end";
  sideOffset?: number;
}

export const PopoverContent = React.forwardRef<HTMLDivElement, PopoverContentProps>(
  ({ className, align = "start", sideOffset = 6, children, style, ...props }, ref) => {
    const { open, setOpen, triggerRef } = usePopover();
    const contentRef = React.useRef<HTMLDivElement | null>(null);
    const [mounted, setMounted] = React.useState(false);
    const [coords, setCoords] = React.useState<{ top: number; left: number } | null>(null);

    React.useEffect(() => {
      setMounted(true);
    }, []);

    // Calculate position based on trigger element bounding box
    React.useLayoutEffect(() => {
      if (!open || !triggerRef.current) return;

      const updatePosition = () => {
        if (!triggerRef.current) return;
        const rect = triggerRef.current.getBoundingClientRect();
        const top = rect.bottom + sideOffset;
        let left = rect.left;

        if (align === "center") {
          left = rect.left + rect.width / 2 - 130;
        } else if (align === "end") {
          left = rect.right - 260;
        }

        // Clamp to screen bounds
        if (typeof window !== "undefined") {
          left = Math.max(12, Math.min(left, window.innerWidth - 280));
        }

        setCoords({ top, left });
      };

      updatePosition();
      window.addEventListener("resize", updatePosition);
      window.addEventListener("scroll", updatePosition, true);

      return () => {
        window.removeEventListener("resize", updatePosition);
        window.removeEventListener("scroll", updatePosition, true);
      };
    }, [open, align, sideOffset, triggerRef]);

    // Handle outside click & escape key dismiss
    React.useEffect(() => {
      if (!open) return;

      const handlePointerDown = (e: MouseEvent | TouchEvent) => {
        const target = e.target as Node;
        if (
          contentRef.current &&
          !contentRef.current.contains(target) &&
          triggerRef.current &&
          !triggerRef.current.contains(target)
        ) {
          setOpen(false);
        }
      };

      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === "Escape") {
          setOpen(false);
        }
      };

      document.addEventListener("mousedown", handlePointerDown);
      document.addEventListener("touchstart", handlePointerDown);
      document.addEventListener("keydown", handleKeyDown);

      return () => {
        document.removeEventListener("mousedown", handlePointerDown);
        document.removeEventListener("touchstart", handlePointerDown);
        document.removeEventListener("keydown", handleKeyDown);
      };
    }, [open, setOpen, triggerRef]);

    if (!mounted) return null;

    return createPortal(
      <AnimatePresence>
        {open && coords && (
          <motion.div
            ref={(node) => {
              contentRef.current = node;
              if (typeof ref === "function") ref(node);
              else if (ref) (ref as React.MutableRefObject<HTMLDivElement | null>).current = node;
            }}
            initial={{ opacity: 0, scale: 0.95, y: -4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -4 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            style={{
              position: "fixed",
              top: coords.top,
              left: coords.left,
              ...style,
            }}
            className={cn(
              "z-50 min-w-[260px] rounded-xl border border-zinc-800 bg-zinc-900/95 p-3 text-zinc-100 shadow-2xl backdrop-blur-md outline-none",
              className
            )}
            {...props}
          >
            {children}
          </motion.div>
        )}
      </AnimatePresence>,
      document.body
    );
  }
);
PopoverContent.displayName = "PopoverContent";
