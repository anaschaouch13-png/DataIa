import React, { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ChatBubble } from '../components/chat/ChatBubble';
import { ChatInput } from '../components/chat/ChatInput';
import { Button } from '../components/ui/Button';
import { SimulatorPanel } from '../components/simulator/SimulatorPanel';
import { FilePreview } from '../components/dashboard/FilePreview';
import { FileSpreadsheet, ArrowLeft, Download, Loader2, Bot, PanelRightClose, PanelRightOpen, Calculator } from 'lucide-react';
import { api } from '../lib/api';
import { cn } from '../lib/utils';
import type { Fichier, ChatMessage, Apercu } from '../types';
import { toast } from 'sonner';

const SUGGESTIONS_PAR_DEFAUT = [
  'Quel est le total des ventes ?',
  'Affiche un graphique des ventes par mois',
  'Détecte les anomalies',
  "Prévois le chiffre d'affaires des 6 prochains mois",
];

export function ChatPage() {
  const { fileId } = useParams<{ fileId: string }>();
  const navigate = useNavigate();
  const id = Number(fileId);

  const [fichier, setFichier] = useState<Fichier | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [apercu, setApercu] = useState<Apercu | null>(null);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [isAskingAi, setIsAskingAi] = useState(false);
  const [isExportingPdf, setIsExportingPdf] = useState(false);
  // Simulateur : ouvert sur grand écran, replié par défaut sur petit écran
  const [panneauOuvert, setPanneauOuvert] = useState(() => window.innerWidth >= 1280);
  const finRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    finRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isAskingAi]);

  useEffect(() => {
    if (!id) return;
    setIsLoadingHistory(true);
    api.getChatHistory(id)
      .then((data) => {
        setFichier(data.fichier);
        const charges: ChatMessage[] = [];
        data.historique.forEach((h: any) => {
          charges.push({ id: `q-${h.id_question}`, sender: 'user', text: h.question_texte, date: h.date_question });
          charges.push({
            id: `a-${h.id_question}`, sender: 'bot', text: h.reponse_texte || '', figures: h.figures,
            ancienGraphique: h.ancien_graphique, question: h.question_texte, date: h.date_question,
          });
        });
        setMessages(charges);
        if (!data.disponible) toast.warning("Le fichier n'existe plus sur le serveur : réimportez-le pour poser des questions.");
      })
      .catch((err) => {
        toast.error(err.message || 'Impossible de charger le chat.');
        navigate('/files');
      })
      .finally(() => setIsLoadingHistory(false));
    // Phase 7 : aperçu du fichier + questions suggérées adaptées au fichier et au domaine
    api.getApercu(id).then(setApercu).catch(() => setApercu(null));
  }, [id, navigate]);

  const envoyer = async (question: string) => {
    if (!id || !question.trim() || isAskingAi) return;
    const avec: ChatMessage[] = [...messages, { id: `u-${Date.now()}`, sender: 'user', text: question }];
    setMessages(avec);
    setIsAskingAi(true);
    try {
      const r = await api.askIa(id, question);
      setMessages([...avec, {
        id: `b-${Date.now()}`, sender: 'bot', text: r.answer, intent: r.intent,
        figures: (r.graphiques || []).map((g) => g.figure), suggestions: r.suggestions,
      }]);
    } catch (err: any) {
      setMessages([...avec, { id: `e-${Date.now()}`, sender: 'bot', text: `⚠️ ${err.message || "Erreur de communication avec l'IA."}` }]);
    } finally {
      setIsAskingAi(false);
    }
  };

  const exporterPdf = async () => {
    if (messages.length === 0) {
      toast.error('Aucun échange à exporter pour le moment.');
      return;
    }
    setIsExportingPdf(true);
    try {
      const blob = await api.exportPdf(id);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Rapport_DataIA_${fichier?.nom_fichier || 'analyse'}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success('Rapport PDF téléchargé.');
    } catch (err: any) {
      toast.error(err.message || 'Erreur lors de la génération du PDF.');
    } finally {
      setIsExportingPdf(false);
    }
  };

  const suggestions = apercu?.questions_suggerees?.length ? apercu.questions_suggerees : SUGGESTIONS_PAR_DEFAUT;

  return (
    <div className="flex gap-4 h-[calc(100vh-6.5rem)]">
      {/* ---------- Colonne chat ---------- */}
      <div className="flex flex-col flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2 pb-4 border-b border-slate-800">
          <div className="flex items-center gap-3 min-w-0">
            <Button variant="ghost" size="sm" onClick={() => navigate('/files')} className="px-2" title="Retour à mes fichiers">
              <ArrowLeft className="h-4 w-4" />
            </Button>
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-cyan-500/10 text-cyan-600 border border-cyan-500/20">
              <FileSpreadsheet className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <h2 className="text-sm sm:text-base font-bold text-slate-100 truncate">
                Analyse de : <span className="text-cyan-600">{fichier?.nom_fichier || 'Chargement…'}</span>
              </h2>
              <p className="text-[11px] text-slate-400">Format : {fichier?.type_fichier || '—'} · calculs par pandas · IA locale</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" onClick={exporterPdf} isLoading={isExportingPdf}
                    icon={<Download className="h-3.5 w-3.5" />}>
              Export PDF
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setPanneauOuvert(!panneauOuvert)}
                    title={panneauOuvert ? 'Replier le simulateur' : 'Ouvrir le simulateur'}
                    icon={panneauOuvert ? <PanelRightClose className="h-4 w-4" /> : <PanelRightOpen className="h-4 w-4" />}>
              <span className="hidden sm:inline">Simulateur</span>
            </Button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto py-4 px-1">
          {apercu && messages.length === 0 && <FilePreview apercu={apercu} onQuestion={envoyer} />}
          {isLoadingHistory ? (
            <div className="flex flex-col items-center justify-center h-64 text-slate-400 gap-3">
              <Loader2 className="h-6 w-6 animate-spin text-cyan-600" />
              <p className="text-xs font-medium">Chargement de l'historique…</p>
            </div>
          ) : messages.length === 0 && !apercu ? (
            <div className="flex flex-col items-center justify-center py-16 text-center max-w-md mx-auto">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-cyan-500/10 text-cyan-600 border border-cyan-500/20 mb-4">
                <Bot className="h-8 w-8" />
              </div>
              <h3 className="text-base font-bold text-slate-100">Prêt à analyser « {fichier?.nom_fichier} »</h3>
              <p className="text-xs text-slate-400 mt-2">
                Totaux, moyennes, classements, graphiques, prévisions, anomalies… en français, anglais, arabe ou derja.
              </p>
            </div>
          ) : (
            messages.map((m) => <ChatBubble key={m.id} message={m} onSuggestion={envoyer} />)
          )}
          {isAskingAi && (
            <div className="flex items-center gap-3 text-cyan-600 text-xs font-medium my-4 animate-pulse">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Analyse en cours…</span>
            </div>
          )}
          <div ref={finRef} />
        </div>

        <div className="pt-2">
          <ChatInput onSendMessage={envoyer} isLoading={isAskingAi} suggestions={suggestions}
                     onSelectSuggestion={envoyer} showSuggestions={messages.length <= 2} />
        </div>
      </div>

      {/* ---------- Panneau simulateur (à droite, repliable) ---------- */}
      {panneauOuvert && (
        <>
          {/* Petit écran : tiroir par-dessus le chat */}
          <div className="xl:hidden fixed inset-0 z-40 bg-slate-50/20" onClick={() => setPanneauOuvert(false)} />
          <aside className={cn('w-[22rem] max-w-[92vw] shrink-0',
            'fixed right-2 top-20 bottom-2 z-50 xl:static xl:z-auto shadow-xl xl:shadow-none')}>
            <SimulatorPanel fileId={id} />
          </aside>
        </>
      )}
      {!panneauOuvert && (
        <button onClick={() => setPanneauOuvert(true)}
                className="xl:hidden fixed bottom-36 right-4 z-30 flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-lg"
                title="Ouvrir le simulateur">
          <Calculator className="h-5 w-5" />
        </button>
      )}
    </div>
  );
}
