import * as React from "react"
import type { ColumnDef } from "@tanstack/react-table"

import { Badge } from "@/components/ui/badge"
import { DataTable } from "@/components/ui/data-table"
import { Skeleton } from "@/components/ui/skeleton"
import { useAdminTransactionsQuery } from "../api"
import type { AdminTransaction } from "../types"

const PAGE_SIZE = 20

const columns: ColumnDef<AdminTransaction>[] = [
  {
    accessorKey: "createdAt",
    header: "Date",
    cell: ({ row }) => new Date(row.original.createdAt).toLocaleString(),
  },
  {
    accessorKey: "userId",
    header: "User",
    cell: ({ row }) => (
      <span className="font-mono text-xs">
        {row.original.userId.slice(0, 8)}
      </span>
    ),
  },
  {
    accessorKey: "quantity",
    header: "Tokens",
    cell: ({ row }) => row.original.quantity.toLocaleString(),
  },
  {
    accessorKey: "polarIngested",
    header: "Polar",
    cell: ({ row }) =>
      row.original.polarIngested ? (
        <Badge variant="secondary">ingested</Badge>
      ) : row.original.polarIngestError ? (
        <Badge variant="destructive">error</Badge>
      ) : (
        <Badge variant="outline">pending</Badge>
      ),
  },
  {
    accessorKey: "retryCount",
    header: "Retries",
    cell: ({ row }) => row.original.retryCount,
  },
]

export function AdminTransactionsTable() {
  const [pageIndex, setPageIndex] = React.useState(0)
  const { data, isLoading } = useAdminTransactionsQuery({
    page: pageIndex + 1,
    pageSize: PAGE_SIZE,
  })

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-base font-semibold">Token usage events</h3>
        <p className="text-sm text-muted-foreground">
          Billable LLM-token events metered to Polar.
        </p>
      </div>
      {isLoading || !data ? (
        <Skeleton className="h-80 w-full" />
      ) : (
        <DataTable
          columns={columns}
          data={data.items}
          pageCount={Math.ceil(data.total / PAGE_SIZE)}
          pagination={{ pageIndex, pageSize: PAGE_SIZE }}
          onPaginationChange={(pagination) => setPageIndex(pagination.pageIndex)}
          emptyMessage="No usage events yet."
        />
      )}
    </div>
  )
}
