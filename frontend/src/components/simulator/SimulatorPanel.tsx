import React, { useEffect, useMemo, useState } from 'react';
import { Calculator, Loader2, TrendingUp, ShieldAlert, Users, Play } from 'lucide-react';
import { api } from '../../lib/api';
import { PlotlyChart } from '../chat/PlotlyChart';
import { cn } from '../../lib/utils';
import type { ChampSimulateur, ModeleSimulateur } from '../../types';
import { toast } from 'sonner';

const ICONES: Record<string, any> = { forecast: TrendingUp, anomaly: ShieldAlert, churn: Users };
const nf = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2 });

/**
 * Panneau « what-if » (Phase 6) : n'affiche QUE les modèles du domaine de l'utilisateur
 * (liste fournie par le serveur depuis services/ml/registry.py). Les formulaires sont
 * générés par le serveur à partir des modèles (features du churn, colonnes du fichier...).
 * Chaque simulation est enregistrée dans la table `simulations`.
 */
export function SimulatorPanel({ fileId }: { fileId?: number }) {
  const [modeles, setModeles] = useState<ModeleSimulateur[]>([]);
  const [domaine, setDomaine] = useState('');
  const [actif, setActif] = useState<string>('');
  const [valeurs, setValeurs] = useState<Record<string, Record<string, any>>>({});
  const [resultats, setResultats] = useState<Record<string, any>>({});
  const [chargement, setChargement] = useState(true);
  const [calcul, setCalcul] = useState(false);

  useEffect(() => {
    setChargement(true);
    api.getModelesSimulateur(fileId)
      .then((r) => {
        setModeles(r.modeles);
        setDomaine(r.domaine);
        setActif((a) => a || r.modeles[0]?.cle || '');
        const init: Record<string, Record<string, any>> = {};
        r.modeles.forEach((m) => {
          init[m.cle] = Object.fromEntries(m.champs.map((c) => [c.nom, c.defaut ?? '']));
        });
        setValeurs(init);
      })
      .catch((e) => toast.error(e.message))
      .finally(() => setChargement(false));
  }, [fileId]);

  const modele = useMemo(() => modeles.find((m) => m.cle === actif), [modeles, actif]);

  const lancer = async () => {
    if (!modele) return;
    setCalcul(true);
    try {
      const r = await api.simuler(modele.cle, valeurs[modele.cle] || {}, fileId);
      setResultats((prev) => ({ ...prev, [modele.cle]: r }));
    } catch (e: any) {
      toast.error(e.message || 'Simulation impossible.');
    } finally {
      setCalcul(false);
    }
  };

  const changer = (champ: string, valeur: any) =>
    setValeurs((v) => ({ ...v, [actif]: { ...(v[actif] || {}), [champ]: valeur } }));

  const champ = (c: ChampSimulateur) => {
    const v = valeurs[actif]?.[c.nom] ?? '';
    const label = <label className="block text-[11px] font-semibold text-slate-300 mb-1">{c.libelle || c.nom}</label>;
    const base = 'w-full rounded-lg border border-slate-700 bg-white px-2.5 py-1.5 text-xs text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-500/40';
    if (c.type === 'liste') {
      return (
        <div key={c.nom}>{label}
          <select className={base} value={v} onChange={(e) => changer(c.nom, e.target.value)}>
            {c.options?.map((o) => <option key={o} value={o}>{o}</option>)}
          </select>
        </div>
      );
    }
    if (c.type === 'booleen') {
      return (
        <div key={c.nom}>{label}
          <select className={base} value={String(Number(v))} onChange={(e) => changer(c.nom, Number(e.target.value))}>
            <option value="1">Oui (1)</option>
            <option value="0">Non (0)</option>
          </select>
        </div>
      );
    }
    if (c.type === 'curseur') {
      return (
        <div key={c.nom}>
          <label className="flex justify-between text-[11px] font-semibold text-slate-300 mb-1">
            <span>{c.libelle || c.nom}</span><span className="text-cyan-600">{v}</span>
          </label>
          <input type="range" min={c.min} max={c.max} step={c.pas} value={v} className="w-full accent-cyan-600"
                 onChange={(e) => changer(c.nom, Number(e.target.value))} />
        </div>
      );
    }
    return (
      <div key={c.nom}>{label}
        <input type="number" className={base} value={v} step={c.pas ?? 'any'} min={c.min} max={c.max}
               onChange={(e) => changer(c.nom, e.target.value === '' ? '' : Number(e.target.value))} />
      </div>
    );
  };

  const resultat = resultats[actif];

  return (
    <div className="flex h-full flex-col rounded-2xl border border-slate-800 bg-slate-900 p-4">
      <div className="flex items-center gap-2 mb-1">
        <Calculator className="h-4 w-4 text-cyan-600" />
        <h3 className="text-sm font-bold text-slate-100">Simulateur what-if</h3>
      </div>
      <p className="text-[11px] text-slate-400 mb-3">Domaine : <strong>{domaine || '…'}</strong> — modèles proposés pour ce domaine</p>

      {chargement ? (
        <div className="flex items-center gap-2 text-xs text-slate-400"><Loader2 className="h-4 w-4 animate-spin" /> Chargement…</div>
      ) : (
        <>
          <div className="flex flex-wrap gap-1.5 mb-3">
            {modeles.map((m) => {
              const Icone = ICONES[m.cle] || Calculator;
              return (
                <button key={m.cle} onClick={() => setActif(m.cle)}
                        className={cn('inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[11px] font-semibold border transition',
                          actif === m.cle ? 'bg-cyan-600 text-white border-cyan-600' : 'border-slate-700 text-slate-300 hover:bg-slate-800')}>
                  <Icone className="h-3.5 w-3.5" />
                  {m.cle === 'forecast' ? 'Prévision CA' : m.cle === 'anomaly' ? 'Anomalies' : 'Churn'}
                </button>
              );
            })}
          </div>

          {modele && !modele.disponible ? (
            <p className="text-xs text-slate-400">{modele.raison}</p>
          ) : modele ? (
            <div className="flex-1 overflow-y-auto pr-1 space-y-3">
              <div className="grid grid-cols-2 gap-2.5">{modele.champs.map(champ)}</div>
              <button onClick={lancer} disabled={calcul}
                      className="w-full inline-flex justify-center items-center gap-2 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 py-2 text-xs font-bold text-white disabled:opacity-60">
                {calcul ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />} Simuler
              </button>

              {resultat && actif === 'forecast' && (
                <div className="space-y-2 rounded-xl border border-slate-800 bg-white p-3">
                  <p className="text-xs text-slate-300">Prochaine période ({resultat.periode_prevue})</p>
                  <p className="text-2xl font-black text-slate-50">{nf.format(resultat.valeur_prevue)}</p>
                  <p className="text-[11px] text-slate-300">
                    Modèle <strong>{resultat.modele}</strong> · Précision <strong>{nf.format(resultat.precision)} %</strong> ({String(resultat.critere).toUpperCase()} = {nf.format(resultat.mape)} %)
                  </p>
                  <PlotlyChart figure={resultat.figure} height={240} />
                </div>
              )}
              {resultat && actif === 'anomaly' && (
                <div className={cn('rounded-xl border p-3 text-xs', resultat.anomalie ? 'border-rose-300 bg-rose-50 text-rose-800' : 'border-emerald-300 bg-emerald-50 text-emerald-800')}>
                  <p className="text-lg font-black">{resultat.verdict}</p>
                  <p>Score {nf.format(resultat.score)} (seuil {nf.format(resultat.seuil)}) — plus inhabituelle que {nf.format(resultat.percentile)} % des transactions du fichier</p>
                  <p className="mt-1 opacity-80">{resultat.raison}</p>
                </div>
              )}
              {resultat && actif === 'churn' && (
                <div className={cn('rounded-xl border p-3 text-xs', resultat.prediction === 'Reste' ? 'border-emerald-300 bg-emerald-50 text-emerald-800' : 'border-rose-300 bg-rose-50 text-rose-800')}>
                  <p className="text-lg font-black">{resultat.prediction}</p>
                  <p>Probabilité de départ : <strong>{nf.format(resultat.pourcentage)} %</strong> (seuil 50 %)</p>
                  <div className="mt-2 h-2 w-full rounded-full bg-slate-800">
                    <div className="h-2 rounded-full bg-gradient-to-r from-emerald-500 to-rose-500" style={{ width: `${resultat.pourcentage}%` }} />
                  </div>
                </div>
              )}
            </div>
          ) : (
            <p className="text-xs text-slate-400">Aucun modèle pour ce domaine.</p>
          )}
        </>
      )}
    </div>
  );
}
