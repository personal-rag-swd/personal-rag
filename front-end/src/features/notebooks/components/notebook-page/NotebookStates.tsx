import { AlertCircleIcon, ArrowLeftIcon, Loader2Icon } from "lucide-react";
import { Link } from "react-router-dom";

import { Skeleton } from "@/components/ui/skeleton";

export function NotebookSkeleton() {
  return (
    <div className="flex flex-col h-full">
      <div className="flex h-12 items-center gap-3 border-b border-border/50 px-4">
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-4 w-px" />
        <Skeleton className="h-5 w-48" />
      </div>
      <div className="flex flex-1 overflow-hidden">
        <div className="w-64 border-r border-border/50 p-4 flex flex-col gap-3">
          <Skeleton className="h-9 w-full rounded-xl" />
          <Skeleton className="h-9 w-full rounded-xl" />
          <Skeleton className="h-7 w-24 rounded-full" />
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Loader2Icon className="size-5 animate-spin" />
            <span className="text-sm">Loading notebook...</span>
          </div>
        </div>
        <div className="w-64 border-l border-border/50 p-4 flex flex-col gap-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full rounded-xl" />
          ))}
        </div>
      </div>
    </div>
  );
}

export function NotebookError({ message }: { message: string }) {
  return (
    <div className="flex flex-col h-full items-center justify-center gap-4 text-center px-6">
      <div className="flex size-14 items-center justify-center rounded-2xl bg-destructive/10 text-destructive">
        <AlertCircleIcon className="size-7" />
      </div>
      <div className="space-y-1.5">
        <h3 className="text-base font-bold text-foreground">Notebook not found</h3>
        <p className="text-sm text-muted-foreground max-w-xs">{message}</p>
      </div>
      <Link
        to="/dashboard"
        className="mt-2 inline-flex items-center gap-2 rounded-xl border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-muted transition-colors"
      >
        <ArrowLeftIcon className="size-4" />
        Back to Notebooks
      </Link>
    </div>
  );
}
