import React, { useEffect, useState } from 'react';
import { StatCard } from '../components/dashboard/StatCard';
import { FileUploadZone } from '../components/dashboard/FileUploadZone';
import { RecentFilesTable } from '../components/dashboard/RecentFilesTable';
import { FileSpreadsheet, HelpCircle, Sparkles } from 'lucide-react';
import { api } from '../lib/api';
import type { Fichier, DashboardStats } from '../types';
import { toast } from 'sonner';

export function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats>({ files_count: 0, questions_count: 0 });
  const [recentFiles, setRecentFiles] = useState<Fichier[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const loadDashboardData = async () => {
    setIsLoading(true);
    try {
      const data = await api.getDashboard();
      setStats(data.stats);
      setRecentFiles(data.recent_files);
    } catch (err: any) {
      toast.error('Erreur lors du chargement des données du tableau de bord.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
  }, []);

  return (
    <div className="space-y-8">
      {/* Welcome banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-slate-900 via-slate-900/90 to-cyan-950/40 p-6 sm:p-8 border border-slate-800/80 shadow-xl">
        <div className="relative z-10 max-w-2xl">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 text-xs font-semibold mb-3">
            <Sparkles className="h-3.5 w-3.5" /> Espace Décisionnel
          </div>
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-50">
            Tableau de Bord DataIA
          </h2>
          <p className="mt-2 text-sm text-slate-300 leading-relaxed">
            Importez vos fichiers de données tabulaires pour obtenir des analyses assistées par IA et générer vos rapports en un clic.
          </p>
        </div>
      </div>

      {/* KPI Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
        <StatCard
          title="Mes Fichiers Importés"
          value={isLoading ? '...' : stats.files_count}
          description="Fichiers prêts à l'analyse (CSV, Excel, PDF, images)"
          icon={<FileSpreadsheet className="h-6 w-6" />}
          gradient="cyan"
        />

        <StatCard
          title="Questions Posées à l'IA"
          value={isLoading ? '...' : stats.questions_count}
          description="Total des requêtes RAG et analyses générées"
          icon={<HelpCircle className="h-6 w-6" />}
          gradient="purple"
        />
      </div>

      {/* Upload Zone */}
      <FileUploadZone onUploadSuccess={loadDashboardData} />

      {/* Recent Files Table */}
      <RecentFilesTable
        files={recentFiles}
        isLoading={isLoading}
        onRefresh={loadDashboardData}
        showAllLink={true}
      />
    </div>
  );
}
