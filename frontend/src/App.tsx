import type { ReactElement } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Shell from "./components/Shell";
import { getToken } from "./lib/api";
import { SessionProvider, useSession } from "./lib/session";
import LandingPage from "./pages/Landing";
import EntryPage from "./pages/Entry";
import OverviewPage from "./pages/admin/Overview";
import KnowledgePage from "./pages/admin/Knowledge";
import ReviewPage from "./pages/admin/Review";
import ReviewDetailPage from "./pages/admin/ReviewDetail";
import CampaignsPage from "./pages/admin/Campaigns";
import IntelligencePage from "./pages/admin/Intelligence";
import ApprovalsPage from "./pages/admin/Approvals";
import FreelancerDashboard from "./pages/freelancer/Dashboard";
import TasksPage from "./pages/freelancer/Tasks";
import TaskDetailPage from "./pages/freelancer/TaskDetail";
import SubmitPage from "./pages/freelancer/Submit";
import MySubmissionsPage from "./pages/freelancer/Submissions";
import SubmissionDetailPage from "./pages/freelancer/SubmissionDetail";
import FeedbackPage from "./pages/freelancer/Feedback";
import KnowledgeWalletPage from "./pages/freelancer/KnowledgeWallet";
import CampaignScannerPage from "./pages/freelancer/CampaignScanner";

function Home() {
  const { isFreelancer } = useSession();
  return <Shell>{isFreelancer ? <FreelancerDashboard /> : <OverviewPage />}</Shell>;
}

function Guard({ admin, children }: { admin: boolean; children: ReactElement }) {
  const { isAdmin, isFreelancer } = useSession();
  if (admin && !isAdmin) return <Navigate to={isFreelancer ? "/" : "/"} replace />;
  if (!admin && !isFreelancer) return <Navigate to="/" replace />;
  return <Shell>{children}</Shell>;
}

function PublicRoutes() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/get-started" element={<EntryPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function AuthenticatedRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/get-started" element={<Navigate to="/" replace />} />
      <Route path="/knowledge" element={<Guard admin><KnowledgePage /></Guard>} />
      <Route path="/review" element={<Guard admin><ReviewPage /></Guard>} />
      <Route path="/review/:id" element={<Guard admin><ReviewDetailPage /></Guard>} />
      <Route path="/campaigns" element={<Guard admin><CampaignsPage /></Guard>} />
      <Route path="/intelligence" element={<Guard admin><IntelligencePage /></Guard>} />
      <Route path="/approvals" element={<Guard admin><ApprovalsPage /></Guard>} />

      <Route path="/wallet" element={<Guard admin={false}><KnowledgeWalletPage /></Guard>} />
      <Route path="/scanner" element={<Guard admin={false}><CampaignScannerPage /></Guard>} />
      <Route path="/tasks" element={<Guard admin={false}><TasksPage /></Guard>} />
      <Route path="/tasks/:id" element={<Guard admin={false}><TaskDetailPage /></Guard>} />
      <Route path="/submit" element={<Guard admin={false}><SubmitPage /></Guard>} />
      <Route path="/submissions" element={<Guard admin={false}><MySubmissionsPage /></Guard>} />
      <Route path="/submissions/:id" element={<Guard admin={false}><SubmissionDetailPage /></Guard>} />
      <Route path="/feedback" element={<Guard admin={false}><FeedbackPage /></Guard>} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function Application() {
  const { user } = useSession();
  if (!getToken() || !user) return <PublicRoutes />;
  return <AuthenticatedRoutes />;
}

export default function App() {
  return (
    <BrowserRouter>
      <SessionProvider>
        <Application />
      </SessionProvider>
    </BrowserRouter>
  );
}
