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
  AdminDocumentPreview,
  AdminOrder,
  AdminOrderPage,
  AdminStats,
  AdminTransaction,
  AdminTransactionPage,
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

type AdminDocumentPreviewApiPayload = {
  filename: string
  content_type: string | null
  size: number | null
  url: string | null
  content: string | null
  preview_type: "text" | "url"
}

type AdminTransactionApiPayload = {
  id: string
  user_id: string
  notebook_id: string | null
  quantity: number
  polar_ingested: boolean
  polar_ingested_at: string | null
  polar_ingest_error: string | null
  retry_count: number
  created_at: string
}

type AdminTransactionPageApiPayload = {
  items: AdminTransactionApiPayload[]
  total: number
  page: number
  page_size: number
}

type AdminOrderApiPayload = {
  id: string
  amount: number | null
  currency: string | null
  status: string | null
  customer_email: string | null
  product_id: string | null
  created_at: string | null
}

type AdminOrderPageApiPayload = {
  items: AdminOrderApiPayload[]
  total: number
  configured: boolean
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

function mapAdminDocumentPreview(
  payload: AdminDocumentPreviewApiPayload
): AdminDocumentPreview {
  return {
    filename: payload.filename,
    contentType: payload.content_type,
    size: payload.size,
    url: payload.url,
    content: payload.content,
    previewType: payload.preview_type,
  }
}

function mapAdminTransaction(
  payload: AdminTransactionApiPayload
): AdminTransaction {
  return {
    id: payload.id,
    userId: payload.user_id,
    notebookId: payload.notebook_id,
    quantity: payload.quantity,
    polarIngested: payload.polar_ingested,
    polarIngestedAt: payload.polar_ingested_at,
    polarIngestError: payload.polar_ingest_error,
    retryCount: payload.retry_count,
    createdAt: payload.created_at,
  }
}

function mapAdminOrder(payload: AdminOrderApiPayload): AdminOrder {
  return {
    id: payload.id,
    amount: payload.amount,
    currency: payload.currency,
    status: payload.status,
    customerEmail: payload.customer_email,
    productId: payload.product_id,
    createdAt: payload.created_at,
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
  search,
  page,
  pageSize,
}: {
  status: string
  search: string
  page: number
  pageSize: number
}) {
  return useQuery({
    queryKey: ["admin", "documents", { status, search, page, pageSize }],
    queryFn: async (): Promise<AdminDocumentPage> => {
      const payload = await apiFetch<AdminDocumentPageApiPayload>(
        "/api/v1/admin/documents",
        {
          params: {
            page,
            page_size: pageSize,
            ...(status ? { status } : {}),
            ...(search ? { search } : {}),
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

export function useAdminDocumentPreviewQuery(documentId: string | null) {
  return useQuery({
    queryKey: ["admin", "document-preview", documentId],
    queryFn: async () =>
      mapAdminDocumentPreview(
        await apiFetch<AdminDocumentPreviewApiPayload>(
          `/api/v1/admin/documents/${documentId}/preview`
        )
      ),
    enabled: documentId !== null,
  })
}

export function useUpdateDocumentMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({
      documentId,
      filename,
      status,
    }: {
      documentId: string
      filename?: string
      status?: string
    }) =>
      mapAdminDocument(
        await apiFetch<AdminDocumentApiPayload>(
          `/api/v1/admin/documents/${documentId}`,
          {
            method: "PATCH",
            data: {
              ...(filename !== undefined ? { filename } : {}),
              ...(status !== undefined ? { status } : {}),
            },
          }
        )
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "documents"] })
      void queryClient.invalidateQueries({ queryKey: ["admin", "stats"] })
    },
  })
}

export function useDeleteDocumentMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (documentId: string) =>
      apiFetch<void>(`/api/v1/admin/documents/${documentId}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "documents"] })
      void queryClient.invalidateQueries({ queryKey: ["admin", "stats"] })
    },
  })
}

export function useAdminTransactionsQuery({
  page,
  pageSize,
}: {
  page: number
  pageSize: number
}) {
  return useQuery({
    queryKey: ["admin", "transactions", { page, pageSize }],
    queryFn: async (): Promise<AdminTransactionPage> => {
      const payload = await apiFetch<AdminTransactionPageApiPayload>(
        "/api/v1/admin/transactions",
        { params: { page, page_size: pageSize } }
      )
      return {
        items: payload.items.map(mapAdminTransaction),
        total: payload.total,
        page: payload.page,
        pageSize: payload.page_size,
      }
    },
    placeholderData: keepPreviousData,
  })
}

export function useAdminOrdersQuery({
  page,
  pageSize,
}: {
  page: number
  pageSize: number
}) {
  return useQuery({
    queryKey: ["admin", "orders", { page, pageSize }],
    queryFn: async (): Promise<AdminOrderPage> => {
      const payload = await apiFetch<AdminOrderPageApiPayload>(
        "/api/v1/admin/orders",
        { params: { page, page_size: pageSize } }
      )
      return {
        items: payload.items.map(mapAdminOrder),
        total: payload.total,
        configured: payload.configured,
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
