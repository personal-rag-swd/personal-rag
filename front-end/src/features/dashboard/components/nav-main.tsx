import { Link, useLocation } from "react-router-dom"

import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"
import { CirclePlusIcon, LayoutDashboardIcon, ChartBarIcon } from "lucide-react"

export function NavMain({
  items,
  onQuickCreateClick,
}: {
  items: {
    title: string
    url: string
    icon?: React.ReactNode
  }[]
  onQuickCreateClick?: () => void
}) {
  const location = useLocation()

  return (
    <SidebarGroup>
      <SidebarGroupContent className="flex flex-col gap-2">
        <SidebarMenu>
          <SidebarMenuItem className="flex items-center gap-2">
            <SidebarMenuButton
              onClick={onQuickCreateClick}
              tooltip="Quick Create"
              className="min-w-8 bg-primary text-primary-foreground duration-200 ease-linear hover:bg-primary/90 hover:text-primary-foreground active:bg-primary/90 active:text-primary-foreground"
            >
              <CirclePlusIcon />
              <span>Quick Create</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
        <SidebarMenu>
          {items.map((item) => {
            const isActive = location.pathname === item.url
            return (
              <SidebarMenuItem key={item.title}>
                <SidebarMenuButton
                  isActive={isActive}
                  tooltip={item.title}
                  className={`
                    transition-all duration-150
                    ${isActive
                      ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium shadow-sm"
                      : "hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground"
                    }
                  `}
                  render={
                    item.url.startsWith("/") ? (
                      <Link to={item.url} />
                    ) : (
                      <a href={item.url} />
                    )
                  }
                >
                  {item.icon}
                  <span>{item.title}</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            )
          })}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  )
}

// Add the nav items config for easy access
NavMain.defaultProps = {
  items: [
    { title: "Dashboard", url: "/dashboard", icon: <LayoutDashboardIcon /> },
    { title: "Analytics", url: "/analytics", icon: <ChartBarIcon /> },
  ],
}
