"use client"

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuAction,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"
import { useNotebooks } from "@/hooks/use-notebooks"
import { MoreHorizontalIcon, Trash2Icon, FolderIcon } from "lucide-react"

export function NavNotebooks() {
  const { notebooks, activeNotebook, selectNotebook, deleteNotebook } = useNotebooks()
  const { isMobile } = useSidebar()


  if (notebooks.length === 0) return null;

  return (
    <SidebarGroup className="group-data-[collapsible=icon]:hidden select-none">
      <SidebarGroupLabel className="font-semibold text-sidebar-foreground/60">Notebooks</SidebarGroupLabel>
      <SidebarMenu>
        {notebooks.map((notebook) => {
          const isActive = activeNotebook?.id === notebook.id

          return (
            <SidebarMenuItem key={notebook.id} className="group/item">
              <SidebarMenuButton 
                onClick={() => selectNotebook(notebook.id)}
                isActive={isActive}
                className="transition-all duration-200"
              >
                <span className={`truncate ${isActive ? "font-semibold" : "font-medium text-sidebar-foreground/80"}`}>
                  {notebook.name}
                </span>
              </SidebarMenuButton>
              <DropdownMenu>
                <DropdownMenuTrigger
                  render={
                    <SidebarMenuAction
                      showOnHover
                      className="aria-expanded:bg-muted"
                    />
                  }
                >
                  <MoreHorizontalIcon />
                  <span className="sr-only">More</span>
                </DropdownMenuTrigger>
                <DropdownMenuContent
                  className="w-40"
                  side={isMobile ? "bottom" : "right"}
                  align={isMobile ? "end" : "start"}
                >
                  <DropdownMenuItem onClick={() => selectNotebook(notebook.id)}>
                    <FolderIcon className="size-4 mr-2" />
                    <span>Select Notebook</span>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem 
                    variant="destructive"
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteNotebook(notebook.id);
                    }}
                  >
                    <Trash2Icon className="size-4 mr-2" />
                    <span>Delete</span>
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </SidebarMenuItem>
          )
        })}
      </SidebarMenu>
    </SidebarGroup>
  )
}
