export interface User {
  id: number;
  nom: string;
  email: string;
  role: 'administrateur' | 'utilisateur' | string;
  est_bloque: number;
  domaine: string;
}

export interface Fichier {
  id_fichier: number;
  nom_fichier: string;
  type_fichier: string;
  date_upload: string | null;
  disponible?: boolean;
}

export interface DashboardStats {
  files_count: number;
  questions_count: number;
  modeles_count?: number;
  graphiques_count?: number;
}

/** Figure Plotly complète construite par le serveur (données calculées par pandas). */
export interface PlotlyFigure {
  data: any[];
  layout: Record<string, any>;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'bot';
  text: string;
  date?: string;
  figures?: PlotlyFigure[];
  suggestions?: string[];
  ancienGraphique?: boolean;   // graphique de l'ancienne version (valeurs écrites par le LLM)
  question?: string;           // question d'origine (pour « Régénérer »)
  intent?: string;
}

export interface AskIaResponse {
  status: string;
  answer: string;
  intent?: string;
  suggestions?: string[];
  graphiques?: { id_graphique: number; figure: PlotlyFigure; type: string }[];
  demande_precision?: boolean;
  temps?: Record<string, any>;
  message?: string;
}

export interface AdminUser {
  id_utilisateur: number;
  nom_utilisateur: string;
  email: string;
  role: string;
  domaine: string;
  est_bloque: number;
  nb_questions: number;
  nb_rapports: number;
  nb_modeles: number;
}

export interface AdminReport {
  id_rapport: number;
  id_question: number | null;
  question_texte: string;
  user_name: string;
  date_generation: string;
  chemin_resume: string;
}

export interface AdminData {
  stats: {
    users_count: number;
    reports_count: number;
    questions_count: number;
    modeles_count: number;
  };
  users: AdminUser[];
  reports: AdminReport[];
  domaines: string[];
}

/** Champ d'un formulaire du simulateur (généré par le serveur à partir du modèle). */
export interface ChampSimulateur {
  nom: string;
  type: 'nombre' | 'liste' | 'booleen' | 'curseur';
  libelle?: string;
  options?: string[];
  min?: number;
  max?: number;
  pas?: number;
  defaut?: any;
}

export interface ModeleSimulateur {
  cle: 'forecast' | 'anomaly' | 'churn' | string;
  nom: string;
  besoin_fichier: boolean;
  disponible: boolean;
  raison: string;
  champs: ChampSimulateur[];
}

export interface ExecutionML {
  id_modele: number;
  type: 'prevision' | 'anomalie' | 'churn';
  algorithme: string;
  metrique_mape: number | null;
  metrique_mae: number | null;
  metrique_accuracy: number | null;
  date_execution: string;
  nom_fichier: string | null;
  disponible: boolean;
  liens: { csv: string; xlsx: string; rapport: string };
}

export interface Apercu {
  nb_lignes: number;
  nb_colonnes: number;
  colonnes: { nom: string; type: string; exemple?: string }[];
  lignes: Record<string, any>[];
  questions_suggerees: string[];
  source?: string;
  remarques?: string[];
}
