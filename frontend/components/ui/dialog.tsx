"use client";

import * as React from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

interface DialogContextType {
  open: boolean;
  setOpen: (open: boolean) => void;
}

const DialogContext = React.createContext<DialogContextType | undefined>(undefined);

function useDialog() {
  const context = React.useContext(DialogContext);
  if (!context) {
    throw new Error("Dialog compound components must be used within a <Dialog />");
  }
  return context;
}

export interface DialogProps {
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  children: React.ReactNode;
}

export const Dialog: React.FC<DialogProps> = ({
  open: controlledOpen,
  defaultOpen = false,
  onOpenChange,
  children,
}) => {
  const [uncontrolledOpen, setUncontrolledOpen] = React.useState(defaultOpen);
  const isControlled = controlledOpen !== undefined;
  const open = isControlled ? controlledOpen : uncontrolledOpen;

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
    <DialogContext.Provider value={{ open, setOpen }}>
      {children}
    </DialogContext.Provider>
  );
};

export interface DialogTriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  asChild?: boolean;
}

export const DialogTrigger = React.forwardRef<HTMLButtonElement, DialogTriggerProps>(
  ({ asChild, children, onClick, ...props }, ref) => {
    const { setOpen } = useDialog();

    const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
      onClick?.(e);
      if (!e.defaultPrevented) {
        setOpen(true);
      }
    };

    if (asChild && React.isValidElement(children)) {
      return React.cloneElement(children as React.ReactElement<{ onClick?: (e: React.MouseEvent) => void }>, {
        onClick: (e: React.MouseEvent) => {
          (children as React.ReactElement<{ onClick?: (e: React.MouseEvent) => void }>).props.onClick?.(e);
          if (!e.defaultPrevented) {
            setOpen(true);
          }
        },
      });
    }

    return (
      <button ref={ref} onClick={handleClick} type="button" {...props}>
        {children}
      </button>
    );
  }
);
DialogTrigger.displayName = "DialogTrigger";

export interface DialogContentProps extends React.HTMLAttributes<HTMLDivElement> {
  onClose?: () => void;
}

export const DialogContent = React.forwardRef<HTMLDivElement, DialogContentProps>(
  ({ className, children, onClose, ...props }, ref) => {
    const { open, setOpen } = useDialog();
    const [mounted, setMounted] = React.useState(false);

    React.useEffect(() => {
      setMounted(true);
      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === "Escape") {
          setOpen(false);
          onClose?.();
        }
      };
      if (open) {
        window.addEventListener("keydown", handleKeyDown);
        document.body.style.overflow = "hidden";
      }
      return () => {
        window.removeEventListener("keydown", handleKeyDown);
        document.body.style.overflow = "unset";
      };
    }, [open, setOpen, onClose]);

    if (!mounted) return null;

    return createPortal(
      <AnimatePresence>
        {open && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              onClick={() => {
                setOpen(false);
                onClose?.();
              }}
              className="fixed inset-0 bg-black/80 backdrop-blur-sm"
              aria-hidden="true"
            />

            {/* Modal Dialog Card */}
            <motion.div
              ref={ref}
              role="dialog"
              aria-modal="true"
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              transition={{ duration: 0.25, ease: "easeOut" }}
              className={cn(
                "relative z-10 w-full max-w-lg rounded-2xl border border-zinc-800 bg-zinc-950/95 p-6 text-zinc-100 shadow-2xl shadow-indigo-950/30 backdrop-blur-xl focus:outline-none",
                className
              )}
              {...props}
            >
              <button
                type="button"
                onClick={() => {
                  setOpen(false);
                  onClose?.();
                }}
                className="absolute right-4 top-4 rounded-lg p-1 text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                aria-label="Close"
              >
                <X className="h-4 w-4" />
              </button>
              {children}
            </motion.div>
          </div>
        )}
      </AnimatePresence>,
      document.body
    );
  }
);
DialogContent.displayName = "DialogContent";

export const DialogHeader: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className,
  ...props
}) => (
  <div
    className={cn("flex flex-col space-y-1.5 text-center sm:text-left", className)}
    {...props}
  />
);

export const DialogFooter: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className,
  ...props
}) => (
  <div
    className={cn(
      "flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2 mt-6",
      className
    )}
    {...props}
  />
);

export const DialogTitle: React.FC<React.HTMLAttributes<HTMLHeadingElement>> = ({
  className,
  ...props
}) => (
  <h2
    className={cn("text-lg font-semibold leading-none tracking-tight text-zinc-100", className)}
    {...props}
  />
);

export const DialogDescription: React.FC<React.HTMLAttributes<HTMLParagraphElement>> = ({
  className,
  ...props
}) => (
  <p
    className={cn("text-sm text-zinc-400 leading-relaxed", className)}
    {...props}
  />
);

export const DialogClose = React.forwardRef<HTMLButtonElement, React.ButtonHTMLAttributes<HTMLButtonElement>>(
  ({ onClick, children, ...props }, ref) => {
    const { setOpen } = useDialog();
    return (
      <button
        ref={ref}
        type="button"
        onClick={(e) => {
          onClick?.(e);
          setOpen(false);
        }}
        {...props}
      >
        {children}
      </button>
    );
  }
);
DialogClose.displayName = "DialogClose";
