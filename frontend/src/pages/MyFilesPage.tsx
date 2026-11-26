import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Dialog } from '../components/ui/Dialog';
import { Skeleton } from '../components/ui/Skeleton';
import { Input } from '../components/ui/Input';
import {
  FileSpreadsheet,
  Bot,
  Trash2,
  FolderOpen,
  Plus,
  Search,
  Filter,
} from 'lucide-react';
import { formatDate } from '../../src/lib/utils';
import { api } from '../lib/api';
import { toast } from 'sonner';
import type { Fichier } from '../types';

export function MyFilesPage() {
  const navigate = useNavigate();
  const [files, setFiles] = useState<Fichier[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedFormat, setSelectedFormat] = useState<'all' | 'csv' | 'excel'>('all');
  const [fileToDelete, setFileToDelete] = useState<Fichier | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const loadFiles = async () => {
    setIsLoading(true);
    try {
      const data = await api.getFiles();
      setFiles(data.fichiers);
    } catch {
      toast.error('Erreur lors du chargement de la liste des fichiers.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadFiles();
  }, []);

  const confirmDelete = async () => {
    if (!fileToDelete) return;
    setIsDeleting(true);
    try {
      await api.deleteFile(fileToDelete.id_fichier);
      toast.success(`Fichier "${fileToDelete.nom_fichier}" supprimé.`);
      setFileToDelete(null);
      loadFiles();
    } catch (err: any) {
      toast.error(err.message || 'Erreur lors de la suppression.');
    } finally {
      setIsDeleting(false);
    }
  };

  // Filtrage
  const filteredFiles = files.filter((f) => {
    const matchesSearch = f.nom_fichier.toLowerCase().includes(searchQuery.toLowerCase());
    if (!matchesSearch) return false;
    if (selectedFormat === 'csv') return f.type_fichier?.toLowerCase().includes('csv');
    if (selectedFormat === 'excel') return !f.type_fichier?.toLowerCase().includes('csv');
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Header with Title & Action */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-50 flex items-center gap-2.5">
            <FolderOpen className="h-6 w-6 text-cyan-400" />
            Bibliothèque de Données
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Gérez et explorez l'ensemble de vos jeux de données importés sur la plateforme ({files.length} fichier{files.length > 1 ? 's' : ''}).
          </p>
        </div>

        <Button
          onClick={() => navigate('/dashboard')}
          icon={<Plus className="h-4 w-4" />}
          size="md"
        >
          Nouvel Upload
        </Button>
      </div>

      {/* Filter & Search Bar */}
      <Card className="p-4 border-slate-800/80 bg-slate-900/40">
        <div className="flex flex-col sm:flex-row items-center gap-3">
          <div className="w-full sm:flex-1">
            <Input
              placeholder="Rechercher un fichier par son nom..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              icon={<Search className="h-4 w-4" />}
            />
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto">
            <button
              onClick={() => setSelectedFormat('all')}
              className={`text-xs px-3.5 py-2 rounded-xl font-medium transition ${
                selectedFormat === 'all'
                  ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30'
                  : 'bg-slate-800/50 text-slate-400 hover:text-slate-200'
              }`}
            >
              Tous
            </button>
            <button
              onClick={() => setSelectedFormat('excel')}
              className={`text-xs px-3.5 py-2 rounded-xl font-medium transition ${
                selectedFormat === 'excel'
                  ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30'
                  : 'bg-slate-800/50 text-slate-400 hover:text-slate-200'
              }`}
            >
              Excel (.xlsx, .xls)
            </button>
            <button
              onClick={() => setSelectedFormat('csv')}
              className={`text-xs px-3.5 py-2 rounded-xl font-medium transition ${
                selectedFormat === 'csv'
                  ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30'
                  : 'bg-slate-800/50 text-slate-400 hover:text-slate-200'
              }`}
            >
              CSV
            </button>
          </div>
        </div>
      </Card>

      {/* Files Table */}
      <Card className="border-slate-800/80 bg-slate-900/40 overflow-hidden">
        {isLoading ? (
          <div className="p-6 space-y-3">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="flex items-center justify-between gap-4 p-3 rounded-xl bg-slate-900/60">
                <div className="flex items-center gap-3 w-1/3">
                  <Skeleton className="h-9 w-9 rounded-lg" />
                  <Skeleton className="h-4 w-48" />
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
        ) : filteredFiles.length === 0 ? (
          <div className="p-16 text-center flex flex-col items-center justify-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-800/60 text-slate-400 mb-4 border border-slate-700/40">
              <FolderOpen className="h-7 w-7" />
            </div>
            <h4 className="text-sm font-semibold text-slate-200">
              {searchQuery ? 'Aucun fichier ne correspond à votre recherche' : 'Votre bibliothèque est vide'}
            </h4>
            <p className="text-xs text-slate-400 max-w-sm mt-1">
              {searchQuery
                ? 'Essayez avec d’autres mots-clés ou réinitialisez le filtre.'
                : 'Importez votre premier fichier de données pour débuter les analyses.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-950/50 text-xs font-semibold text-slate-400 uppercase tracking-wider border-b border-slate-800">
                <tr>
                  <th className="py-3.5 px-6">Nom du fichier</th>
                  <th className="py-3.5 px-4">Date d'Upload</th>
                  <th className="py-3.5 px-4">Type</th>
                  <th className="py-3.5 px-6 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {filteredFiles.map((file) => (
                  <tr
                    key={file.id_fichier}
                    className="hover:bg-slate-800/40 transition-colors duration-150 group"
                  >
                    <td className="py-4 px-6 font-medium text-slate-200 flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 group-hover:scale-105 transition-transform">
                        <FileSpreadsheet className="h-5 w-5" />
                      </div>
                      <div>
                        <p className="font-semibold text-slate-100">{file.nom_fichier}</p>
                        <p className="text-[11px] text-slate-500">ID Fichier : #{file.id_fichier}</p>
                      </div>
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
                          title="Supprimer ce fichier"
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
        title="Supprimer ce document ?"
        description={`Confirmez-vous la suppression de "${fileToDelete?.nom_fichier}" ? L'ensemble des messages et analyses RAG associées seront supprimés.`}
        confirmText="Supprimer définitivement"
        isLoading={isDeleting}
        onConfirm={confirmDelete}
        onClose={() => setFileToDelete(null)}
      />
    </div>
  );
}
