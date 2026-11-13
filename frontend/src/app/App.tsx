import { lazy, Suspense, useState } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig } from "framer-motion";
import { BankProvider } from "../hooks/useBank";
import AppLayout from "../layouts/AppLayout";
import Landing from "../pages/Landing";
import { SkeletonRows } from "../components/ui";
import NotFound from "../pages/NotFound";

const Overview = lazy(() => import("../pages/Overview"));
const Workspace = lazy(() => import("../pages/Workspace"));
const Chat = lazy(() => import("../pages/Chat"));
const History = lazy(() => import("../pages/History"));
const AuditPage = lazy(() => import("../pages/AuditPage"));
const KnowledgeBase = lazy(() => import("../pages/KnowledgeBase"));
const Models = lazy(() => import("../pages/Models"));
const Settings = lazy(() => import("../pages/Settings"));

export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: (n, err) => n < 1 && !(err as { status?: number })?.status, staleTime: 5_000, refetchOnWindowFocus: false },
    },
  });
}

export function AppRoutes() {
  return (
    <Suspense fallback={<div className="p-8"><SkeletonRows /></div>}>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/app" element={<AppLayout />}>
          <Route index element={<Overview />} />
          <Route path="chat" element={<Chat />} />
          <Route path="chat/:id" element={<Chat />} />
          <Route path="workspace" element={<Workspace />} />
          <Route path="history" element={<History />} />
          <Route path="runs/:id" element={<AuditPage />} />
          <Route path="knowledge" element={<KnowledgeBase />} />
          <Route path="models" element={<Models />} />
          <Route path="settings" element={<Settings />} />
          <Route path="*" element={<NotFound />} />
        </Route>
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
}

export default function App() {
  const [client] = useState(makeQueryClient);
  return (
    <QueryClientProvider client={client}>
      <MotionConfig reducedMotion="user">
        <BankProvider>
          <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><AppRoutes /></BrowserRouter>
        </BankProvider>
      </MotionConfig>
    </QueryClientProvider>
  );
}
