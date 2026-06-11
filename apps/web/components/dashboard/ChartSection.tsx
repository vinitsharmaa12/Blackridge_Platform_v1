import type { ReactNode } from "react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

type ChartSectionProps = {
  title: string;
  description?: string;
  meta?: string;
  children: ReactNode;
  className?: string;
  compact?: boolean;
};

export function ChartSection({
  title,
  description,
  meta,
  children,
  className,
  compact = false,
}: ChartSectionProps) {
  return (
    <Card
      size={compact ? "sm" : "default"}
      className={cn("flex h-full flex-col shadow-none", className)}
    >
      <CardHeader className={cn("shrink-0", compact ? "pb-1" : "pb-2")}>
        <CardTitle className={compact ? "text-xs" : "text-sm"}>
          {title}
        </CardTitle>
        {!compact && description ? (
          <CardDescription>{description}</CardDescription>
        ) : null}
        {meta ? (
          <p className="text-xs font-mono text-muted-foreground">{meta}</p>
        ) : null}
      </CardHeader>
      <CardContent className="min-h-0 flex-1 overflow-hidden pt-0">
        {children}
      </CardContent>
    </Card>
  );
}
