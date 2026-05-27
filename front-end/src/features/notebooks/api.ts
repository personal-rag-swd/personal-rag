import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { type Notebook, type NotebookApiPayload } from "./types";

export function mapNotebook(payload: NotebookApiPayload): Notebook {
  return {
    id: payload.id,
    name: payload.name,
    description: payload.description,
    documentCount: payload.document_count,
    queryCount: payload.query_count,
    createdAt: payload.created_at,
    lastActiveAt: payload.last_active_at,
    tags: payload.tags,
  };
}

export function useNotebooksQuery() {
  return useQuery<Notebook[]>({
    queryKey: ["notebooks"],
    queryFn: async () => {
      const data = await apiFetch<NotebookApiPayload[]>("/api/v1/notebooks/");
      return data.map(mapNotebook);
    },
  });
}

export function useCreateNotebookMutation() {
  const queryClient = useQueryClient();
  return useMutation<Notebook, Error, { name: string; description: string; tags: string[] }>({
    mutationFn: async (variables: { name: string; description: string; tags: string[] }) => {
      const data = await apiFetch<NotebookApiPayload>("/api/v1/notebooks/", {
        method: "POST",
        data: variables,
      });
      return mapNotebook(data);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["notebooks"] });
    },
  });
}

export function useUpdateNotebookMutation() {
  const queryClient = useQueryClient();
  return useMutation<Notebook, Error, { id: string; name: string; description: string; tags: string[] }>({
    mutationFn: async ({ id, ...variables }: { id: string; name: string; description: string; tags: string[] }) => {
      const data = await apiFetch<NotebookApiPayload>(`/api/v1/notebooks/${id}`, {
        method: "PATCH",
        data: variables,
      });
      return mapNotebook(data);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["notebooks"] });
    },
  });
}

export function useDeleteNotebookMutation() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: async (id: string) => {
      await apiFetch(`/api/v1/notebooks/${id}`, {
        method: "DELETE",
      });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["notebooks"] });
    },
  });
}

export function useTouchNotebookMutation() {
  const queryClient = useQueryClient();
  return useMutation<Notebook, Error, string>({
    mutationFn: async (id: string) => {
      const data = await apiFetch<NotebookApiPayload>(`/api/v1/notebooks/${id}/touch`, {
        method: "POST",
      });
      return mapNotebook(data);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["notebooks"] });
    },
  });
}
