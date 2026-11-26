import React, { useEffect, useState } from 'react';
import { Eraser, Download } from 'lucide-react';
import { api } from '../lib/api';
import type { ExecutionML } from '../types';
import { formatDate } from '../lib/utils';

const LIBELLES: Record<string, string> = { prevision: 'Prévision CA', anomalie: 'Anomalies', churn: 'Churn' };

/**
 * « Mes données nettoyées » (Phase 5.5) : pour chaque exécution d'un modèle, le jeu de données
 * EXACTEMENT passé au modèle (CSV, Excel) et le rapport de nettoyage.
 */
export function CleanedDataPage() {
  const [executions, setExecutions] = useState<ExecutionML[] | null>(null);
  useEffect(() => { api.getDonneesNettoyees().then(setExecutions).catch(() => setExecutions([])); }, []);

  return (
    <div className="max-w-5xl mx-auto space-y-5">
      <div>
        <h2 className="text-2xl font-bold text-slate-50 flex items-center gap-2"><Eraser className="h-6 w-6 text-cyan-600" /> Mes données nettoyées</h2>
        <p className="text-sm text-slate-400 mt-1">Données passées aux modèles ML, téléchargeables avec leur rapport de nettoyage.</p>
      </div>
      {executions === null ? <p className="text-sm text-slate-400">Chargement…</p> : executions.length === 0 ? (
        <p className="rounded-xl border border-slate-800 bg-slate-900 p-4 text-sm text-slate-300">
          Aucune exécution pour l'instant. Dans le chat d'un fichier, demandez « Prévois le chiffre d'affaires » ou « Détecte les anomalies ».
        </p>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-slate-800">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-900 text-left text-xs text-slate-300">
              <tr><th className="p-3">Date</th><th className="p-3">Modèle</th><th className="p-3">Algorithme</th>
                <th className="p-3">Fichier</th><th className="p-3">Métrique</th><th className="p-3 text-right">Téléchargements</th></tr>
            </thead>
            <tbody>
              {executions.map((e) => (
                <tr key={e.id_modele} className="border-t border-slate-800">
                  <td className="p-3 text-xs text-slate-300">{formatDate(e.date_execution)}</td>
                  <td className="p-3"><span className="rounded-md bg-cyan-500/10 px-2 py-0.5 text-xs font-semibold text-cyan-700">{LIBELLES[e.type]}</span></td>
                  <td className="p-3 text-xs text-slate-300">{e.algorithme}</td>
                  <td className="p-3 text-xs text-slate-300">{e.nom_fichier || '(fichier supprimé)'}</td>
                  <td className="p-3 text-xs text-slate-300">
                    {e.metrique_mape != null && `MAPE ${e.metrique_mape.toFixed(2)} %`}
                    {e.metrique_accuracy != null && `Accuracy ${(e.metrique_accuracy * 100).toFixed(1)} %`}
                  </td>
                  <td className="p-3 text-right whitespace-nowrap">
                    {e.disponible ? (['csv', 'xlsx', 'rapport'] as const).map((f) => (
                      <a key={f} href={e.liens[f]}
                         className="ml-1 inline-flex items-center gap-1 rounded-lg border border-slate-700 px-2 py-1 text-xs font-medium text-slate-200 hover:bg-slate-800">
                        <Download className="h-3 w-3" />{f === 'xlsx' ? 'Excel' : f === 'csv' ? 'CSV' : 'Rapport'}
                      </a>
                    )) : <span className="text-xs text-slate-400">fichier absent</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
