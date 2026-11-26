import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { Card } from '../components/ui/Card';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { BrainCircuit, User, Mail, Lock, Eye, EyeOff, AlertCircle, Briefcase } from 'lucide-react';
import { api } from '../lib/api';
import { toast } from 'sonner';

export function SignupPage() {
  const [nom, setNom] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  // Phase 2 : domaine d'activité (détermine les modèles ML proposés)
  const [domaine, setDomaine] = useState('');
  const [domaines, setDomaines] = useState<string[]>([]);
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const { signup } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    api.getDomaines().then(setDomaines).catch(() => setDomaines([]));
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!nom.trim() || !email.trim() || !password) {
      setErrorMessage('Tous les champs sont obligatoires.');
      return;
    }

    const emailRegex = /^[\w\.-]+@[\w\.-]+\.\w+$/;
    if (!emailRegex.test(email.trim())) {
      setErrorMessage("Veuillez saisir une adresse email valide.");
      return;
    }

    if (!domaine) {
      setErrorMessage("Veuillez choisir votre domaine d'activité.");
      return;
    }

    if (password.length < 6) {
      setErrorMessage('Le mot de passe doit contenir au moins 6 caractères.');
      return;
    }

    setIsLoading(true);
    try {
      await signup({ nom_utilisateur: nom.trim(), email: email.trim(), password, domaine });
      toast.success('Compte créé avec succès ! Connectez-vous.');
      navigate('/login');
    } catch (err: any) {
      setErrorMessage(err.message || "Erreur lors de l'inscription.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center items-center p-4 relative overflow-hidden">
      {/* Background ambient glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[300px] bg-gradient-to-tr from-cyan-500/15 to-blue-600/10 blur-[120px] rounded-full pointer-events-none" />

      <div className="w-full max-w-md relative z-10">
        {/* App Logo */}
        <div className="text-center mb-8">
          <Link to="/" className="inline-flex items-center gap-3 group">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-tr from-cyan-500 to-blue-600 text-white shadow-lg shadow-cyan-500/20 group-hover:scale-105 transition-transform duration-200">
              <BrainCircuit className="h-7 w-7" />
            </div>
            <span className="text-2xl font-bold tracking-tight text-slate-50 flex items-center gap-1">
              DATA<span className="text-cyan-400">IA</span>
            </span>
          </Link>
          <h2 className="text-xl font-bold text-slate-100 mt-4">Créer un compte DataIA</h2>
          <p className="text-xs text-slate-400 mt-1">
            Analysez vos fichiers : calculs exacts, graphiques et modèles de prévision
          </p>
        </div>

        {/* Card Form */}
        <Card className="p-8 border-slate-800/80 bg-slate-900/80 backdrop-blur-2xl shadow-2xl">
          {errorMessage && (
            <div className="mb-6 flex items-center gap-2.5 rounded-xl bg-rose-500/10 border border-rose-500/20 p-3 text-xs font-medium text-rose-400 animate-in fade-in">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Nom complet ou Identifiant"
              type="text"
              placeholder="Ex: Selmane S."
              value={nom}
              onChange={(e) => setNom(e.target.value)}
              icon={<User className="h-4 w-4" />}
              autoComplete="name"
              required
            />

            <Input
              label="Adresse Email"
              type="email"
              placeholder="votre@email.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              icon={<Mail className="h-4 w-4" />}
              autoComplete="email"
              required
            />

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">Domaine d'activité</label>
              <div className="relative">
                <Briefcase className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <select
                  value={domaine}
                  onChange={(e) => setDomaine(e.target.value)}
                  required
                  className="w-full rounded-xl border border-slate-700 bg-white pl-9 pr-3 py-2.5 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-500/40"
                >
                  <option value="" disabled>Choisissez votre domaine…</option>
                  {domaines.map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
              </div>
              <p className="text-[11px] text-slate-400 mt-1">Les modèles d'analyse proposés dépendent de votre domaine (modifiable dans votre profil).</p>
            </div>

            <Input
              label="Mot de passe (6 caractères minimum)"
              type={showPassword ? 'text' : 'password'}
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              icon={<Lock className="h-4 w-4" />}
              autoComplete="new-password"
              required
              rightElement={
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="text-slate-400 hover:text-slate-200 transition"
                  title={showPassword ? 'Masquer' : 'Afficher'}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              }
            />

            <Button
              type="submit"
              size="lg"
              className="w-full mt-2 font-semibold"
              isLoading={isLoading}
            >
              Créer mon compte
            </Button>
          </form>

          <div className="mt-6 text-center text-xs text-slate-400 border-t border-slate-800/80 pt-4">
            Vous possédez déjà un compte ?{' '}
            <Link to="/login" className="text-cyan-400 font-semibold hover:underline">
              Se connecter
            </Link>
          </div>
        </Card>
      </div>
    </div>
  );
}
