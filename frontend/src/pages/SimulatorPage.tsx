import React, { useEffect, useState } from 'react';
import { Calculator } from 'lucide-react';
import { SimulatorPanel } from '../components/simulator/SimulatorPanel';
import { api } from '../lib/api';
import type { Fichier } from '../types';
import { useAuth } from '../hooks/useAuth';

/**
 * Page Simulateur (Phase 6) : le même panneau que dans le chat, avec le choix du fichier.
 * La prévision et les anomalies ont besoin d'un fichier ; le churn (Banque) n'en a pas besoin.
 */
export function SimulatorPage() {
  const { user } = useAuth();
  const [fichiers, setFichiers] = useState<Fichier[]>([]);
  const [fileId, setFileId] = useState<number | undefined>();

  useEffect(() => {
    api.getFiles().then((r) => {
      const dispo = r.fichiers.filter((f) => f.disponible !== false);
      setFichiers(dispo);
      if (dispo.length) setFileId(dispo[0].id_fichier);
    }).catch(() => setFichiers([]));
  }, []);

  return (
    <div className="max-w-3xl mx-auto space-y-5">
      <div>
        <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-50 flex items-center gap-3">
          <Calculator className="h-7 w-7 text-cyan-600" /> Simulateur what-if
        </h2>
        <p className="text-sm text-slate-400 mt-1">
          Modèles proposés pour votre domaine (<strong>{user?.domaine}</strong>). Chaque simulation est enregistrée.
        </p>
      </div>
      <div>
        <label className="block text-xs font-semibold text-slate-300 mb-1">Fichier de référence (prévision, anomalies)</label>
        <select className="w-full rounded-xl border border-slate-700 bg-white px-3 py-2 text-sm"
                value={fileId ?? ''} onChange={(e) => setFileId(e.target.value ? Number(e.target.value) : undefined)}>
          <option value="">— aucun fichier —</option>
          {fichiers.map((f) => <option key={f.id_fichier} value={f.id_fichier}>{f.nom_fichier}</option>)}
        </select>
      </div>
      <div className="min-h-[520px]">
        <SimulatorPanel key={fileId ?? 0} fileId={fileId} />
      </div>
    </div>
  );
}
