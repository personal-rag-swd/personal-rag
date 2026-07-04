import { toast } from "sonner"
import { format } from "date-fns"
import {
  CalendarClockIcon,
  CheckIcon,
  CreditCardIcon,
  GaugeIcon,
  SparklesIcon,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Progress, ProgressTrack, ProgressIndicator } from "@/components/ui/progress"
import { cn, getErrorMessage } from "@/lib/utils"

import {
  useChangePlanMutation,
  useCreateCheckoutMutation,
  useCustomerPortalMutation,
  useSubscriptionStatusQuery,
  useUsageSummaryQuery,
} from "../api"
import type { BillingTier } from "../types"

const FREE_TIER_TOKENS = "6,000,000 tokens/mo"

const PLANS: {
  tier: BillingTier
  name: string
  price: string
  tokens: string
  perks: string[]
}[] = [
  {
    tier: "pro",
    name: "Pro",
    price: "$20/mo",
    tokens: "20,000,000 tokens/mo",
    perks: ["Priority ingestion", "Longer chat context", "Email support"],
  },
  {
    tier: "max",
    name: "Max",
    price: "$100/mo",
    tokens: "140,000,000 tokens/mo",
    perks: ["Priority ingestion", "Longest chat context", "Priority support"],
  },
]

function UsageBar({
  label,
  used,
  allowance,
}: {
  label: string
  used: number
  allowance: number
}) {
  const percent = allowance > 0 ? Math.min(100, (used / allowance) * 100) : 0
  const remaining = Math.max(0, allowance - used)
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium">{label}</span>
        <span className="text-muted-foreground tabular-nums">
          {used.toLocaleString()} / {allowance.toLocaleString()} (
          {percent.toFixed(1)}%)
        </span>
      </div>
      <Progress value={percent}>
        <ProgressTrack>
          <ProgressIndicator
            className={percent >= 100 ? "bg-destructive" : undefined}
          />
        </ProgressTrack>
      </Progress>
      <p className="text-xs text-muted-foreground">
        {remaining.toLocaleString()} tokens remaining this period
      </p>
    </div>
  )
}

