import React from 'react';
import { Table2, Lightbulb } from 'lucide-react';
import type { Apercu } from '../../types';

/**
 * Aperçu d'un fichier après l'upload (Phase 7) : premières lignes, colonnes et types détectés,
 * et 3-4 questions suggérées cliquables. AUCUN graphique ni prédiction automatique.
 */
export function FilePreview({ apercu, onQuestion }: { apercu: Apercu; onQuestion?: (q: string) => void }) {
  const colonnes = apercu.colonnes.map((c) => c.nom);
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900 p-4 mb-4 space-y-3">
      <div className="flex items-center gap-2 text-sm font-bold text-slate-100">
        <Table2 className="h-4 w-4 text-cyan-600" /> Aperçu du fichier
        <span className="text-xs font-normal text-slate-400">
          {apercu.nb_lignes.toLocaleString('fr-FR')} lignes · {apercu.nb_colonnes} colonnes
          {apercu.source ? ` · ${apercu.source}` : ''}
        </span>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {apercu.colonnes.map((c) => (
          <span key={c.nom} className="rounded-md border border-slate-700 bg-white px-2 py-0.5 text-[11px] text-slate-200">
            <strong>{c.nom}</strong> <span className="text-slate-400">· {c.type}</span>
          </span>
        ))}
      </div>

      <div className="overflow-x-auto rounded-lg border border-slate-800">
        <table className="min-w-full text-[11px]">
          <thead className="bg-slate-800">
            <tr>{colonnes.map((c) => <th key={c} className="px-2 py-1.5 text-left font-semibold text-slate-200 whitespace-nowrap">{c}</th>)}</tr>
          </thead>
          <tbody>
            {apercu.lignes.map((l, i) => (
              <tr key={i} className="border-t border-slate-800">
                {colonnes.map((c) => <td key={c} className="px-2 py-1 whitespace-nowrap text-slate-300">{String(l[c] ?? '')}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {apercu.remarques && apercu.remarques.length > 0 && (
        <ul className="text-[11px] text-amber-700 list-disc ml-4">
          {apercu.remarques.map((r) => <li key={r}>{r}</li>)}
        </ul>
      )}

      {apercu.questions_suggerees.length > 0 && (
        <div>
          <p className="flex items-center gap-1 text-xs font-semibold text-slate-300 mb-1.5">
            <Lightbulb className="h-3.5 w-3.5 text-amber-500" /> Questions suggérées
          </p>
          <div className="flex flex-wrap gap-2">
            {apercu.questions_suggerees.map((q) => (
              <button key={q} onClick={() => onQuestion?.(q)}
                      className="rounded-full border border-cyan-500/40 bg-cyan-500/5 px-3 py-1 text-xs font-medium text-cyan-700 hover:bg-cyan-500/15">
                {q}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
