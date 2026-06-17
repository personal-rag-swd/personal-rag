import * as React from "react"
import { Navigate, Route, Routes } from "react-router-dom"
import { Loader2 } from "lucide-react"

import { useAuth } from "@/features/auth/store/auth-store"
import { LoginForm } from "@/features/auth/components/LoginForm"
import { RegisterForm } from "@/features/auth/components/RegisterForm"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { AppSidebar } from "@/features/dashboard/components/app-sidebar"
import { SiteHeader } from "@/features/dashboard/components/site-header"
import { DashboardClient } from "@/features/dashboard/components/dashboard-client"
import { NotebookPage } from "@/features/notebooks/components/NotebookPage"

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
  )
}

// Notebook full-page layout (no dashboard sidebar)
function NotebookLayout() {
  return (
    <main className="h-dvh overflow-hidden bg-background">
      <NotebookPage />
    </main>
  )
}

export function AppRoutes() {
  return (
    <Routes>
      {/* Public Pages */}
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
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
