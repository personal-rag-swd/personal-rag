export interface AdminStats {
  totalUsers: number
  activeUsers: number
  totalNotebooks: number
  documentsByStatus: Record<string, number>
  reportsByStatus: Record<string, number>
  tokensThisMonth: number
  activeSubscriptions: number
}

export interface DailyUsagePoint {
  date: string
  tokens: number
}

export interface AdminUser {
  id: string
  email: string
  role: string
  isActive: boolean
  createdAt: string
  subscriptionStatus: string | null
  productId: string | null
  tokensUsedThisPeriod: number
}

export interface AdminUserPage {
  items: AdminUser[]
  total: number
  page: number
  pageSize: number
}

export interface AdminUserUsage {
  periodStart: string
  periodEnd: string
  llmTokensUsed: number
  llmTokensAllowance: number
  isSubscriptionActive: boolean
  tier: string | null
  sessionTokensUsed: number
  sessionTokensAllowance: number
  sessionResetAt: string
  weeklyTokensUsed: number
  weeklyTokensAllowance: number
  weeklyResetAt: string
}

export interface AdminDocument {
  id: string
  filename: string
  contentType: string | null
  size: number | null
  status: string
  errorMessage: string | null
  notebookId: string
  userId: string
  createdAt: string
  updatedAt: string
}

export interface AdminDocumentPage {
  items: AdminDocument[]
  total: number
  page: number
  pageSize: number
}

export interface BillingSummary {
  byStatus: Record<string, number>
  byProduct: Record<string, number>
  totalCustomers: number
}
