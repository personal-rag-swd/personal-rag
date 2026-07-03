export type BillingTier = "pro" | "max"

export interface UsageSummary {
  periodStart: string
  periodEnd: string
  llmTokensUsed: number
  llmTokensAllowance: number
  isSubscriptionActive: boolean
  tier: BillingTier | null
  sessionTokensUsed: number
  sessionTokensAllowance: number
  sessionResetAt: string
  weeklyTokensUsed: number
  weeklyTokensAllowance: number
  weeklyResetAt: string
}

export interface UsageSummaryApiPayload {
  period_start: string
  period_end: string
  llm_tokens_used: number
  llm_tokens_allowance: number
  is_subscription_active: boolean
  tier: BillingTier | null
  session_tokens_used: number
  session_tokens_allowance: number
  session_reset_at: string
  weekly_tokens_used: number
  weekly_tokens_allowance: number
  weekly_reset_at: string
}

export interface QuotaExceededDetail {
  message: string
  window: "session" | "weekly" | "monthly"
  reset_at: string | null
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
