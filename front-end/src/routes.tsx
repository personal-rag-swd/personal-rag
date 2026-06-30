import * as React from "react"
import { Navigate, Route, Routes } from "react-router-dom"
import { Loader2 } from "lucide-react"

import { useAuth } from "@/features/auth/store/auth-store"
import { ForgotPasswordForm } from "@/features/auth/components/ForgotPasswordForm"
import { LoginForm } from "@/features/auth/components/LoginForm"
import { RegisterForm } from "@/features/auth/components/RegisterForm"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { LandingPage } from "@/features/landing/LandingPage"

const AppSidebar = React.lazy(() =>
  import("@/features/dashboard/components/app-sidebar").then((module) => ({
    default: module.AppSidebar,
  }))
)
const SiteHeader = React.lazy(() =>
  import("@/features/dashboard/components/site-header").then((module) => ({
    default: module.SiteHeader,
  }))
)
const DashboardClient = React.lazy(() =>
  import("@/features/dashboard/components/dashboard-client").then((module) => ({
    default: module.DashboardClient,
  }))
)
const NotebookPage = React.lazy(() =>
  import("@/features/notebooks/components/NotebookPage").then((module) => ({
    default: module.NotebookPage,
  }))
)

// Premium, beautifully animated full-screen loader
function FullPageSpinner() {
  return (
    <div className="flex h-screen w-screen animate-in flex-col items-center justify-center gap-4 bg-background text-foreground duration-300 select-none fade-in">
      <div className="relative flex size-16 items-center justify-center">
        <div className="absolute size-16 animate-pulse rounded-full border-4 border-primary/20" />
        <Loader2 className="size-8 animate-spin text-primary" />
      </div>
      <p className="animate-pulse text-xs font-semibold tracking-wide text-muted-foreground">
        Initializing workspace...
      </p>
    </div>
  )
}

// Protected Route Guard
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return <FullPageSpinner />
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

// Public Route Guard (prevents logged in users from returning to Login/Register)
function PublicRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return <FullPageSpinner />
  }

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />
  }

  return <>{children}</>
}

// Auth Layout Centered Box
function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="flex min-h-dvh items-center justify-center px-4 py-10">
      <div className="w-full max-w-sm">{children}</div>
    </main>
  )
}

// Protected Dashboard Layout
function DashboardLayout() {
  return (
    <React.Suspense fallback={<FullPageSpinner />}>
      <SidebarProvider
        defaultOpen={true}
        style={
          {
            "--sidebar-width": "calc(var(--spacing) * 72)",
            "--header-height": "calc(var(--spacing) * 12)",
          } as React.CSSProperties
        }
      >
        <AppSidebar variant="inset" />
        <SidebarInset>
          <SiteHeader />
          <DashboardClient />
        </SidebarInset>
      </SidebarProvider>
    </React.Suspense>
  )
}

// Notebook full-page layout (no dashboard sidebar)
function NotebookLayout() {
  return (
    <React.Suspense fallback={<FullPageSpinner />}>
      <main className="h-dvh overflow-hidden bg-background">
        <NotebookPage />
      </main>
    </React.Suspense>
  )
}

export function AppRoutes() {
  return (
    <Routes>
      {/* Public Pages */}
      <Route path="/" element={<LandingPage />} />
      <Route
        path="/login"
        element={
          <PublicRoute>
            <AuthLayout>
              <LoginForm />
            </AuthLayout>
          </PublicRoute>
        }
      />
      <Route
        path="/register"
        element={
          <PublicRoute>
            <AuthLayout>
              <RegisterForm />
            </AuthLayout>
          </PublicRoute>
        }
      />
      <Route
        path="/forgot-password"
        element={
          <PublicRoute>
            <AuthLayout>
              <ForgotPasswordForm />
            </AuthLayout>
          </PublicRoute>
        }
      />

      {/* Protected Pages */}
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <DashboardLayout />
          </ProtectedRoute>
        }
      />
      <Route
        path="/notebook/:id"
        element={
          <ProtectedRoute>
            <NotebookLayout />
          </ProtectedRoute>
        }
      />

      {/* Fallbacks */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
