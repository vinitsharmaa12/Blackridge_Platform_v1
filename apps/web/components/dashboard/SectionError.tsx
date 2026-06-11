import { Button } from "@/components/ui/button";

type SectionErrorProps = {
  message: string;
  onRetry?: () => void;
};

export function SectionError({ message, onRetry }: SectionErrorProps) {
  return (
    <div className="flex flex-col items-center gap-2 py-8 text-center">
      <p className="text-sm text-destructive">{message}</p>
      {onRetry ? (
        <Button type="button" variant="outline" size="sm" onClick={onRetry}>
          Retry
        </Button>
      ) : null}
    </div>
  );
}
