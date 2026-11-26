import React, { useState, useRef } from 'react';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { UploadCloud, FileSpreadsheet, CheckCircle2, AlertCircle, X, Loader2 } from 'lucide-react';
import { api } from '../../lib/api';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

interface FileUploadZoneProps {
  onUploadSuccess: () => void;
}

export function FileUploadZone({ onUploadSuccess }: FileUploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const validateAndSelectFile = (file: File) => {
    // Phase 7 : CSV, Excel (toutes les feuilles), PDF (tableaux + texte) et images (OCR)
    const validExtensions = ['.csv', '.xlsx', '.xls', '.pdf', '.png', '.jpg', '.jpeg'];
    const fileName = file.name.toLowerCase();
    const hasValidExt = validExtensions.some((ext) => fileName.endsWith(ext));

    if (!hasValidExt) {
      toast.error('Format non supporté. Formats acceptés : CSV, Excel, PDF, PNG, JPG.');
      return;
    }

    const maxSizeInBytes = 10 * 1024 * 1024; // 10 Mo
    if (file.size > maxSizeInBytes) {
      toast.error('Le fichier est trop lourd (taille maximale autorisée : 10 Mo).');
      return;
    }

    setSelectedFile(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndSelectFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      validateAndSelectFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    setIsUploading(true);
    setUploadProgress(20);

    // Simulation de progression fluide
    const interval = setInterval(() => {
      setUploadProgress((prev) => {
        if (prev >= 85) {
          clearInterval(interval);
          return 85;
        }
        return prev + 15;
      });
    }, 150);

    try {
      const res = await api.uploadFile(selectedFile);
      setUploadProgress(100);
      toast.success(`Fichier "${selectedFile.name}" importé : aperçu et questions suggérées dans le chat.`);
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      onUploadSuccess();
      // Après l'upload : PAS de graphique ni de prédiction automatique, seulement l'aperçu (Phase 7)
      navigate(`/chat/${res.fichier.id_fichier}`);
    } catch (err: any) {
      toast.error(err.message || "Erreur lors de l'importation du fichier.");
    } finally {
      clearInterval(interval);
      setTimeout(() => {
        setIsUploading(false);
        setUploadProgress(0);
      }, 500);
    }
  };

  return (
    <Card className="p-6 border-slate-800/80 bg-slate-900/40">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
            <UploadCloud className="h-5 w-5 text-cyan-400" />
            Importer un nouveau jeu de données
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            CSV, Excel, PDF ou image (PNG/JPG) : un aperçu et des questions suggérées s'affichent ensuite.
          </p>
        </div>
      </div>

      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !isUploading && fileInputRef.current?.click()}
        className={`relative flex flex-col items-center justify-center p-8 border-2 border-dashed rounded-2xl transition-all duration-200 cursor-pointer ${
          isDragging
            ? 'border-cyan-400 bg-cyan-500/10 scale-[1.01]'
            : 'border-slate-800 hover:border-slate-700 bg-slate-950/40 hover:bg-slate-900/50'
        } ${isUploading ? 'pointer-events-none opacity-80' : ''}`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.xlsx,.xls,.pdf,.png,.jpg,.jpeg"
          onChange={handleFileInputChange}
          className="hidden"
        />

        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 shadow-lg shadow-cyan-500/10 mb-4">
          <FileSpreadsheet className="h-7 w-7" />
        </div>

        <p className="text-sm font-medium text-slate-200 text-center">
          <span className="text-cyan-400 font-semibold underline underline-offset-2">Cliquez pour parcourir</span> ou glissez-déposez votre fichier ici
        </p>
        <p className="text-xs text-slate-500 mt-1.5">Formats acceptés : CSV, XLSX, XLS, PDF, PNG, JPG (max. 10 Mo)</p>

        {/* Selected file preview */}
        {selectedFile && !isUploading && (
          <div
            onClick={(e) => e.stopPropagation()}
            className="mt-5 flex items-center justify-between gap-3 w-full max-w-md rounded-xl bg-slate-800/80 border border-slate-700/60 p-3 shadow-md animate-in fade-in"
          >
            <div className="flex items-center gap-2.5 overflow-hidden">
              <FileSpreadsheet className="h-5 w-5 text-cyan-400 shrink-0" />
              <div className="truncate text-left">
                <p className="text-xs font-semibold text-slate-200 truncate">{selectedFile.name}</p>
                <p className="text-[10px] text-slate-400">
                  {(selectedFile.size / (1024 * 1024)).toFixed(2)} Mo
                </p>
              </div>
            </div>
            <button
              onClick={() => setSelectedFile(null)}
              className="p-1 rounded-lg hover:bg-slate-700 text-slate-400 hover:text-slate-100 transition"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )}

        {/* Progress bar */}
        {isUploading && (
          <div className="w-full max-w-md mt-5 space-y-2">
            <div className="flex justify-between text-xs text-slate-300 font-medium">
              <span className="flex items-center gap-1.5">
                <Loader2 className="h-3.5 w-3.5 animate-spin text-cyan-400" />
                Téléversement et indexation RAG...
              </span>
              <span>{uploadProgress}%</span>
            </div>
            <div className="h-2 w-full rounded-full bg-slate-800 overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 transition-all duration-300 rounded-full"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {selectedFile && !isUploading && (
        <div className="flex justify-end mt-4">
          <Button onClick={handleUpload} isLoading={isUploading} size="md">
            Lancer l'importation
          </Button>
        </div>
      )}
    </Card>
  );
}
