import React, { useEffect, useState } from 'react';
import { UserCog, Save } from 'lucide-react';
import { api } from '../lib/api';
import { useAuth } from '../hooks/useAuth';
import { Button } from '../components/ui/Button';
import { toast } from 'sonner';

/** Profil (Phase 2) : nom et domaine d'activité modifiables ; modèles ML du domaine. */
export function ProfilePage() {
  const { refreshUser } = useAuth();
  const [profil, setProfil] = useState<any>(null);
  const [domaines, setDomaines] = useState<string[]>([]);
  const [nom, setNom] = useState('');
  const [domaine, setDomaine] = useState('');
  const [enCours, setEnCours] = useState(false);

  useEffect(() => {
    api.getProfil().then((p) => { setProfil(p); setNom(p.nom_utilisateur); setDomaine(p.domaine); });
    api.getDomaines().then(setDomaines);
  }, []);

  const enregistrer = async (e: React.FormEvent) => {
    e.preventDefault();
    setEnCours(true);
    try {
      const p = await api.updateProfil({ nom_utilisateur: nom.trim(), domaine });
      setProfil(p);
      await refreshUser();
      toast.success('Profil mis à jour.');
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setEnCours(false);
    }
  };

  if (!profil) return <p className="text-sm text-slate-400">Chargement…</p>;
  const champ = 'w-full rounded-xl border border-slate-700 bg-white px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-500/40';

  return (
    <div className="max-w-xl mx-auto space-y-5">
      <h2 className="text-2xl font-bold text-slate-50 flex items-center gap-2"><UserCog className="h-6 w-6 text-cyan-600" /> Mon profil</h2>
      <form onSubmit={enregistrer} className="rounded-2xl border border-slate-800 bg-slate-900 p-6 space-y-4">
        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1">Nom d'utilisateur</label>
          <input className={champ} value={nom} maxLength={50} required onChange={(e) => setNom(e.target.value)} />
        </div>
        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1">Email (identifiant de connexion)</label>
          <input className={`${champ} opacity-70`} value={profil.email} disabled />
        </div>
        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1">Domaine d'activité</label>
          <select className={champ} value={domaine} onChange={(e) => setDomaine(e.target.value)}>
            {domaines.map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>
        <div className="rounded-xl bg-white border border-slate-800 p-3 text-xs text-slate-300">
          <p className="font-semibold mb-1">Modèles disponibles pour « {profil.domaine} » :</p>
          <ul className="list-disc ml-4">{profil.modeles.map((m: any) => <li key={m.cle}>{m.nom}</li>)}</ul>
          <p className="mt-1 text-slate-400">Tous les domaines : prévision du CA et anomalies. Banque : en plus, le churn.</p>
        </div>
        <Button type="submit" isLoading={enCours} icon={<Save className="h-4 w-4" />}>Enregistrer</Button>
      </form>
    </div>
  );
}
