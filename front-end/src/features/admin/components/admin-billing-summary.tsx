import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useAdminBillingSummaryQuery } from "../api"
import { AdminOrdersTable } from "./admin-orders-table"

function BreakdownCard({
  title,
  entries,
}: {
  title: string
  entries: Record<string, number>
}) {
  const rows = Object.entries(entries).sort(([, a], [, b]) => b - a)
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">No data yet.</p>
        ) : (
          <div className="grid gap-2 text-sm">
            {rows.map(([key, count]) => (
              <div key={key} className="flex justify-between">
                <span className="text-muted-foreground">{key}</span>
                <span className="font-medium">{count}</span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export function AdminBillingSummary() {
  const { data, isLoading } = useAdminBillingSummaryQuery()

  return (
    <div className="space-y-6">
      {isLoading || !data ? (
        <div className="grid gap-4 md:grid-cols-3">
          {Array.from({ length: 3 }, (_, index) => (
            <Skeleton key={index} className="h-40" />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader>
              <CardTitle>Total customers</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{data.totalCustomers}</div>
            </CardContent>
          </Card>
          <BreakdownCard
            title="By subscription status"
            entries={data.byStatus}
          />
          <BreakdownCard title="By product" entries={data.byProduct} />
        </div>
      )}
      <AdminOrdersTable />
    </div>
  )
}
