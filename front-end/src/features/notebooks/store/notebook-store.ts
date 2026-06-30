import { create } from "zustand"

import {
  useDeleteNotebookMutation,
  useNotebooksQuery,
  useTouchNotebookMutation,
} from "../api"
import { type Notebook } from "../types"

interface NotebookUiStore {
  activeNotebookId: string | null
  setActiveNotebookId: (id: string | null) => void
}

export interface NotebookHookValue {
  notebooks: Notebook[]
  activeNotebook: Notebook | null
  isLoading: boolean
  selectNotebook: (id: string) => void
  addNotebook: (notebook: Notebook) => void
  deleteNotebook: (id: string) => void
  updateNotebook: () => void
}

export const useNotebookUiStore = create<NotebookUiStore>((set) => ({
  activeNotebookId: null,
  setActiveNotebookId: (id) => set({ activeNotebookId: id }),
}))

export function useNotebooks(): NotebookHookValue {
  const { data: notebooks = [], isLoading } = useNotebooksQuery()
  const deleteMutation = useDeleteNotebookMutation()
  const touchMutation = useTouchNotebookMutation()
  const activeNotebookId = useNotebookUiStore((state) => state.activeNotebookId)
  const setActiveNotebookId = useNotebookUiStore(
    (state) => state.setActiveNotebookId
  )

  const activeNotebook = activeNotebookId
    ? (notebooks.find((notebook) => notebook.id === activeNotebookId) ?? null)
    : (notebooks[0] ?? null)

  return {
    notebooks,
    activeNotebook,
    isLoading,
    selectNotebook: (id) => {
      setActiveNotebookId(id)
      touchMutation.mutate(id)
    },
    addNotebook: (notebook) => {
      setActiveNotebookId(notebook.id)
    },
    deleteNotebook: (id) => {
      deleteMutation.mutate(id, {
        onSuccess: () => {
          const currentActiveId = activeNotebookId || notebooks[0]?.id

          if (currentActiveId === id) {
            const remaining = notebooks.filter((notebook) => notebook.id !== id)
            setActiveNotebookId(remaining[0]?.id ?? null)
          }
        },
      })
    },
    updateNotebook: () => {
      // React Query invalidation in api.ts refetches notebooks after mutation.
    },
  }
}
