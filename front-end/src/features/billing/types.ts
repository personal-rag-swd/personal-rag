export type BillingTier = "plus" | "pro"

export interface UsageSummary {
  periodStart: string
  periodEnd: string
  llmTokensUsed: number
  llmTokensAllowance: number
  isSubscriptionActive: boolean
  tier: BillingTier | null
}

export interface UsageSummaryApiPayload {
  period_start: string
  period_end: string
  llm_tokens_used: number
  llm_tokens_allowance: number
  is_subscription_active: boolean
  tier: BillingTier | null
}

export interface SubscriptionStatus {
  subscriptionStatus: string | null
  currentPeriodStart: string | null
  currentPeriodEnd: string | null
  tier: BillingTier | null
}

export interface SubscriptionStatusApiPayload {
  subscription_status: string | null
  current_period_start: string | null
  current_period_end: string | null
  tier: BillingTier | null
}
