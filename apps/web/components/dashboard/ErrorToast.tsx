"use client";

import { Button } from "@/components/ui/button";

type ErrorToastProps = {
  message: string;
  onRetry?: () => void;
  onDismiss: () => void;
};

/** Fixed toast for recoverable API errors (partial dashboard failures). */
export function ErrorToast({ message, onRetry, onDismiss }: ErrorToastProps) {
  return (
    <div
      className="fixed bottom-4 right-4 z-50 flex max-w-sm flex-col gap-2 rounded-lg border border-border bg-card p-3 shadow-md"
      role="alert"
    >
      <p className="text-sm text-destructive">{message}</p>
      <div className="flex gap-2">
        {onRetry ? (
          <Button type="button" variant="outline" size="sm" onClick={onRetry}>
            Retry
          </Button>
        ) : null}
        <Button type="button" variant="ghost" size="sm" onClick={onDismiss}>
          Dismiss
        </Button>
      </div>
    </div>
  );
}
