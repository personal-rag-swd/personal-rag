import * as React from "react"
import { toast } from "sonner"
import { EllipsisVerticalIcon } from "lucide-react"
import type { ColumnDef } from "@tanstack/react-table"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { DataTable } from "@/components/ui/data-table"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { useAuth } from "@/features/auth/store/auth-store"
import {
  useAdminUserUsageQuery,
  useAdminUsersQuery,
  useUpdateUserMutation,
} from "../api"
import type { AdminUser } from "../types"

const PAGE_SIZE = 20

type PendingAction = {
  user: AdminUser
  kind: "promote" | "demote" | "activate" | "deactivate"
}

const actionLabels: Record<PendingAction["kind"], string> = {
  promote: "Promote to admin",
  demote: "Demote to user",
  activate: "Activate",
  deactivate: "Deactivate",
}

function UsageDialog({
  user,
  onClose,
}: {
  user: AdminUser
  onClose: () => void
}) {
  const { data: usage, isLoading } = useAdminUserUsageQuery(user.id)

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Usage for {user.email}</DialogTitle>
          <DialogDescription>
            Current billing-period token consumption.
          </DialogDescription>
        </DialogHeader>
        {isLoading || !usage ? (
          <Skeleton className="h-32 w-full" />
        ) : (
          <div className="grid gap-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Tier</span>
              <span>{usage.tier ?? "free"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Monthly tokens</span>
              <span>
                {usage.llmTokensUsed.toLocaleString()} /{" "}
                {usage.llmTokensAllowance.toLocaleString()}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Session tokens</span>
              <span>
                {usage.sessionTokensUsed.toLocaleString()} /{" "}
                {usage.sessionTokensAllowance.toLocaleString()}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Weekly tokens</span>
              <span>
                {usage.weeklyTokensUsed.toLocaleString()} /{" "}
                {usage.weeklyTokensAllowance.toLocaleString()}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Period ends</span>
              <span>{new Date(usage.periodEnd).toLocaleDateString()}</span>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

export function AdminUsersTable() {
  const { user: currentUser } = useAuth()
  const [pageIndex, setPageIndex] = React.useState(0)
  const [searchInput, setSearchInput] = React.useState("")
  const [search, setSearch] = React.useState("")
  const [pendingAction, setPendingAction] =
    React.useState<PendingAction | null>(null)
  const [usageUser, setUsageUser] = React.useState<AdminUser | null>(null)

  React.useEffect(() => {
    const timeout = setTimeout(() => {
      setSearch(searchInput)
      setPageIndex(0)
    }, 300)
    return () => clearTimeout(timeout)
  }, [searchInput])

  const { data, isLoading } = useAdminUsersQuery({
    page: pageIndex + 1,
    pageSize: PAGE_SIZE,
    search,
  })
  const updateUser = useUpdateUserMutation()

  const confirmAction = () => {
    if (!pendingAction) return
    const { user, kind } = pendingAction
    updateUser.mutate(
      {
        userId: user.id,
        ...(kind === "promote" ? { role: "admin" } : {}),
        ...(kind === "demote" ? { role: "user" } : {}),
        ...(kind === "activate" ? { isActive: true } : {}),
        ...(kind === "deactivate" ? { isActive: false } : {}),
      },
      {
        onSuccess: () => {
          toast.success(`${actionLabels[kind]} succeeded for ${user.email}`)
        },
        onError: (error) => {
          toast.error(error.message)
        },
      }
    )
    setPendingAction(null)
  }

  const columns: ColumnDef<AdminUser>[] = [
    {
      accessorKey: "email",
      header: "Email",
    },
    {
      accessorKey: "role",
      header: "Role",
      cell: ({ row }) => (
        <Badge variant={row.original.role === "admin" ? "default" : "secondary"}>
          {row.original.role}
        </Badge>
      ),
    },
    {
      accessorKey: "isActive",
      header: "Status",
      cell: ({ row }) => (
        <Badge variant={row.original.isActive ? "secondary" : "destructive"}>
          {row.original.isActive ? "active" : "inactive"}
        </Badge>
      ),
    },
    {
      accessorKey: "subscriptionStatus",
      header: "Subscription",
      cell: ({ row }) =>
        row.original.subscriptionStatus ? (
          <Badge variant="outline">{row.original.subscriptionStatus}</Badge>
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
    {
      accessorKey: "tokensUsedThisPeriod",
      header: "Tokens this period",
      cell: ({ row }) => row.original.tokensUsedThisPeriod.toLocaleString(),
    },
    {
      accessorKey: "createdAt",
      header: "Joined",
      cell: ({ row }) => new Date(row.original.createdAt).toLocaleDateString(),
    },
    {
      id: "actions",
      cell: ({ row }) => {
        const user = row.original
        const isSelf = user.id === currentUser?.id
        return (
          <DropdownMenu>
            <DropdownMenuTrigger
              render={<Button variant="ghost" size="icon" className="size-8" />}
            >
              <EllipsisVerticalIcon className="size-4" />
              <span className="sr-only">Open actions</span>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => setUsageUser(user)}>
                View usage
              </DropdownMenuItem>
              {user.role === "admin" ? (
                <DropdownMenuItem
                  disabled={isSelf}
                  onClick={() => setPendingAction({ user, kind: "demote" })}
                >
                  Demote to user
                </DropdownMenuItem>
              ) : (
                <DropdownMenuItem
                  onClick={() => setPendingAction({ user, kind: "promote" })}
                >
                  Promote to admin
                </DropdownMenuItem>
              )}
              {user.isActive ? (
                <DropdownMenuItem
                  disabled={isSelf}
                  variant="destructive"
                  onClick={() => setPendingAction({ user, kind: "deactivate" })}
                >
                  Deactivate
                </DropdownMenuItem>
              ) : (
                <DropdownMenuItem
                  onClick={() => setPendingAction({ user, kind: "activate" })}
                >
                  Activate
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        )
      },
    },
  ]

  return (
    <div className="space-y-4">
      <Input
        placeholder="Search by email..."
        value={searchInput}
        onChange={(event) => setSearchInput(event.target.value)}
        className="max-w-sm"
      />
      {isLoading || !data ? (
        <Skeleton className="h-96 w-full" />
      ) : (
        <DataTable
          columns={columns}
          data={data.items}
          pageCount={Math.ceil(data.total / PAGE_SIZE)}
          pagination={{ pageIndex, pageSize: PAGE_SIZE }}
          onPaginationChange={(pagination) =>
            setPageIndex(pagination.pageIndex)
          }
          emptyMessage="No users found."
        />
      )}

      <AlertDialog
        open={pendingAction !== null}
        onOpenChange={(open) => !open && setPendingAction(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {pendingAction ? actionLabels[pendingAction.kind] : ""}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {pendingAction
                ? `Are you sure you want to ${actionLabels[
                    pendingAction.kind
                  ].toLowerCase()} for ${pendingAction.user.email}?`
                : ""}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmAction}>
              Confirm
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {usageUser && (
        <UsageDialog user={usageUser} onClose={() => setUsageUser(null)} />
      )}
    </div>
  )
}
