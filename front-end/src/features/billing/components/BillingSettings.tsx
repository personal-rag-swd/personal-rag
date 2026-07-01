import { toast } from "sonner"
import { CreditCardIcon, SparklesIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Progress, ProgressTrack, ProgressIndicator } from "@/components/ui/progress"
import { getErrorMessage } from "@/lib/utils"

import {
  useCreateCheckoutMutation,
  useCustomerPortalMutation,
  useSubscriptionStatusQuery,
  useUsageSummaryQuery,
} from "../api"

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
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium">{label}</span>
        <span className="text-muted-foreground tabular-nums">
          {used.toLocaleString()} / {allowance.toLocaleString()}
        </span>
      </div>
      <Progress value={percent}>
        <ProgressTrack>
          <ProgressIndicator
            className={percent >= 100 ? "bg-destructive" : undefined}
          />
        </ProgressTrack>
      </Progress>
    </div>
  )
}

export function BillingSettings() {
  const usageQuery = useUsageSummaryQuery()
  const subscriptionQuery = useSubscriptionStatusQuery()
  const checkoutMutation = useCreateCheckoutMutation()
  const portalMutation = useCustomerPortalMutation()

  const isActive = usageQuery.data?.isSubscriptionActive ?? false

  const handleUpgrade = async () => {
    try {
      const url = await checkoutMutation.mutateAsync()
      window.location.href = url
    } catch (error) {
      toast.error(
        getErrorMessage(error, "Could not start checkout. Please try again.")
      )
    }
  }

  const handleManageBilling = async () => {
    try {
      const url = await portalMutation.mutateAsync()
      window.location.href = url
    } catch (error) {
      toast.error(
        getErrorMessage(error, "Could not open the billing portal.")
      )
    }
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 p-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CreditCardIcon className="size-5" />
            Billing
          </CardTitle>
          <CardDescription>
            Manage your subscription and monitor AI token usage against the
            free tier.
          </CardDescription>
          <CardAction>
            {isActive ? (
              <Badge variant="secondary">
                {subscriptionQuery.data?.subscriptionStatus ?? "active"}
              </Badge>
            ) : (
              <Badge variant="outline">Free tier</Badge>
            )}
          </CardAction>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          {usageQuery.data && (
            <UsageBar
              label="LLM tokens (this period)"
              used={usageQuery.data.llmTokensUsed}
              allowance={usageQuery.data.llmTokensAllowance}
            />
          )}

          <div className="flex flex-wrap gap-3">
            {!isActive && (
              <Button
                onClick={() => void handleUpgrade()}
                disabled={checkoutMutation.isPending}
              >
                <SparklesIcon className="size-4" />
                Upgrade for unlimited usage
              </Button>
            )}
            <Button
              variant="outline"
              onClick={() => void handleManageBilling()}
              disabled={portalMutation.isPending}
            >
              Manage billing
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
