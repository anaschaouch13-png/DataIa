import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Bot, User as UserIcon, Copy, Check, Sparkles, AlertTriangle, RefreshCw } from 'lucide-react';
import { PlotlyChart } from './PlotlyChart';
import { cn } from '../../lib/utils';
import type { ChatMessage } from '../../types';
import { toast } from 'sonner';

interface ChatBubbleProps {
  message: ChatMessage;
  onSuggestion?: (texte: string) => void;
}

/** <details>/<summary> (résumé du nettoyage) : le Markdown du serveur les contient en HTML. */
function texteSansDetails(texte: string): { principal: string; details: { titre: string; corps: string }[] } {
  const details: { titre: string; corps: string }[] = [];
  const principal = texte.replace(/<details><summary>([\s\S]*?)<\/summary>([\s\S]*?)<\/details>/g, (_, titre, corps) => {
    details.push({ titre, corps });
    return '';
  });
  return { principal, details };
}

export function ChatBubble({ message, onSuggestion }: ChatBubbleProps) {
  const isUser = message.sender === 'user';
  const [copied, setCopied] = useState(false);

  const copyToClipboard = () => {
    navigator.clipboard.writeText(message.text);
    setCopied(true);
    toast.success('Texte copié dans le presse-papier !');
    setTimeout(() => setCopied(false), 2000);
  };

  const { principal, details } = texteSansDetails(message.text || '');
  // Les liens /telecharger/... sont des fichiers servis par Flask : on les ouvre hors du routeur React
  const composants = {
    a: ({ href, children }: any) => (
      <a href={href} target={href?.startsWith('/telecharger') ? '_self' : '_blank'} rel="noreferrer">{children}</a>
    ),
  };

  return (
    <div className={cn('flex w-full gap-3.5 my-4', isUser ? 'justify-end' : 'justify-start')}>
      {!isUser && (
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 text-white shadow-md mt-1">
          <Bot className="h-5 w-5" />
        </div>
      )}

      <div
        className={cn(
          'relative group max-w-[92%] sm:max-w-[85%] rounded-2xl p-4 sm:p-5 shadow-sm min-w-0',
          isUser
            ? 'bg-gradient-to-r from-cyan-500 to-blue-600 text-white rounded-tr-sm'
            : 'bg-slate-900 text-slate-100 border border-slate-800 rounded-tl-sm'
        )}
      >
        {isUser ? (
          <p className="text-sm font-medium leading-relaxed whitespace-pre-wrap" dir="auto">{message.text}</p>
        ) : (
          <div className="space-y-3 min-w-0">
            {principal.trim() && (
              <div className="markdown" dir="auto">
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={composants}>{principal}</ReactMarkdown>
              </div>
            )}

            {details.map((d, i) => (
              <details key={i} className="markdown">
                <summary>{d.titre}</summary>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{d.corps}</ReactMarkdown>
              </details>
            ))}

            {message.ancienGraphique && (
              <div className="flex flex-wrap items-center gap-2 rounded-xl border border-amber-300 bg-amber-50 p-3 text-xs text-amber-800">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                <span>Graphique de l'ancienne version : ses valeurs avaient été écrites par l'IA, sans calcul vérifié. Il n'est plus affiché.</span>
                {message.question && onSuggestion && (
                  <button
                    onClick={() => onSuggestion(message.question!)}
                    className="ml-auto inline-flex items-center gap-1 rounded-lg border border-amber-400 px-2 py-1 font-semibold hover:bg-amber-100"
                  >
                    <RefreshCw className="h-3 w-3" /> Régénérer avec le nouveau moteur
                  </button>
                )}
              </div>
            )}

            {(message.figures || []).map((figure, i) => (
              <PlotlyChart key={i} figure={figure} />
            ))}

            {message.suggestions && message.suggestions.length > 0 && onSuggestion && (
              <div className="flex flex-wrap gap-2 pt-1">
                {message.suggestions.map((s) => (
                  <button
                    key={s}
                    onClick={() => onSuggestion(s)}
                    className="rounded-full border border-cyan-500/40 bg-cyan-500/5 px-3 py-1 text-xs font-medium text-cyan-700 hover:bg-cyan-500/15 transition"
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}

            <div className="flex items-center justify-between pt-2 border-t border-slate-800 mt-3 text-[11px] text-slate-400">
              <span className="flex items-center gap-1 text-cyan-600 font-medium">
                <Sparkles className="h-3 w-3" /> Analyse DataIA
              </span>
              <button
                onClick={copyToClipboard}
                className="flex items-center gap-1 px-2 py-1 rounded-md hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition"
                title="Copier la réponse"
              >
                {copied ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
                <span>{copied ? 'Copié' : 'Copier'}</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {isUser && (
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-800 text-slate-300 border border-slate-700 mt-1">
          <UserIcon className="h-5 w-5" />
        </div>
      )}
    </div>
  );
}
