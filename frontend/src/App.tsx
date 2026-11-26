import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from './hooks/useAuth';
import { Toaster } from 'sonner';

// Pages
import { LandingPage } from './pages/LandingPage';
import { LoginPage } from './pages/LoginPage';
import { SignupPage } from './pages/SignupPage';
import { DashboardPage } from './pages/DashboardPage';
import { MyFilesPage } from './pages/MyFilesPage';
import { ChatPage } from './pages/ChatPage';
import { AdminPage } from './pages/AdminPage';
import { SimulatorPage } from './pages/SimulatorPage';
import { ProfilePage } from './pages/ProfilePage';
import { CleanedDataPage } from './pages/CleanedDataPage';

// Layout
import { AppLayout } from './components/layout/AppLayout';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

/**
 * Phase 6 : l'application est servie par Flask sous /app/ (basename), les appels au serveur
 * passent par /api/* (session Flask-Login). Les pages Jinja restent disponibles en secours.
 */
export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter basename="/app">
          <Routes>
            {/* Pages publiques */}
            <Route path="/" element={<LandingPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />

            {/* Espace connecté */}
            <Route element={<AppLayout title="Tableau de bord" subtitle="Analyse intelligente et suivi des activités" />}>
              <Route path="/dashboard" element={<DashboardPage />} />
            </Route>
            <Route element={<AppLayout title="Mes fichiers" subtitle="CSV, Excel, PDF et images" />}>
              <Route path="/files" element={<MyFilesPage />} />
            </Route>
            <Route element={<AppLayout title="Assistant IA" subtitle="Calculs pandas, graphiques, modèles ML et simulateur" />}>
              <Route path="/chat/:fileId" element={<ChatPage />} />
            </Route>
            <Route element={<AppLayout title="Simulateur ML" subtitle="Scénarios what-if selon votre domaine" />}>
              <Route path="/simulator" element={<SimulatorPage />} />
            </Route>
            <Route element={<AppLayout title="Données nettoyées" subtitle="Données passées aux modèles et rapports de nettoyage" />}>
              <Route path="/donnees" element={<CleanedDataPage />} />
            </Route>
            <Route element={<AppLayout title="Mon profil" subtitle="Nom et domaine d'activité" />}>
              <Route path="/profil" element={<ProfilePage />} />
            </Route>

            {/* Console admin (réservée) */}
            <Route element={<AppLayout title="Console Admin" subtitle="Gouvernance et supervision" adminOnly={true} />}>
              <Route path="/admin" element={<AdminPage />} />
            </Route>

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
        <Toaster position="top-right" richColors theme="light" closeButton />
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
