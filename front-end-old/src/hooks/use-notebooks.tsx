"use client";

import * as React from "react";

import {
  deleteNotebookAction,
  touchNotebookAction,
} from "@/features/notebooks/actions";
import { type Notebook } from "@/features/notebooks/types";

export interface NotebookContextType {
  notebooks: Notebook[];
  activeNotebook: Notebook | null;
  selectNotebook: (id: string) => void;
  addNotebook: (notebook: Notebook) => void;
  deleteNotebook: (id: string) => void;
  updateNotebook: (id: string, updates: Partial<Notebook>) => void;
}

const NotebookContext = React.createContext<NotebookContextType | undefined>(undefined);

export function NotebookProvider({
  children,
  notebooks: initialNotebooks = [],
}: {
  children: React.ReactNode;
  notebooks?: Notebook[];
}) {
  const [notebooks, setNotebooks] = React.useState<Notebook[]>(initialNotebooks);
  const [activeId, setActiveId] = React.useState<string | null>(() => {
    return initialNotebooks[0]?.id ?? null;
  });

  const selectNotebook = React.useCallback((id: string) => {
    setActiveId(id);
    const now = new Date().toISOString();
    setNotebooks((prev) => {
      return prev.map((notebook) =>
        notebook.id === id ? { ...notebook, lastActiveAt: now } : notebook
      );
    });

    void touchNotebookAction(id)
      .then((notebook) => {
        setNotebooks((prev) =>
          prev.map((current) => (current.id === notebook.id ? notebook : current))
        );
      })
      .catch((error) => {
        console.error("Failed to update notebook activity", error);
      });
  }, []);

  const addNotebook = React.useCallback((notebook: Notebook) => {
    setNotebooks((prev) => [notebook, ...prev.filter((current) => current.id !== notebook.id)]);
    setActiveId(notebook.id);
  }, []);

  const deleteNotebook = React.useCallback(
    (id: string) => {
      const previousActiveId = activeId;
      let deletedNotebook: Notebook | undefined;

      setNotebooks((prev) => {
        deletedNotebook = prev.find((notebook) => notebook.id === id);
        const updated = prev.filter((nb) => nb.id !== id);
        if (activeId === id) {
          setActiveId(updated[0]?.id ?? null);
        }
        return updated;
      });

      void deleteNotebookAction(id).catch((error) => {
        console.error("Failed to delete notebook", error);
        if (!deletedNotebook) return;
        setNotebooks((prev) => [deletedNotebook as Notebook, ...prev]);
        setActiveId(previousActiveId);
      });
    },
    [activeId]
  );

  const updateNotebook = React.useCallback(
    (id: string, updates: Partial<Notebook>) => {
      setNotebooks((prev) => {
        return prev.map((nb) => (nb.id === id ? { ...nb, ...updates } : nb));
      });
    },
    []
  );

  const activeNotebook = React.useMemo(() => {
    return notebooks.find((nb) => nb.id === activeId) || null;
  }, [notebooks, activeId]);

  const value = React.useMemo(
    () => ({
      notebooks,
      activeNotebook,
      selectNotebook,
      addNotebook,
      deleteNotebook,
      updateNotebook,
    }),
    [
      notebooks,
      activeNotebook,
      selectNotebook,
      addNotebook,
      deleteNotebook,
      updateNotebook,
    ]
  );

  return <NotebookContext.Provider value={value}>{children}</NotebookContext.Provider>;
}

export function useNotebooks() {
  const context = React.useContext(NotebookContext);
  if (context === undefined) {
    throw new Error("useNotebooks must be used within a NotebookProvider");
  }
  return context;
}
