import * as React from "react"
import { formatDistanceToNow } from "date-fns"
import { AlertTriangleIcon } from "lucide-react"

import { cn } from "@/lib/utils"

import { useUsageSummaryQuery } from "../api"
import type { QuotaExceededDetail } from "../types"

function resetLabel(resetAt: string | null): string {
  if (!resetAt) return "later"
  const date = new Date(resetAt)
  if (date.getTime() <= Date.now()) return "shortly"
  return formatDistanceToNow(date, { addSuffix: true })
}

const WINDOW_LABEL: Record<QuotaExceededDetail["window"], string> = {
  session: "Session",
  weekly: "Weekly",
  monthly: "Monthly",
}

export function QuotaBanner({
  override,
  className,
}: {
  override: QuotaExceededDetail | null
  className?: string
}) {
  const usageQuery = useUsageSummaryQuery()

  const proactive = React.useMemo<QuotaExceededDetail | null>(() => {
    const usage = usageQuery.data
    if (!usage) return null
    if (usage.sessionTokensUsed >= usage.sessionTokensAllowance) {
      return {
        message: "Session token limit reached. Please try again later.",
        window: "session",
        reset_at: usage.sessionResetAt,
      }
    }
    if (usage.weeklyTokensUsed >= usage.weeklyTokensAllowance) {
      return {
        message: "Weekly token limit reached. Please try again later.",
        window: "weekly",
        reset_at: usage.weeklyResetAt,
      }
    }
    if (usage.llmTokensUsed >= usage.llmTokensAllowance) {
      return {
        message: "Monthly token limit reached. Upgrade your plan to continue.",
        window: "monthly",
        reset_at: usage.periodEnd,
      }
    }
    return null
  }, [usageQuery.data])

  const active = override ?? proactive
  if (!active) return null

  return (
    <div
      className={cn(
        "flex items-center gap-2 border-b border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive",
        className
      )}
    >
      <AlertTriangleIcon className="size-4 shrink-0" />
      <span className="font-medium">{WINDOW_LABEL[active.window]} limit reached.</span>
      <span className="text-destructive/80">
        Try again {resetLabel(active.reset_at)}.
      </span>
    </div>
  )
}
