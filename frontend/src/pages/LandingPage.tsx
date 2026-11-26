import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import {
  BrainCircuit,
  Sparkles,
  BarChart3,
  FileText,
  ShieldCheck,
  ArrowRight,
  Database,
  Cpu,
  Layers,
  CheckCircle,
} from 'lucide-react';
import { Button } from '../components/ui/Button';

export function LandingPage() {
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-cyan-500/20 selection:text-cyan-300">
      {/* Top Navbar */}
      <header className="sticky top-0 z-40 border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto flex h-20 items-center justify-between px-6">
          <Link to="/" className="flex items-center gap-3 group">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-tr from-cyan-500 to-blue-600 text-white shadow-lg shadow-cyan-500/20 group-hover:scale-105 transition-transform duration-200">
              <BrainCircuit className="h-6 w-6" />
            </div>
            <div className="flex flex-col">
              <span className="text-xl font-bold tracking-tight text-slate-50 flex items-center gap-1">
                DATA<span className="text-cyan-400">IA</span>
              </span>
              <span className="text-[10px] text-slate-400 font-medium tracking-widest uppercase">
                Enterprise Intelligence
              </span>
            </div>
          </Link>

          <div className="flex items-center gap-4">
            {isAuthenticated ? (
              <Button onClick={() => navigate('/dashboard')} size="md" icon={<ArrowRight className="h-4 w-4" />}>
                Accéder au Dashboard
              </Button>
            ) : (
              <>
                <Button
                  variant="ghost"
                  size="md"
                  onClick={() => navigate('/login')}
                  className="text-slate-300 hover:text-slate-50"
                >
                  Se connecter
                </Button>
                <Button
                  variant="primary"
                  size="md"
                  onClick={() => navigate('/signup')}
                  icon={<Sparkles className="h-4 w-4" />}
                >
                  S'inscrire
                </Button>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative overflow-hidden pt-24 pb-20 sm:pt-32 sm:pb-28">
        {/* Glow ambient background */}
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[350px] bg-gradient-to-tr from-cyan-500/20 via-blue-600/15 to-purple-600/10 blur-[130px] rounded-full pointer-events-none" />

        <div className="relative max-w-5xl mx-auto text-center px-6">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 text-xs font-semibold mb-8 animate-in fade-in slide-in-from-top-4 duration-500">
            <Sparkles className="h-3.5 w-3.5" />
            Intelligence Décisionnelle & Moteur RAG Haute Précision
          </div>

          <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight text-slate-100 leading-[1.15]">
            Analyse intelligente de vos fichiers{' '}
            <span className="bg-gradient-to-r from-cyan-400 via-sky-300 to-blue-500 bg-clip-text text-transparent">
              CSV et Excel
            </span>
          </h1>

          <p className="mt-6 text-base sm:text-xl text-slate-400 max-w-3xl mx-auto leading-relaxed">
            Téléversez vos données d'entreprise et dialoguez en langage naturel avec une IA de pointe.
            Obtenez instantanément des synthèses stratégiques, des visualisations graphiques et des rapports PDF professionnels.
          </p>

          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Button
              size="lg"
              onClick={() => navigate(isAuthenticated ? '/dashboard' : '/signup')}
              icon={<ArrowRight className="h-5 w-5" />}
              className="w-full sm:w-auto text-base px-8 py-3.5 shadow-cyan-500/25"
            >
              {isAuthenticated ? 'Ouvrir mon tableau de bord' : 'Commencer gratuitement'}
            </Button>
            <Button
              variant="outline"
              size="lg"
              onClick={() => navigate('/login')}
              className="w-full sm:w-auto text-base px-8 py-3.5"
            >
              Accéder à la démo
            </Button>
          </div>

          {/* Key tags */}
          <div className="mt-12 flex flex-wrap items-center justify-center gap-6 text-xs text-slate-400 font-medium">
            <span className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-emerald-400" /> Sécurité & Confidentialité totale
            </span>
            <span className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-emerald-400" /> RAG local FAISS + Embeddings
            </span>
            <span className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-emerald-400" /> Export PDF automatique
            </span>
          </div>
        </div>
      </section>

      {/* Features Grid */}
      <section className="py-20 border-t border-slate-900 bg-slate-950/60 relative">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-50">
              Une suite complète pour exploiter vos données
            </h2>
            <p className="mt-3 text-sm text-slate-400">
              Des fonctionnalités conçues pour transformer n'importe quel tableau en avantage stratégique.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {/* Feature 1 */}
            <div className="rounded-2xl border border-slate-800/80 bg-slate-900/40 p-6 backdrop-blur-xl hover:border-cyan-500/40 transition-all duration-200 group">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 mb-5 group-hover:scale-110 transition-transform">
                <BrainCircuit className="h-6 w-6" />
              </div>
              <h3 className="text-base font-semibold text-slate-100 mb-2">Chat IA en Langage Naturel</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Posez vos questions en français, anglais ou derja. L'IA lit vos données, détecte les tendances et répond sans jargon.
              </p>
            </div>

            {/* Feature 2 */}
            <div className="rounded-2xl border border-slate-800/80 bg-slate-900/40 p-6 backdrop-blur-xl hover:border-blue-500/40 transition-all duration-200 group">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20 mb-5 group-hover:scale-110 transition-transform">
                <BarChart3 className="h-6 w-6" />
              </div>
              <h3 className="text-base font-semibold text-slate-100 mb-2">Graphiques Automatiques</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Demandez un graphique et admirez des diagrammes interactifs (barres, courbes, camemberts) générés à la volée.
              </p>
            </div>

            {/* Feature 3 */}
            <div className="rounded-2xl border border-slate-800/80 bg-slate-900/40 p-6 backdrop-blur-xl hover:border-purple-500/40 transition-all duration-200 group">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20 mb-5 group-hover:scale-110 transition-transform">
                <FileText className="h-6 w-6" />
              </div>
              <h3 className="text-base font-semibold text-slate-100 mb-2">Export PDF Synthétique</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Téléchargez un rapport officiel professionnel reprenant l'historique des échanges et les recommandations stratégiques.
              </p>
            </div>

            {/* Feature 4 */}
            <div className="rounded-2xl border border-slate-800/80 bg-slate-900/40 p-6 backdrop-blur-xl hover:border-emerald-500/40 transition-all duration-200 group">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 mb-5 group-hover:scale-110 transition-transform">
                <ShieldCheck className="h-6 w-6" />
              </div>
              <h3 className="text-base font-semibold text-slate-100 mb-2">Console d'Administration</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Gouvernance avancée : surveillance de l'activité, gestion des statuts de comptes et consultation de tous les rapports.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* How it works in 3 steps */}
      <section className="py-20 border-t border-slate-900">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <span className="text-xs font-semibold text-cyan-400 uppercase tracking-widest">Workflow Simple</span>
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-50 mt-2">
              Comment ça marche en 3 étapes
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="relative p-6 rounded-2xl bg-slate-900/30 border border-slate-800">
              <span className="text-5xl font-black text-slate-800/80 absolute top-4 right-6">01</span>
              <h3 className="text-base font-bold text-slate-100 mb-2">Importez votre fichier</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Glissez-déposez un fichier CSV ou Excel (ventes, prêts, RH, inventaire). Le système extrait et indexe les données instantanément.
              </p>
            </div>

            <div className="relative p-6 rounded-2xl bg-slate-900/30 border border-slate-800">
              <span className="text-5xl font-black text-slate-800/80 absolute top-4 right-6">02</span>
              <h3 className="text-base font-bold text-slate-100 mb-2">Interrogez l'Assistant</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Posez vos questions métiers dans le chat. Le moteur RAG local recherche les 100 lignes les plus pertinentes et rédige une réponse fiable.
              </p>
            </div>

            <div className="relative p-6 rounded-2xl bg-slate-900/30 border border-slate-800">
              <span className="text-5xl font-black text-slate-800/80 absolute top-4 right-6">03</span>
              <h3 className="text-base font-bold text-slate-100 mb-2">Décidez et Exportez</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Visualisez les graphiques dynamiques et téléchargez un rapport d'analyse complet en PDF en un simple clic.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="mt-auto border-t border-slate-900 py-10 bg-slate-950">
        <div className="max-w-7xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-400">
          <div className="flex items-center gap-2">
            <BrainCircuit className="h-4 w-4 text-cyan-400" />
            <span className="font-semibold text-slate-300">DataIA Platform</span>
            <span>— Projet d'Intégration & PFE</span>
          </div>
          <p>© {new Date().getFullYear()} DataIA. Tous droits réservés.</p>
        </div>
      </footer>
    </div>
  );
}
