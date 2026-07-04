import { Area, AreaChart, CartesianGrid, XAxis } from "recharts"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"
import { Skeleton } from "@/components/ui/skeleton"
import { useAdminDailyUsageQuery, useAdminStatsQuery } from "../api"

const usageChartConfig = {
  tokens: {
    label: "Tokens",
    color: "var(--chart-1)",
  },
} satisfies ChartConfig

function StatCard({ title, value }: { title: string; value: React.ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
      </CardContent>
    </Card>
  )
}

export function AdminOverview() {
  const { data: stats, isLoading: statsLoading } = useAdminStatsQuery()
  const { data: dailyUsage, isLoading: usageLoading } =
    useAdminDailyUsageQuery(30)

  if (statsLoading || !stats) {
    return (
      <div className="grid gap-4 md:grid-cols-3">
        {Array.from({ length: 6 }, (_, index) => (
          <Skeleton key={index} className="h-28" />
        ))}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 md:grid-cols-3">
        <StatCard title="Total users" value={stats.totalUsers} />
        <StatCard title="Active users" value={stats.activeUsers} />
        <StatCard title="Notebooks" value={stats.totalNotebooks} />
        <StatCard
          title="Documents (indexed / failed)"
          value={`${stats.documentsByStatus.indexed ?? 0} / ${stats.documentsByStatus.failed ?? 0}`}
        />
        <StatCard
          title="Tokens this month"
          value={stats.tokensThisMonth.toLocaleString()}
        />
        <StatCard
          title="Active subscriptions"
          value={stats.activeSubscriptions}
        />
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Daily token usage (last 30 days)</CardTitle>
        </CardHeader>
        <CardContent>
          {usageLoading ? (
            <Skeleton className="h-64 w-full" />
          ) : (
            <ChartContainer
              config={usageChartConfig}
              className="h-64 w-full"
            >
              <AreaChart data={dailyUsage ?? []}>
                <CartesianGrid vertical={false} />
                <XAxis
                  dataKey="date"
                  tickLine={false}
                  axisLine={false}
                  tickMargin={8}
                />
                <ChartTooltip content={<ChartTooltipContent />} />
                <Area
                  dataKey="tokens"
                  type="monotone"
                  fill="var(--color-tokens)"
                  fillOpacity={0.3}
                  stroke="var(--color-tokens)"
                />
              </AreaChart>
            </ChartContainer>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
