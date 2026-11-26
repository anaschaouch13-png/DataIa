import React from 'react';
import { Card } from '../ui/Card';
import { cn } from '../../lib/utils';

interface StatCardProps {
  title: string;
  value: number | string;
  description?: string;
  icon: React.ReactNode;
  trend?: string;
  gradient?: 'cyan' | 'purple' | 'slate';
}

export function StatCard({ title, value, description, icon, trend, gradient = 'cyan' }: StatCardProps) {
  const gradientStyles = {
    cyan: 'from-cyan-500/10 via-blue-500/5 to-transparent border-cyan-500/20 text-cyan-400',
    purple: 'from-purple-500/10 via-indigo-500/5 to-transparent border-purple-500/20 text-purple-400',
    slate: 'from-slate-700/10 via-slate-800/5 to-transparent border-slate-700/30 text-slate-300',
  };

  const iconBgStyles = {
    cyan: 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 shadow-cyan-500/10',
    purple: 'bg-purple-500/10 text-purple-400 border border-purple-500/20 shadow-purple-500/10',
    slate: 'bg-slate-800/50 text-slate-300 border border-slate-700/50 shadow-slate-200/40',
  };

  return (
    <Card
      className={cn(
        'relative overflow-hidden bg-gradient-to-br p-6 transition-all duration-300 hover:translate-y-[-2px] hover:shadow-xl',
        gradientStyles[gradient]
      )}
    >
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">{title}</p>
          <h3 className="mt-2 text-3xl font-bold tracking-tight text-slate-50">{value}</h3>
          {description && <p className="mt-1 text-xs text-slate-400">{description}</p>}
          {trend && (
            <span className="mt-2 inline-flex items-center text-xs font-medium text-emerald-400">
              {trend}
            </span>
          )}
        </div>
        <div className={cn('flex h-12 w-12 items-center justify-center rounded-2xl shadow-lg', iconBgStyles[gradient])}>
          {icon}
        </div>
      </div>
    </Card>
  );
}
