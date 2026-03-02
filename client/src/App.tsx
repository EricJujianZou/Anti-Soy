import React, { Suspense } from "react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import LandingPage from "./pages/LandingPage";
import Index from "./pages/Index";
import HackerPage from "./pages/HackerPage";
import RepoAnalysis from "./pages/RepoAnalysis";
import NotFound from "./pages/NotFound";
import { usePageTracking } from "./hooks/usePageTracking";

const UploadPage = React.lazy(() => import("./pages/UploadPage"));
const BatchDashboard = React.lazy(() => import("./pages/BatchDashboard"));

const queryClient = new QueryClient();

const basename = "";

// Inner component so usePageTracking can call useLocation inside BrowserRouter
const AppContent = () => {
  usePageTracking();
  return (
    <Suspense fallback={<div className="flex items-center justify-center min-h-screen">Loading...</div>}>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/recruiter" element={<Index />} />
        <Route path="/hacker" element={<HackerPage />} />
        <Route path="/repo/:repoId" element={<RepoAnalysis />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/dashboard/:batchId" element={<BatchDashboard />} />
        {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
};

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter basename={basename}>
        <AppContent />
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
