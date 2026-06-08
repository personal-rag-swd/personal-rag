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
import { useNotebooks } from "@/features/notebooks/store/notebook-store"
import { MoreHorizontalIcon, Trash2Icon, FolderIcon } from "lucide-react"
import { useNavigate } from "react-router-dom"

export function NavNotebooks() {
  const { notebooks, selectNotebook, deleteNotebook } = useNotebooks()
  const { isMobile } = useSidebar()
  const navigate = useNavigate()

  if (notebooks.length === 0) return null

  return (
    <SidebarGroup className="select-none group-data-[collapsible=icon]:hidden">
      <SidebarGroupLabel className="font-semibold text-sidebar-foreground/60">
        Notebooks
      </SidebarGroupLabel>
      <SidebarMenu>
        {notebooks.map((notebook) => {
          return (
            <SidebarMenuItem key={notebook.id} className="group/item">
              <SidebarMenuButton
                onClick={() => {
                  selectNotebook(notebook.id)
                  void navigate(`/notebook/${notebook.id}`)
                }}
                className="transition-all duration-200"
              >
                <span className="truncate font-medium text-sidebar-foreground/80">
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
                  <DropdownMenuItem
                    onClick={() => {
                      selectNotebook(notebook.id)
                      void navigate(`/notebook/${notebook.id}`)
                    }}
                  >
                    <FolderIcon className="mr-2 size-4" />
                    <span>Select Notebook</span>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    variant="destructive"
                    onClick={(e) => {
                      e.stopPropagation()
                      deleteNotebook(notebook.id)
                    }}
                  >
                    <Trash2Icon className="mr-2 size-4" />
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
