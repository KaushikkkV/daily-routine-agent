"use client";

import * as React from "react";
import { DayPicker } from "react-day-picker";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { buttonVariants } from "@/components/ui/button";

export type CalendarProps = React.ComponentProps<typeof DayPicker>;

function Calendar({
  className,
  classNames,
  showOutsideDays = true,
  ...props
}: CalendarProps) {
  return (
    <DayPicker
      showOutsideDays={showOutsideDays}
      className={cn("p-2 font-sans select-none", className)}
      classNames={{
        months: "flex flex-col sm:flex-row space-y-3 sm:space-x-4 sm:space-y-0",
        month: "space-y-3",
        caption: "relative flex justify-center items-center pt-1 px-8 w-full",
        month_caption: "relative flex justify-center items-center pt-1 px-8 w-full mb-1",
        caption_label: "text-xs font-semibold text-zinc-200 tracking-tight",
        nav: "flex items-center",
        nav_button: cn(
          buttonVariants({ variant: "outline" }),
          "h-7 w-7 bg-transparent p-0 opacity-70 hover:opacity-100 flex items-center justify-center rounded-md border border-border/50 text-foreground"
        ),
        nav_button_previous: "absolute left-2 top-1",
        nav_button_next: "absolute right-2 top-1",
        button_previous: cn(
          buttonVariants({ variant: "outline" }),
          "h-7 w-7 bg-transparent p-0 opacity-70 hover:opacity-100 flex items-center justify-center rounded-md border border-border/50 text-foreground absolute left-2 top-1"
        ),
        button_next: cn(
          buttonVariants({ variant: "outline" }),
          "h-7 w-7 bg-transparent p-0 opacity-70 hover:opacity-100 flex items-center justify-center rounded-md border border-border/50 text-foreground absolute right-2 top-1"
        ),
        month_grid: "w-full border-collapse space-y-1",
        weekdays: "flex w-full justify-between mb-1",
        weekday: "text-zinc-500 w-8 font-medium text-[0.75rem] text-center",
        weeks: "space-y-1",
        week: "flex w-full justify-between mt-1",
        day: "h-8 w-8 p-0 text-center text-xs relative [&:has([aria-selected])]:bg-transparent focus-within:relative focus-within:z-20",
        day_button: cn(
          buttonVariants({ variant: "ghost" }),
          "h-8 w-8 p-0 font-normal text-zinc-300 rounded-lg flex items-center justify-center transition-colors hover:bg-zinc-800 hover:text-zinc-100 aria-selected:opacity-100"
        ),
        selected:
          "!bg-indigo-600 !text-white hover:!bg-indigo-600 hover:!text-white focus:!bg-indigo-600 focus:!text-white font-semibold rounded-lg shadow-md shadow-indigo-600/30",
        today: "border border-indigo-500/50 text-indigo-400 font-bold",
        outside: "text-zinc-600 opacity-40 hover:opacity-70",
        disabled: "text-zinc-600 opacity-40 pointer-events-none",
        hidden: "invisible",
        ...classNames,
      }}
      components={{
        Chevron: ({ orientation, ...chevronProps }) =>
          orientation === "left" ? (
            <ChevronLeft className="h-4 w-4" {...chevronProps} />
          ) : (
            <ChevronRight className="h-4 w-4" {...chevronProps} />
          ),
      }}
      {...props}
    />
  );
}
Calendar.displayName = "Calendar";

export { Calendar };
