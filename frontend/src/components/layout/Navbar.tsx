import React from 'react';
import { Menu, Sparkles } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';

interface NavbarProps {
  onOpenMobile: () => void;
  title?: string;
  subtitle?: string;
}

export function Navbar({ onOpenMobile, title = 'Tableau de bord', subtitle }: NavbarProps) {
  const { user } = useAuth();
  // Phase 6 : thème clair unique (fond blanc sur toute la plateforme) -> plus de bascule sombre/clair

  return (
    <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b border-slate-800/80 bg-slate-950/80 px-4 sm:px-6 backdrop-blur-xl">
      <div className="flex items-center gap-3">
        {/* Mobile menu button */}
        <button
          onClick={onOpenMobile}
          className="lg:hidden flex h-9 w-9 items-center justify-center rounded-lg border border-slate-800 text-slate-300 hover:bg-slate-900 transition"
        >
          <Menu className="h-5 w-5" />
        </button>

        <div>
          <h1 className="text-base sm:text-lg font-semibold text-slate-100 flex items-center gap-2">
            {title}
          </h1>
          {subtitle && <p className="text-xs text-slate-400 hidden sm:block">{subtitle}</p>}
        </div>
      </div>

      <div className="flex items-center gap-3">
        {/* User indicator */}
        {user && (
          <div className="hidden sm:flex items-center gap-2.5 pl-3 border-l border-slate-800">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-tr from-cyan-500 to-blue-600 text-white font-bold text-xs shadow-sm">
              {user.nom ? user.nom.charAt(0).toUpperCase() : 'U'}
            </div>
            <div className="flex flex-col text-left">
              <span className="text-xs font-semibold text-slate-200">{user.nom}</span>
              <span className="text-[10px] text-cyan-400 font-medium">{user.role}</span>
            </div>
          </div>
        )}
      </div>
    </header>
  );
}
