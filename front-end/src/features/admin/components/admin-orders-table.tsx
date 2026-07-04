import * as React from "react"
import type { ColumnDef } from "@tanstack/react-table"

import { Badge } from "@/components/ui/badge"
import { DataTable } from "@/components/ui/data-table"
import { Skeleton } from "@/components/ui/skeleton"
import { useAdminOrdersQuery } from "../api"
import type { AdminOrder } from "../types"

const PAGE_SIZE = 20

function formatAmount(order: AdminOrder) {
  if (order.amount === null) return "—"
  const currency = (order.currency ?? "usd").toUpperCase()
  // Polar amounts are in minor units (cents).
  return `${(order.amount / 100).toFixed(2)} ${currency}`
}

const columns: ColumnDef<AdminOrder>[] = [
  {
    accessorKey: "createdAt",
    header: "Date",
    cell: ({ row }) =>
      row.original.createdAt
        ? new Date(row.original.createdAt).toLocaleString()
        : "—",
  },
  {
    accessorKey: "customerEmail",
    header: "Customer",
    cell: ({ row }) =>
      row.original.customerEmail ?? (
        <span className="text-muted-foreground">—</span>
      ),
  },
  {
    id: "amount",
    header: "Amount",
    cell: ({ row }) => formatAmount(row.original),
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) =>
      row.original.status ? (
        <Badge variant="outline">{row.original.status}</Badge>
      ) : (
        <span className="text-muted-foreground">—</span>
      ),
  },
  {
    accessorKey: "id",
    header: "Order ID",
    cell: ({ row }) => (
      <span className="font-mono text-xs">{row.original.id.slice(0, 8)}</span>
    ),
  },
]

export function AdminOrdersTable() {
  const [pageIndex, setPageIndex] = React.useState(0)
  const { data, isLoading } = useAdminOrdersQuery({
    page: pageIndex + 1,
    pageSize: PAGE_SIZE,
  })

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-base font-semibold">Orders</h3>
        <p className="text-sm text-muted-foreground">
          Payments and subscription orders from Polar.
        </p>
      </div>
      {isLoading || !data ? (
        <Skeleton className="h-80 w-full" />
      ) : !data.configured ? (
        <div className="rounded-md border p-6 text-center text-sm text-muted-foreground">
          Polar billing is not configured in this environment.
        </div>
      ) : (
        <DataTable
          columns={columns}
          data={data.items}
          pageCount={Math.ceil(data.total / PAGE_SIZE)}
          pagination={{ pageIndex, pageSize: PAGE_SIZE }}
          onPaginationChange={(pagination) => setPageIndex(pagination.pageIndex)}
          emptyMessage="No orders found."
        />
      )}
    </div>
  )
}
