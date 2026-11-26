import React, { useState, useRef, useEffect } from 'react';
import { Send, Sparkles, Loader2 } from 'lucide-react';
import { Button } from '../ui/Button';

interface ChatInputProps {
  onSendMessage: (msg: string) => void;
  isLoading: boolean;
  suggestions?: string[];
  onSelectSuggestion?: (sug: string) => void;
  showSuggestions?: boolean;
}

export function ChatInput({
  onSendMessage,
  isLoading,
  suggestions = [],
  onSelectSuggestion,
  showSuggestions = false,
}: ChatInputProps) {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    if (!input.trim() || isLoading) return;
    onSendMessage(input.trim());
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Ajustement automatique de la hauteur du textarea
  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
  };

  return (
    <div className="w-full space-y-3">
      {/* Suggestions cliquables */}
      {showSuggestions && suggestions.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-slate-400 font-medium flex items-center gap-1">
            <Sparkles className="h-3.5 w-3.5 text-cyan-400" /> Suggestions :
          </span>
          {suggestions.map((sug, i) => (
            <button
              key={i}
              onClick={() => onSelectSuggestion?.(sug)}
              disabled={isLoading}
              className="text-xs px-3 py-1.5 rounded-full bg-slate-900/80 hover:bg-slate-850 text-slate-300 hover:text-cyan-300 border border-slate-800 hover:border-cyan-500/40 transition-all duration-150 text-left active:scale-95 disabled:opacity-50"
            >
              {sug}
            </button>
          ))}
        </div>
      )}

      {/* Input Box */}
      <div className="relative flex items-end rounded-2xl border border-slate-800 bg-slate-900/90 p-2 shadow-xl backdrop-blur-xl focus-within:border-cyan-500/50 focus-within:ring-2 focus-within:ring-cyan-500/20 transition-all">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
          rows={1}
          placeholder="Posez une question sur vos données (ex: Quel est le total des ventes ? Affiche un graphique...)"
          className="w-full resize-none bg-transparent px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none max-h-32 disabled:opacity-50"
        />

        <Button
          onClick={handleSend}
          disabled={!input.trim() || isLoading}
          size="sm"
          className="h-10 w-10 shrink-0 p-0 rounded-xl"
          title="Envoyer (Entrée)"
        >
          {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        </Button>
      </div>

      <div className="flex justify-between items-center px-2 text-[11px] text-slate-400">
        <span>Appuyez sur <kbd className="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-300 font-mono text-[10px]">Entrée</kbd> pour envoyer, <kbd className="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-300 font-mono text-[10px]">Maj+Entrée</kbd> pour un saut de ligne</span>
        <span className="hidden sm:inline">Moteur RAG + IA Locale active</span>
      </div>
    </div>
  );
}
