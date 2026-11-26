import React, { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import {
  LayoutDashboard,
  FolderKanban,
  Calculator,
  ShieldAlert,
  LogOut,
  BrainCircuit,
  ChevronLeft,
  ChevronRight,
  Menu,
  X,
  Home,
  User as UserIcon,
  Eraser,
  UserCog,
} from 'lucide-react';
import { cn } from '../../lib/utils';
import { Badge } from '../ui/Badge';

interface SidebarProps {
  isMobileOpen: boolean;
  setIsMobileOpen: (open: boolean) => void;
}

export function Sidebar({ isMobileOpen, setIsMobileOpen }: SidebarProps) {
  const { user, isAdmin, logout } = useAuth();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const navLinks: { name: string; path: string; icon: any; end?: boolean; adminOnly?: boolean }[] = [
    { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
    { name: 'Mes Fichiers', path: '/files', icon: FolderKanban },
    { name: 'Simulateur ML', path: '/simulator', icon: Calculator },
    { name: 'Données nettoyées', path: '/donnees', icon: Eraser },
    { name: 'Mon profil', path: '/profil', icon: UserCog },
    ...(isAdmin ? [{ name: 'Admin Console', path: '/admin', icon: ShieldAlert, adminOnly: true }] : []),
  ];

  const content = (
    <div className="flex h-full flex-col justify-between p-4 bg-slate-950/90 border-r border-slate-800/80 backdrop-blur-xl">
      {/* Top Logo & App Title */}
      <div>
        <div className="flex items-center justify-between pb-6 border-b border-slate-800/80">
          <NavLink to="/" className="flex items-center gap-3 group">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 text-white shadow-lg shadow-cyan-500/20 group-hover:scale-105 transition-transform duration-200">
              <BrainCircuit className="h-6 w-6" />
            </div>
            {!isCollapsed && (
              <div className="flex flex-col">
                <span className="text-lg font-bold tracking-tight text-slate-50 flex items-center gap-1.5">
                  DATA<span className="text-cyan-400">IA</span>
                </span>
                <span className="text-[10px] text-slate-400 font-medium tracking-wider uppercase">
                  Intelligent Analytics
                </span>
              </div>
            )}
          </NavLink>

          {/* Desktop Collapse Toggle */}
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="hidden lg:flex h-7 w-7 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-800 hover:text-slate-50 transition"
          >
            {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>

          {/* Mobile Close Button */}
          <button
            onClick={() => setIsMobileOpen(false)}
            className="lg:hidden h-8 w-8 flex items-center justify-center text-slate-400 hover:text-slate-50"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation Items */}
        <nav className="mt-6 space-y-1.5">
          {navLinks.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.end}
                onClick={() => setIsMobileOpen(false)}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3.5 rounded-xl px-3.5 py-2.5 text-sm font-medium transition-all duration-150 group relative',
                    isActive
                      ? 'bg-gradient-to-r from-cyan-500/10 to-blue-500/10 text-cyan-400 border border-cyan-500/20 shadow-sm'
                      : 'text-slate-400 hover:bg-slate-900 hover:text-slate-100',
                    isCollapsed && 'justify-center px-2'
                  )
                }
              >
                <Icon className="h-5 w-5 shrink-0 transition-transform group-hover:scale-110" />
                {!isCollapsed && (
                  <div className="flex items-center justify-between w-full">
                    <span>{item.name}</span>
                    {item.adminOnly && (
                      <Badge variant="danger" className="text-[9px] px-1.5 py-0">
                        Admin
                      </Badge>
                    )}
                  </div>
                )}
              </NavLink>
            );
          })}
        </nav>
      </div>

      {/* Bottom User Area & Logout */}
      <div className="pt-4 border-t border-slate-800/80 space-y-3">
        {user && (
          <div
            className={cn(
              'flex items-center gap-3 rounded-xl p-2.5 bg-slate-900/60 border border-slate-800/60',
              isCollapsed && 'justify-center p-2'
            )}
          >
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-tr from-cyan-500/20 to-blue-500/20 text-cyan-400 border border-cyan-500/30">
              <UserIcon className="h-5 w-5" />
            </div>
            {!isCollapsed && (
              <div className="flex flex-col min-w-0 flex-1">
                <span className="text-xs font-semibold text-slate-200 truncate">{user.nom}</span>
                <span className="text-[11px] text-slate-400 truncate">{user.email}</span>
                <div className="mt-1 flex flex-wrap gap-1">
                  <Badge variant={user.role === 'administrateur' ? 'danger' : 'info'} className="text-[9px] py-0 px-1.5">
                    {user.role}
                  </Badge>
                  <Badge variant="success" className="text-[9px] py-0 px-1.5" title="Domaine d'activité">
                    {user.domaine}
                  </Badge>
                </div>
              </div>
            )}
          </div>
        )}

        <button
          onClick={handleLogout}
          className={cn(
            'flex w-full items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium text-slate-400 hover:bg-rose-500/10 hover:text-rose-400 hover:border-rose-500/20 border border-transparent transition-all duration-150',
            isCollapsed && 'justify-center px-2'
          )}
          title="Se déconnecter (session détruite côté serveur)"
          id="btn-deconnexion"
        >
          <LogOut className="h-5 w-5 shrink-0" />
          {!isCollapsed && <span>Déconnexion</span>}
        </button>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Sidebar */}
      <aside
        className={cn(
          'hidden lg:flex fixed inset-y-0 left-0 z-40 flex-col transition-all duration-300 ease-in-out',
          isCollapsed ? 'w-20' : 'w-64'
        )}
      >
        {content}
      </aside>

      {/* Mobile Drawer */}
      {isMobileOpen && (
        <div className="lg:hidden fixed inset-0 z-50 flex">
          <div
            className="fixed inset-0 bg-slate-50/30 backdrop-blur-sm transition-opacity"
            onClick={() => setIsMobileOpen(false)}
          />
          <div className="relative flex w-72 flex-col z-10 animate-in slide-in-from-left duration-200">
            {content}
          </div>
        </div>
      )}
    </>
  );
}
