import { AlertCircleIcon, ArrowLeftIcon, Loader2Icon } from "lucide-react"
import { Link } from "react-router-dom"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

export function NotebookSkeleton() {
  return (
    <div className="flex h-full flex-col bg-muted/30">
      <div className="flex min-h-16 items-center gap-3 border-b bg-background px-4">
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-4 w-px" />
        <Skeleton className="h-5 w-48" />
      </div>
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 p-3 lg:grid-cols-[minmax(220px,1fr)_minmax(360px,2fr)_minmax(220px,1fr)]">
        <Card className="hidden gap-3 p-4 lg:flex">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-24 w-full" />
        </Card>
        <Card className="min-h-0">
          <CardHeader>
            <CardTitle className="text-sm">Chat</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-1 items-center justify-center">
            <div className="flex items-center gap-2 text-muted-foreground">
              <Loader2Icon className="size-5 animate-spin" />
              <span className="text-sm">Loading notebook...</span>
            </div>
          </CardContent>
        </Card>
        <Card className="hidden gap-3 p-4 lg:flex">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </Card>
      </div>
    </div>
  )
}

export function NotebookError({ message }: { message: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center bg-muted/30 px-6 text-center">
      <Card className="w-full max-w-md">
        <CardContent className="flex flex-col items-center gap-4 pt-2">
          <div className="flex size-14 items-center justify-center rounded-3xl bg-destructive/10 text-destructive">
            <AlertCircleIcon className="size-7" />
          </div>
          <div className="flex flex-col gap-1.5">
            <h3 className="font-heading text-base font-medium text-foreground">
              Notebook not found
            </h3>
            <p className="max-w-xs text-sm text-muted-foreground">{message}</p>
          </div>
          <Button variant="outline" render={<Link to="/dashboard" />}>
            <ArrowLeftIcon data-icon="inline-start" />
            Back to Notebooks
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
