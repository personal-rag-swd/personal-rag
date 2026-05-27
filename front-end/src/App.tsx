import { BrowserRouter } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import * as React from "react";

import { queryClient } from "@/lib/query-client";
import { useAuthStore } from "@/features/auth/store/auth-store";
import { AppRoutes } from "@/routes";
import { Toaster } from "@/components/ui/sonner";
import { ThemeClassEffect } from "@/components/theme-provider";

function AuthSessionEffect() {
  const initializeSession = useAuthStore((state) => state.initializeSession);

  React.useEffect(() => {
    void initializeSession();
  }, [initializeSession]);

  return null;
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ThemeClassEffect />
        <AuthSessionEffect />
        <AppRoutes />
        <Toaster position="top-right" richColors />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
