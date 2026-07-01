import { useMutation, useQuery } from "@tanstack/react-query"

import { apiFetch } from "@/lib/api-client"

import type {
  BillingTier,
  SubscriptionStatus,
  SubscriptionStatusApiPayload,
  UsageSummary,
  UsageSummaryApiPayload,
} from "./types"

function mapUsageSummary(payload: UsageSummaryApiPayload): UsageSummary {
  return {
    periodStart: payload.period_start,
    periodEnd: payload.period_end,
    llmTokensUsed: payload.llm_tokens_used,
    llmTokensAllowance: payload.llm_tokens_allowance,
    isSubscriptionActive: payload.is_subscription_active,
    tier: payload.tier,
  }
}

function mapSubscriptionStatus(
  payload: SubscriptionStatusApiPayload
): SubscriptionStatus {
  return {
    subscriptionStatus: payload.subscription_status,
    currentPeriodStart: payload.current_period_start,
    currentPeriodEnd: payload.current_period_end,
    tier: payload.tier,
  }
}

export function useUsageSummaryQuery() {
  return useQuery<UsageSummary>({
    queryKey: ["billing", "usage"],
    queryFn: async () => {
      const data = await apiFetch<UsageSummaryApiPayload>("/api/v1/billing/usage")
      return mapUsageSummary(data)
    },
  })
}

export function useSubscriptionStatusQuery() {
  return useQuery<SubscriptionStatus>({
    queryKey: ["billing", "subscription"],
    queryFn: async () => {
      const data = await apiFetch<SubscriptionStatusApiPayload>(
        "/api/v1/billing/subscription"
      )
      return mapSubscriptionStatus(data)
    },
  })
}

export function useCreateCheckoutMutation() {
  return useMutation<string, Error, BillingTier>({
    mutationFn: async (tier: BillingTier) => {
      const data = await apiFetch<{ url: string }>("/api/v1/billing/checkout", {
        method: "POST",
        data: { tier },
      })
      return data.url
    },
  })
}

export function useCustomerPortalMutation() {
  return useMutation<string, Error, void>({
    mutationFn: async () => {
      const data = await apiFetch<{ url: string }>("/api/v1/billing/portal")
      return data.url
    },
  })
}
