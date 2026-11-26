import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import { Dialog } from '../ui/Dialog';
import { Skeleton } from '../ui/Skeleton';
import { FileSpreadsheet, Bot, Trash2, FolderOpen, ArrowRight } from 'lucide-react';
import { formatDate } from '../../lib/utils';
import { api } from '../../lib/api';
import { toast } from 'sonner';
import type { Fichier } from '../../types';

interface RecentFilesTableProps {
  files: Fichier[];
  isLoading: boolean;
  onRefresh: () => void;
  showAllLink?: boolean;
}

export function RecentFilesTable({ files, isLoading, onRefresh, showAllLink = true }: RecentFilesTableProps) {
  const navigate = useNavigate();
  const [fileToDelete, setFileToDelete] = useState<Fichier | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const confirmDelete = async () => {
    if (!fileToDelete) return;
    setIsDeleting(true);
    try {
      await api.deleteFile(fileToDelete.id_fichier);
      toast.success(`Fichier "${fileToDelete.nom_fichier}" supprimé.`);
      setFileToDelete(null);
      onRefresh();
    } catch (err: any) {
      toast.error(err.message || 'Erreur lors de la suppression.');
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <>
      <Card className="border-slate-800/80 bg-slate-900/40 overflow-hidden">
        <div className="p-6 pb-4 flex items-center justify-between border-b border-slate-800/80">
          <div>
            <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
              <FileSpreadsheet className="h-5 w-5 text-cyan-400" />
              Fichiers Récents
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Accédez instantanément à vos jeux de données et lancez l'IA.
            </p>
          </div>
          {showAllLink && files.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate('/files')}
              icon={<ArrowRight className="h-3.5 w-3.5" />}
            >
              Voir tout
            </Button>
          )}
        </div>

        {/* Content */}
        {isLoading ? (
          <div className="p-6 space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex items-center justify-between gap-4 p-3 rounded-xl bg-slate-900/60">
                <div className="flex items-center gap-3 w-1/3">
                  <Skeleton className="h-9 w-9 rounded-lg" />
                  <Skeleton className="h-4 w-40" />
                </div>
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-6 w-16 rounded-full" />
                <div className="flex gap-2">
                  <Skeleton className="h-8 w-20 rounded-lg" />
                  <Skeleton className="h-8 w-8 rounded-lg" />
                </div>
              </div>
            ))}
          </div>
        ) : files.length === 0 ? (
          <div className="p-12 text-center flex flex-col items-center justify-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-800/60 text-slate-400 mb-4 border border-slate-700/40">
              <FolderOpen className="h-7 w-7" />
            </div>
            <h4 className="text-sm font-semibold text-slate-200">Aucun fichier pour le moment</h4>
            <p className="text-xs text-slate-400 max-w-sm mt-1">
              Importez un premier fichier CSV ou Excel ci-dessus pour activer l'analyse intelligente.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-950/50 text-xs font-semibold text-slate-400 uppercase tracking-wider border-b border-slate-800">
                <tr>
                  <th className="py-3 px-6">Nom du fichier</th>
                  <th className="py-3 px-4">Date d'importation</th>
                  <th className="py-3 px-4">Format</th>
                  <th className="py-3 px-6 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {files.map((file) => (
                  <tr
                    key={file.id_fichier}
                    className="hover:bg-slate-800/40 transition-colors duration-150 group"
                  >
                    <td className="py-4 px-6 font-medium text-slate-200 flex items-center gap-3">
                      <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 group-hover:scale-105 transition-transform">
                        <FileSpreadsheet className="h-4 w-4" />
                      </div>
                      <span className="truncate max-w-xs">{file.nom_fichier}</span>
                    </td>
                    <td className="py-4 px-4 text-xs text-slate-400">
                      {formatDate(file.date_upload)}
                    </td>
                    <td className="py-4 px-4">
                      <Badge
                        variant={file.type_fichier?.toLowerCase().includes('csv') ? 'info' : 'success'}
                      >
                        {file.type_fichier || 'Excel'}
                      </Badge>
                    </td>
                    <td className="py-4 px-6 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => navigate(`/chat/${file.id_fichier}`)}
                          icon={<Bot className="h-3.5 w-3.5" />}
                        >
                          Analyser
                        </Button>
                        <Button
                          variant="danger"
                          size="sm"
                          onClick={() => setFileToDelete(file)}
                          className="px-2.5"
                          title="Supprimer le fichier"
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

      {/* Confirmation Dialog */}
      <Dialog
        isOpen={!!fileToDelete}
        title="Supprimer ce fichier ?"
        description={`Êtes-vous sûr de vouloir supprimer définitivement "${fileToDelete?.nom_fichier}" ? Cette action effacera également tout l'historique des analyses et discussions associées.`}
        confirmText="Supprimer définitivement"
        isLoading={isDeleting}
        onConfirm={confirmDelete}
        onClose={() => setFileToDelete(null)}
      />
    </>
  );
}
