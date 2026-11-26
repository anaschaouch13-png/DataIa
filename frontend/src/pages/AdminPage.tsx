import React, { useEffect, useState } from 'react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Dialog } from '../components/ui/Dialog';
import { StatCard } from '../components/dashboard/StatCard';
import { Skeleton } from '../components/ui/Skeleton';
import { Input } from '../components/ui/Input';
import {
  Users,
  FileText,
  BrainCircuit,
  ShieldCheck,
  Trash2,
  Lock,
  Unlock,
  Eye,
  Search,
  RotateCcw,
  Download,
} from 'lucide-react';
import { api } from '../lib/api';
import { formatDate } from '../lib/utils';
import { toast } from 'sonner';
import type { AdminData, AdminUser } from '../types';

export function AdminPage() {
  const [data, setData] = useState<AdminData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedUserFilter, setSelectedUserFilter] = useState<string | null>(null);
  const [searchReport, setSearchReport] = useState('');

  // Confirmation dialogs
  const [userToDelete, setUserToDelete] = useState<AdminUser | null>(null);
  const [isDeletingUser, setIsDeletingUser] = useState(false);
  const [actionLoadingId, setActionLoadingId] = useState<number | null>(null);

  const loadAdminData = async () => {
    setIsLoading(true);
    try {
      const res = await api.getAdminData();
      setData(res);
    } catch (err: any) {
      toast.error(err.message || 'Erreur lors du chargement des données admin.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadAdminData();
  }, []);

  // Bloquer / Débloquer
  const handleDomaine = async (userId: number, domaine: string) => {
    try {
      await api.setDomaine(userId, domaine);
      toast.success('Domaine mis à jour.');
      loadAdminData();
    } catch (err: any) {
      toast.error(err.message || 'Erreur lors de la mise à jour du domaine.');
    }
  };

  const handleToggleUser = async (user: AdminUser) => {
    setActionLoadingId(user.id_utilisateur);
    try {
      await api.toggleUser(user.id_utilisateur);
      toast.success(
        user.est_bloque === 1
          ? `Compte de ${user.nom_utilisateur} débloqué.`
          : `Compte de ${user.nom_utilisateur} bloqué.`
      );
      loadAdminData();
    } catch (err: any) {
      toast.error(err.message || "Erreur lors de la modification de l'état.");
    } finally {
      setActionLoadingId(null);
    }
  };

  // Supprimer un utilisateur
  const confirmDeleteUser = async () => {
    if (!userToDelete) return;
    setIsDeletingUser(true);
    try {
      await api.deleteUser(userToDelete.id_utilisateur);
      toast.success(`Utilisateur "${userToDelete.nom_utilisateur}" supprimé.`);
      setUserToDelete(null);
      loadAdminData();
    } catch (err: any) {
      toast.error(err.message || "Erreur lors de la suppression de l'utilisateur.");
    } finally {
      setIsDeletingUser(false);
    }
  };

  // Filtrage des rapports
  const filteredReports = data?.reports.filter((r) => {
    const matchesUser = selectedUserFilter ? r.user_name === selectedUserFilter : true;
    const matchesSearch = r.question_texte.toLowerCase().includes(searchReport.toLowerCase()) ||
                          r.user_name.toLowerCase().includes(searchReport.toLowerCase());
    return matchesUser && matchesSearch;
  }) || [];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-50 flex items-center gap-2.5">
          <ShieldCheck className="h-6 w-6 text-purple-400" />
          Console d'Administration
        </h2>
        <p className="text-xs text-slate-400 mt-1">
          Supervision globale du système, gestion des comptes utilisateurs et traçabilité des analyses.
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
        <StatCard
          title="Utilisateurs Inscrits"
          value={isLoading ? '...' : (data?.stats.users_count ?? 0)}
          description="Total des comptes enregistrés"
          icon={<Users className="h-6 w-6" />}
          gradient="purple"
        />

        <StatCard
          title="Rapports PDF Générés"
          value={isLoading ? '...' : (data?.stats.reports_count ?? 0)}
          description="Synthèses téléversées et archivées"
          icon={<FileText className="h-6 w-6" />}
          gradient="cyan"
        />

        <StatCard
          title="Total Analyses RAG"
          value={isLoading ? '...' : (data?.stats.questions_count ?? 0)}
          description="Requêtes traitées par le moteur IA"
          icon={<BrainCircuit className="h-6 w-6" />}
          gradient="slate"
        />
      </div>

      {/* Section 1: Users & Activity */}
      <Card className="border-slate-800/80 bg-slate-900/40 overflow-hidden">
        <div className="p-6 pb-4 border-b border-slate-800/80">
          <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
            <Users className="h-5 w-5 text-purple-400" />
            Utilisateurs & Activité
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Cliquez sur le badge d'activité pour filtrer les analyses d'un utilisateur spécifique.
          </p>
        </div>

        {isLoading ? (
          <div className="p-6 space-y-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-12 w-full rounded-xl" />
            ))}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-950/50 text-xs font-semibold text-slate-400 uppercase tracking-wider border-b border-slate-800">
                <tr>
                  <th className="py-3 px-6">Utilisateur</th>
                  <th className="py-3 px-4">Email</th>
                  <th className="py-3 px-4">Domaine</th>
                  <th className="py-3 px-4 text-center">Activité (Filtrer)</th>
                  <th className="py-3 px-4">Statut</th>
                  <th className="py-3 px-6 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {data?.users.map((u) => (
                  <tr key={u.id_utilisateur} className="hover:bg-slate-800/40 transition">
                    <td className="py-4 px-6 font-semibold text-slate-200">
                      {u.nom_utilisateur}
                      {u.role === 'administrateur' && (
                        <span className="ml-2 text-[10px] px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20 font-bold uppercase">
                          Admin
                        </span>
                      )}
                    </td>
                    <td className="py-4 px-4 text-xs text-slate-400">{u.email}</td>
                    <td className="py-4 px-4">
                      {/* Phase 2 : l'admin voit et modifie le domaine d'activité */}
                      <select
                        value={u.domaine}
                        onChange={(e) => handleDomaine(u.id_utilisateur, e.target.value)}
                        className="rounded-lg border border-slate-700 bg-white px-2 py-1 text-xs text-slate-200"
                        aria-label={`Domaine de ${u.nom_utilisateur}`}
                      >
                        {(data?.domaines || []).map((d) => <option key={d} value={d}>{d}</option>)}
                      </select>
                    </td>
                    <td className="py-4 px-4 text-center">
                      <button
                        onClick={() => setSelectedUserFilter(u.nom_utilisateur)}
                        className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-xl text-xs font-bold transition ${
                          selectedUserFilter === u.nom_utilisateur
                            ? 'bg-purple-500 text-white shadow-md'
                            : 'bg-purple-500/10 text-purple-400 hover:bg-purple-500/20 border border-purple-500/30'
                        }`}
                        title="Filtrer les rapports de cet utilisateur"
                      >
                        {u.nb_questions} questions <Eye className="h-3 w-3" />
                      </button>
                    </td>
                    <td className="py-4 px-4">
                      <Badge variant={u.est_bloque === 1 ? 'danger' : 'success'}>
                        {u.est_bloque === 1 ? 'Bloqué' : 'Actif'}
                      </Badge>
                    </td>
                    <td className="py-4 px-6 text-right">
                      <div className="flex items-center justify-end gap-2">
                        {/* Bloquer / Débloquer */}
                        <Button
                          variant={u.est_bloque === 1 ? 'outline' : 'secondary'}
                          size="sm"
                          isLoading={actionLoadingId === u.id_utilisateur}
                          onClick={() => handleToggleUser(u)}
                          icon={u.est_bloque === 1 ? <Unlock className="h-3.5 w-3.5" /> : <Lock className="h-3.5 w-3.5" />}
                        >
                          {u.est_bloque === 1 ? 'Débloquer' : 'Bloquer'}
                        </Button>

                        {/* Supprimer */}
                        <Button
                          variant="danger"
                          size="sm"
                          onClick={() => setUserToDelete(u)}
                          className="px-2.5"
                          title="Supprimer cet utilisateur"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Section 2: Details of Analysis & Reports */}
      <Card className="border-slate-800/80 bg-slate-900/40 overflow-hidden">
        <div className="p-6 pb-4 border-b border-slate-800/80 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
              <FileText className="h-5 w-5 text-cyan-400" />
              Détails des Analyses & Rapports
              {selectedUserFilter && (
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-purple-500/20 text-purple-300 font-normal">
                  Filtre : {selectedUserFilter}
                </span>
              )}
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Historique des questions posées et téléchargement direct des rapports PDF enregistrés.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="w-56">
              <Input
                placeholder="Rechercher..."
                value={searchReport}
                onChange={(e) => setSearchReport(e.target.value)}
                icon={<Search className="h-4 w-4" />}
              />
            </div>
            {selectedUserFilter && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelectedUserFilter(null)}
                icon={<RotateCcw className="h-3.5 w-3.5" />}
              >
                Afficher tout
              </Button>
            )}
          </div>
        </div>

        {isLoading ? (
          <div className="p-6 space-y-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-12 w-full rounded-xl" />
            ))}
          </div>
        ) : filteredReports.length === 0 ? (
          <div className="p-12 text-center text-xs text-slate-400">
            Aucun rapport trouvé pour ces critères.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-950/50 text-xs font-semibold text-slate-400 uppercase tracking-wider border-b border-slate-800">
                <tr>
                  <th className="py-3 px-6">Utilisateur</th>
                  <th className="py-3 px-6">Question / Analyse</th>
                  <th className="py-3 px-4">Date de Génération</th>
                  <th className="py-3 px-6 text-right">Rapport PDF</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {filteredReports.map((r) => (
                  <tr key={r.id_rapport} className="hover:bg-slate-800/40 transition">
                    <td className="py-4 px-6 font-semibold text-slate-200">{r.user_name}</td>
                    <td className="py-4 px-6 text-xs text-slate-300 max-w-md truncate">
                      {r.question_texte}
                    </td>
                    <td className="py-4 px-4 text-xs text-slate-400">
                      {formatDate(r.date_generation)}
                    </td>
                    <td className="py-4 px-6 text-right">
                      <a
                        href={`/view_report/${encodeURIComponent(r.chemin_resume)}`}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium bg-cyan-500/10 text-cyan-400 hover:bg-cyan-500/20 border border-cyan-500/30 transition"
                      >
                        <Download className="h-3.5 w-3.5" /> PDF
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Delete User Dialog */}
      <Dialog
        isOpen={!!userToDelete}
        title="Supprimer cet utilisateur ?"
        description={`Êtes-vous certain de vouloir supprimer le compte de "${userToDelete?.nom_utilisateur}" ? Cette action est irréversible et supprimera en cascade l'ensemble de ses fichiers, questions et rapports.`}
        confirmText="Supprimer définitivement"
        isLoading={isDeletingUser}
        onConfirm={confirmDeleteUser}
        onClose={() => setUserToDelete(null)}
      />
    </div>
  );
}
