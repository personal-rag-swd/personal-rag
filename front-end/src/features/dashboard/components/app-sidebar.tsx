import * as React from "react"
import { Link, useNavigate } from "react-router-dom"
import { toast } from "sonner"

import { AviaryLogo } from "@/components/branding/aviary-logo"
import { NavMain } from "./nav-main"
import { NavNotebooks } from "./nav-notebooks"
import { NavSecondary } from "./nav-secondary"
import { NavUser } from "./nav-user"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"
import { Dialog } from "@/components/ui/dialog"
import { useNotebooks } from "@/features/notebooks/store/notebook-store"
import { CreateNotebookDialogContent } from "./dashboard-client"
import {
  LayoutDashboardIcon,
  SearchIcon,
} from "lucide-react"

const data = {
  user: {
    name: "Personal RAG",
    email: "workspace@example.com",
    avatar: "/avatars/shadcn.jpg",
  },
  navMain: [
    {
      title: "Dashboard",
      url: "/dashboard",
      icon: <LayoutDashboardIcon />,
    },
  ],
  navSecondary: [
    {
      title: "Search",
      url: "#",
      icon: <SearchIcon />,
    },
  ],
}

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const [isCreateOpen, setIsCreateOpen] = React.useState(false)
  const navigate = useNavigate()
  const { addNotebook } = useNotebooks()

  return (
    <Sidebar collapsible="offcanvas" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              className="data-[slot=sidebar-menu-button]:p-1.5!"
              render={<Link to="/dashboard" />}
            >
              <AviaryLogo className="h-14 w-14 shrink-0 object-contain" />
              <span className="text-base font-semibold">Aviary</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <NavMain items={data.navMain} onQuickCreateClick={() => setIsCreateOpen(true)} />
        <NavNotebooks />
        <NavSecondary items={data.navSecondary} className="mt-auto" />
      </SidebarContent>
      <SidebarFooter>
        <NavUser user={data.user} />
      </SidebarFooter>

      <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
        {isCreateOpen && (
          <CreateNotebookDialogContent
            onSuccess={(notebook) => {
              addNotebook(notebook)
              toast.success("Notebook created", {
                description: `"${notebook.name}" is now ready for use.`,
              })
              setIsCreateOpen(false)
              void navigate(`/notebook/${notebook.id}`)
            }}
            onClose={() => setIsCreateOpen(false)}
          />
        )}
      </Dialog>
    </Sidebar>
  )
}
