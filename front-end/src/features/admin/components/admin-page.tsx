import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { AdminBillingSummary } from "./admin-billing-summary"
import { AdminDocumentsTable } from "./admin-documents-table"
import { AdminOverview } from "./admin-overview"
import { AdminUsersTable } from "./admin-users-table"

export function AdminPage() {
  return (
    <div className="flex flex-1 flex-col gap-6 p-4 md:p-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Admin</h1>
        <p className="text-sm text-muted-foreground">
          Platform metrics, user management, ingestion monitoring, and billing.
        </p>
      </div>
      <Tabs defaultValue="overview" className="space-y-6">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="users">Users</TabsTrigger>
          <TabsTrigger value="ingestion">Ingestion</TabsTrigger>
          <TabsTrigger value="billing">Billing</TabsTrigger>
        </TabsList>
        <TabsContent value="overview" className="space-y-6">
          <AdminOverview />
        </TabsContent>
        <TabsContent value="users" className="space-y-6">
          <AdminUsersTable />
        </TabsContent>
        <TabsContent value="ingestion" className="space-y-6">
          <AdminDocumentsTable />
        </TabsContent>
        <TabsContent value="billing" className="space-y-6">
          <AdminBillingSummary />
        </TabsContent>
      </Tabs>
    </div>
  )
}
