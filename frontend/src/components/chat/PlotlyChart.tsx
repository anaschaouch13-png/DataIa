import React, { useEffect, useRef } from 'react';
import type { PlotlyFigure } from '../../types';

/**
 * Affiche une figure Plotly construite par le serveur (Phase 4 : données calculées par pandas).
 * plotly.js est chargé par index.html depuis Flask (/vendor/plotly.min.js, version 3.3.1,
 * identique à celle du serveur) : pas de dépendance npm supplémentaire, fonctionne hors ligne.
 * Remplace l'ancien ChartRenderer (Recharts) qui dessinait des valeurs écrites par le LLM.
 */
export function PlotlyChart({ figure, height = 380 }: { figure: PlotlyFigure; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const Plotly = (window as any).Plotly;
    if (!ref.current || !Plotly || !figure) return;
    const layout = { ...figure.layout, autosize: true, height };
    Plotly.newPlot(ref.current, figure.data, layout, { responsive: true, displaylogo: false });
    const el = ref.current;
    return () => {
      try { Plotly.purge(el); } catch { /* déjà détruit */ }
    };
  }, [figure, height]);

  if (!(window as any).Plotly) {
    return <p className="text-xs text-rose-500">Bibliothèque de graphiques indisponible (plotly.js).</p>;
  }
  return <div ref={ref} className="w-full rounded-xl border border-slate-800 bg-white" style={{ height }} />;
}
