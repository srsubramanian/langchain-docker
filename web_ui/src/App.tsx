import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { MainLayout } from '@/components/layout/MainLayout';
import { ChatPage } from '@/features/chat/ChatPage';
import { MultiAgentPage } from '@/features/multiagent/MultiAgentPage';
import { BuilderPage } from '@/features/builder/BuilderPage';
import { AgentsPage } from '@/features/agents/AgentsPage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainLayout />}>
          <Route index element={<Navigate to="/agents" replace />} />
          <Route path="chat" element={<ChatPage />} />
          <Route path="agents" element={<AgentsPage />} />
          <Route path="multi-agent" element={<MultiAgentPage />} />
          <Route path="builder" element={<BuilderPage />} />
          <Route path="builder/:agentId" element={<BuilderPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
