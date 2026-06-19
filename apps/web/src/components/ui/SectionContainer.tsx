import React from "react";
import { cn } from "@/lib/utils";

interface SectionContainerProps {
  children: React.ReactNode;
  className?: string;
  id?: string;
}

/**
 * Centered max-width section wrapper with consistent horizontal padding.
 */
export default function SectionContainer({
  children,
  className,
  id,
}: SectionContainerProps) {
  return (
    <section id={id} className={cn("w-full max-w-[1400px] mx-auto px-6 py-16 lg:py-24", className)}>
      {children}
    </section>
  );
}
