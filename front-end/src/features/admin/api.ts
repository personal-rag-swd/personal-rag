import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"

import { apiFetch } from "@/lib/api-client"
import type {
  AdminDocument,
  AdminDocumentPage,
  AdminStats,
  AdminUser,
  AdminUserPage,
  AdminUserUsage,
  BillingSummary,
  DailyUsagePoint,
} from "./types"

type AdminStatsApiPayload = {
  total_users: number
  active_users: number
  total_notebooks: number
  documents_by_status: Record<string, number>
  reports_by_status: Record<string, number>
  tokens_this_month: number
  active_subscriptions: number
}

type AdminUserApiPayload = {
  id: string
  email: string
  role: string
  is_active: boolean
  created_at: string
  subscription_status: string | null
  product_id: string | null
  tokens_used_this_period: number
}

type AdminUserPageApiPayload = {
  items: AdminUserApiPayload[]
  total: number
  page: number
  page_size: number
}

type AdminUserUsageApiPayload = {
  period_start: string
  period_end: string
  llm_tokens_used: number
  llm_tokens_allowance: number
  is_subscription_active: boolean
  tier: string | null
  session_tokens_used: number
  session_tokens_allowance: number
  session_reset_at: string
  weekly_tokens_used: number
  weekly_tokens_allowance: number
  weekly_reset_at: string
}

type AdminDocumentApiPayload = {
  id: string
  filename: string
  content_type: string | null
  size: number | null
  status: string
  error_message: string | null
  notebook_id: string
  user_id: string
  created_at: string
  updated_at: string
}

type AdminDocumentPageApiPayload = {
  items: AdminDocumentApiPayload[]
  total: number
  page: number
  page_size: number
}

type BillingSummaryApiPayload = {
  by_status: Record<string, number>
  by_product: Record<string, number>
  total_customers: number
}

function mapAdminStats(payload: AdminStatsApiPayload): AdminStats {
  return {
    totalUsers: payload.total_users,
    activeUsers: payload.active_users,
    totalNotebooks: payload.total_notebooks,
    documentsByStatus: payload.documents_by_status,
    reportsByStatus: payload.reports_by_status,
    tokensThisMonth: payload.tokens_this_month,
    activeSubscriptions: payload.active_subscriptions,
  }
}

function mapAdminUser(payload: AdminUserApiPayload): AdminUser {
  return {
    id: payload.id,
    email: payload.email,
    role: payload.role,
    isActive: payload.is_active,
    createdAt: payload.created_at,
    subscriptionStatus: payload.subscription_status,
    productId: payload.product_id,
    tokensUsedThisPeriod: payload.tokens_used_this_period,
  }
}

function mapAdminUserUsage(payload: AdminUserUsageApiPayload): AdminUserUsage {
  return {
    periodStart: payload.period_start,
    periodEnd: payload.period_end,
    llmTokensUsed: payload.llm_tokens_used,
    llmTokensAllowance: payload.llm_tokens_allowance,
    isSubscriptionActive: payload.is_subscription_active,
    tier: payload.tier,
    sessionTokensUsed: payload.session_tokens_used,
    sessionTokensAllowance: payload.session_tokens_allowance,
    sessionResetAt: payload.session_reset_at,
    weeklyTokensUsed: payload.weekly_tokens_used,
    weeklyTokensAllowance: payload.weekly_tokens_allowance,
    weeklyResetAt: payload.weekly_reset_at,
  }
}

function mapAdminDocument(payload: AdminDocumentApiPayload): AdminDocument {
  return {
    id: payload.id,
    filename: payload.filename,
    contentType: payload.content_type,
    size: payload.size,
    status: payload.status,
    errorMessage: payload.error_message,
    notebookId: payload.notebook_id,
    userId: payload.user_id,
    createdAt: payload.created_at,
    updatedAt: payload.updated_at,
  }
}

export function useAdminStatsQuery() {
  return useQuery({
    queryKey: ["admin", "stats"],
    queryFn: async () =>
      mapAdminStats(await apiFetch<AdminStatsApiPayload>("/api/v1/admin/stats")),
  })
}

export function useAdminDailyUsageQuery(days: number) {
  return useQuery({
    queryKey: ["admin", "usage-daily", days],
    queryFn: () =>
      apiFetch<DailyUsagePoint[]>("/api/v1/admin/usage/daily", {
        params: { days },
      }),
  })
}

export function useAdminUsersQuery({
  page,
  pageSize,
  search,
}: {
  page: number
  pageSize: number
  search: string
}) {
  return useQuery({
    queryKey: ["admin", "users", { page, pageSize, search }],
    queryFn: async (): Promise<AdminUserPage> => {
      const payload = await apiFetch<AdminUserPageApiPayload>(
        "/api/v1/admin/users",
        {
          params: {
            page,
            page_size: pageSize,
            ...(search ? { search } : {}),
          },
        }
      )
      return {
        items: payload.items.map(mapAdminUser),
        total: payload.total,
        page: payload.page,
        pageSize: payload.page_size,
      }
    },
    placeholderData: keepPreviousData,
  })
}

export function useUpdateUserMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({
      userId,
      role,
      isActive,
    }: {
      userId: string
      role?: string
      isActive?: boolean
    }) =>
      mapAdminUser(
        await apiFetch<AdminUserApiPayload>(`/api/v1/admin/users/${userId}`, {
          method: "PATCH",
          data: {
            ...(role !== undefined ? { role } : {}),
            ...(isActive !== undefined ? { is_active: isActive } : {}),
          },
        })
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "users"] })
      void queryClient.invalidateQueries({ queryKey: ["admin", "stats"] })
    },
  })
}

export function useAdminUserUsageQuery(userId: string | null) {
  return useQuery({
    queryKey: ["admin", "user-usage", userId],
    queryFn: async () =>
      mapAdminUserUsage(
        await apiFetch<AdminUserUsageApiPayload>(
          `/api/v1/admin/users/${userId}/usage`
        )
      ),
    enabled: userId !== null,
  })
}

export function useAdminDocumentsQuery({
  status,
  page,
  pageSize,
}: {
  status: string
  page: number
  pageSize: number
}) {
  return useQuery({
    queryKey: ["admin", "documents", { status, page, pageSize }],
    queryFn: async (): Promise<AdminDocumentPage> => {
      const payload = await apiFetch<AdminDocumentPageApiPayload>(
        "/api/v1/admin/documents",
        {
          params: {
            page,
            page_size: pageSize,
            ...(status ? { status } : {}),
          },
        }
      )
      return {
        items: payload.items.map(mapAdminDocument),
        total: payload.total,
        page: payload.page,
        pageSize: payload.page_size,
      }
    },
    placeholderData: keepPreviousData,
  })
}

export function useAdminBillingSummaryQuery() {
  return useQuery({
    queryKey: ["admin", "billing-summary"],
    queryFn: async (): Promise<BillingSummary> => {
      const payload = await apiFetch<BillingSummaryApiPayload>(
        "/api/v1/admin/billing/summary"
      )
      return {
        byStatus: payload.by_status,
        byProduct: payload.by_product,
        totalCustomers: payload.total_customers,
      }
    },
  })
}