export function BillingSettings() {
  const usageQuery = useUsageSummaryQuery()
  const subscriptionQuery = useSubscriptionStatusQuery()
  const checkoutMutation = useCreateCheckoutMutation()
  const changePlanMutation = useChangePlanMutation()
  const portalMutation = useCustomerPortalMutation()

  const isActive = usageQuery.data?.isSubscriptionActive ?? false
  const currentTier = subscriptionQuery.data?.tier ?? null
  const currentPlan = PLANS.find((plan) => plan.tier === currentTier) ?? null
  const freeTierTokens = usageQuery.data
    ? `${usageQuery.data.llmTokensAllowance.toLocaleString()} tokens/mo`
    : null

  const handleUpgrade = async (tier: BillingTier) => {
    try {
      if (isActive) {
        // Polar refuses to checkout a second product while a subscription
        // is active - switching tiers must go through the subscription
        // update flow instead of bouncing through checkout again.
        await changePlanMutation.mutateAsync(tier)
        toast.success(`Switched to the ${tier === "pro" ? "Pro" : "Max"} plan.`)
        return
      }
      const url = await checkoutMutation.mutateAsync(tier)
      window.location.assign(url)
    } catch (error) {
      toast.error(
        getErrorMessage(error, "Could not change your plan. Please try again.")
      )
    }
  }

  const handleManageBilling = async () => {
    try {
      const url = await portalMutation.mutateAsync()
      window.open(url, "_blank", "noopener,noreferrer")
    } catch (error) {
      toast.error(
        getErrorMessage(error, "Could not open the billing portal.")
      )
    }
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 p-6">
      <div className="flex flex-col gap-1">
        <h1 className="flex items-center gap-2 text-2xl font-semibold">
          <CreditCardIcon className="size-6" />
          Billing
        </h1>
        <p className="text-sm text-muted-foreground">
          Manage your subscription, track AI token usage, and compare plans.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <GaugeIcon className="size-5" />
              Current plan
            </CardTitle>
            <CardDescription>
              {currentPlan
                ? `${currentPlan.name} · ${currentPlan.price} · ${currentPlan.tokens}`
                : `Free tier${freeTierTokens ? ` · ${freeTierTokens}` : ""}`}
            </CardDescription>
            <CardAction>
              {isActive ? (
                <Badge variant="secondary">
                  {currentTier
                    ? `${currentTier} — ${subscriptionQuery.data?.subscriptionStatus ?? "active"}`
                    : (subscriptionQuery.data?.subscriptionStatus ?? "active")}
                </Badge>
              ) : (
                <Badge variant="outline">Free tier</Badge>
              )}
            </CardAction>
          </CardHeader>
          <CardContent className="flex flex-col gap-5">
            {usageQuery.data && (
              <>
                <UsageBar
                  label="LLM tokens (this month)"
                  used={usageQuery.data.llmTokensUsed}
                  allowance={usageQuery.data.llmTokensAllowance}
                />
                <UsageBar
                  label="LLM tokens (this week)"
                  used={usageQuery.data.weeklyTokensUsed}
                  allowance={usageQuery.data.weeklyTokensAllowance}
                />
                <UsageBar
                  label="LLM tokens (current 5h session)"
                  used={usageQuery.data.sessionTokensUsed}
                  allowance={usageQuery.data.sessionTokensAllowance}
                />
              </>
            )}

            <div className="flex flex-wrap gap-4 text-sm">
              {usageQuery.data && (
                <div className="flex items-center gap-1.5 text-muted-foreground">
                  <CalendarClockIcon className="size-4" />
                  Usage resets{" "}
                  {format(new Date(usageQuery.data.periodEnd), "MMM d, yyyy")}
                </div>
              )}
              {isActive && subscriptionQuery.data?.currentPeriodEnd && (
                <div className="flex items-center gap-1.5 text-muted-foreground">
                  <CreditCardIcon className="size-4" />
                  Next renewal{" "}
                  {format(
                    new Date(subscriptionQuery.data.currentPeriodEnd),
                    "MMM d, yyyy"
                  )}
                </div>
              )}
            </div>
          </CardContent>
          <CardFooter>
            <Button
              variant="outline"
              onClick={() => void handleManageBilling()}
              disabled={portalMutation.isPending}
            >
              Manage billing
            </Button>
          </CardFooter>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Free tier</CardTitle>
            <CardDescription>{FREE_TIER_TOKENS}</CardDescription>
            <CardAction>
              {currentTier === null && <Badge variant="outline">Current</Badge>}
            </CardAction>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-col gap-1.5 text-sm text-muted-foreground">
              <li className="flex items-center gap-1.5">
                <CheckIcon className="size-3.5" />
                Chat with your notebooks
              </li>
              <li className="flex items-center gap-1.5">
                <CheckIcon className="size-3.5" />
                Document ingestion & citations
              </li>
            </ul>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {PLANS.map((plan) => {
          const isCurrent = currentTier === plan.tier
          return (
            <Card
              key={plan.tier}
              className={cn(isCurrent && "ring-2 ring-primary")}
            >
              <CardHeader>
                <CardTitle>{plan.name}</CardTitle>
                <CardDescription>
                  {plan.price} · {plan.tokens}
                </CardDescription>
                <CardAction>
                  {isCurrent && <Badge variant="secondary">Current</Badge>}
                </CardAction>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <ul className="flex flex-col gap-1.5 text-sm text-muted-foreground">
                  {plan.perks.map((perk) => (
                    <li key={perk} className="flex items-center gap-1.5">
                      <CheckIcon className="size-3.5" />
                      {perk}
                    </li>
                  ))}
                </ul>
                <Button
                  className="w-full"
                  onClick={() => void handleUpgrade(plan.tier)}
                  disabled={
                    checkoutMutation.isPending ||
                    changePlanMutation.isPending ||
                    isCurrent
                  }
                >
                  <SparklesIcon className="size-4" />
                  {isCurrent ? "Current plan" : `Upgrade to ${plan.name}`}
                </Button>
              </CardContent>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
