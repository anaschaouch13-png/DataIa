import type {
  User, Fichier, DashboardStats, AdminData, AskIaResponse, ModeleSimulateur, ExecutionML, Apercu,
} from '../types';

export class ApiError extends Error {
  status: number;
  data: any;

  constructor(message: string, status: number, data?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

/**
 * Client HTTP centralisé. La session est le cookie Flask-Login (HttpOnly, SameSite=Lax),
 * envoyé automatiquement (credentials: 'include'). Toutes les routes /api/* répondent en JSON.
 */
async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const isAuthRoute = endpoint.includes('/api/login') || endpoint.includes('/api/signup') || endpoint === '/api/me';
  const response = await fetch(endpoint, {
    ...options,
    credentials: 'include',
    headers: {
      ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...options.headers,
    },
  });

  if (response.status === 401) {
    let message = 'Session expirée';
    try {
      message = (await response.json()).message || message;
    } catch { /* pas du JSON */ }
    if (!isAuthRoute) {
      window.dispatchEvent(new CustomEvent('auth:expired', { detail: { message } }));
    }
    throw new ApiError(message, 401);
  }

  const contentType = response.headers.get('content-type') || '';
  if (!response.ok) {
    let message = `Erreur ${response.status}`;
    let data = null;
    try {
      data = await response.json();
      message = data.message || message;
    } catch { /* pas du JSON */ }
    throw new ApiError(message, response.status, data);
  }
  if (contentType.includes('application/pdf')) {
    return (await response.blob()) as unknown as T;
  }
  return response.json();
}

const json = (body: unknown) => JSON.stringify(body);

export const api = {
  // ================== Authentification ==================
  async getMe(): Promise<User> {
    const res = await request<{ status: string; user: User }>('/api/me');
    return res.user;
  },

  async login(credentials: { email: string; password: string }): Promise<User> {
    const res = await request<{ user: User }>('/api/login', { method: 'POST', body: json(credentials) });
    return res.user;
  },

  async signup(data: { nom_utilisateur: string; email: string; password: string; domaine: string }) {
    return request<{ status: string; message: string }>('/api/signup', { method: 'POST', body: json(data) });
  },

  /** Déconnexion en POST (Phase 6 : un lien GET pouvait être déclenché par un autre site). */
  async logout(): Promise<void> {
    try {
      await request('/api/logout', { method: 'POST' });
    } catch (e) {
      console.warn('Déconnexion :', e);
    }
  },

  async getDomaines(): Promise<string[]> {
    return (await request<{ domaines: string[] }>('/api/domaines')).domaines;
  },

  async getProfil(): Promise<any> {
    return (await request<{ profil: any }>('/api/profil')).profil;
  },

  async updateProfil(data: { nom_utilisateur: string; domaine: string }): Promise<any> {
    return (await request<{ profil: any }>('/api/profil', { method: 'PUT', body: json(data) })).profil;
  },

  // ================== Dashboard & fichiers ==================
  async getDashboard(): Promise<{ stats: DashboardStats; recent_files: Fichier[] }> {
    return request('/api/dashboard');
  },

  async getFiles(): Promise<{ fichiers: Fichier[] }> {
    return request('/api/files');
  },

  async uploadFile(file: File): Promise<{ fichier: Fichier; apercu?: Apercu }> {
    const formData = new FormData();
    formData.append('file', file);
    return request('/api/upload', { method: 'POST', body: formData });
  },

  async getApercu(fileId: number): Promise<Apercu> {
    return (await request<{ apercu: Apercu }>(`/api/files/${fileId}/apercu`)).apercu;
  },

  async deleteFile(fileId: number): Promise<void> {
    await request(`/api/files/${fileId}`, { method: 'DELETE' });
  },

  // ================== Chat ==================
  async getChatHistory(fileId: number): Promise<{ fichier: Fichier; historique: any[]; disponible: boolean }> {
    return request(`/api/chat/${fileId}/history`);
  },

  async askIa(fileId: number, question: string): Promise<AskIaResponse> {
    const res = await request<AskIaResponse>('/ask_ia', { method: 'POST', body: json({ file_id: fileId, question }) });
    if (res.status !== 'success') {
      throw new Error(res.message || "Erreur de réponse de l'IA.");
    }
    return res;
  },

  /** Rapport PDF complet d'une conversation (Phase 8). */
  async exportPdf(fileId: number): Promise<Blob> {
    return request<Blob>(`/api/rapport/${fileId}/pdf`, { method: 'POST', body: json({}) });
  },

  // ================== Simulateur what-if ==================
  async getModelesSimulateur(fileId?: number): Promise<{ domaine: string; modeles: ModeleSimulateur[] }> {
    return request(`/api/simulateur/modeles${fileId ? `?file_id=${fileId}` : ''}`);
  },

  async simuler(cle: string, entrees: Record<string, any>, fileId?: number): Promise<any> {
    return (await request<{ resultat: any }>(`/api/simulateur/${cle}`, {
      method: 'POST', body: json({ file_id: fileId, entrees }),
    })).resultat;
  },

  // ================== Données nettoyées ==================
  async getDonneesNettoyees(): Promise<ExecutionML[]> {
    return (await request<{ executions: ExecutionML[] }>('/api/donnees_nettoyees')).executions;
  },

  // ================== Console admin ==================
  async getAdminData(): Promise<AdminData> {
    return request<AdminData>('/api/admin/data');
  },

  async toggleUser(userId: number): Promise<void> {
    await request(`/api/admin/users/${userId}/toggle`, { method: 'POST' });
  },

  async setDomaine(userId: number, domaine: string): Promise<void> {
    await request(`/api/admin/users/${userId}/domaine`, { method: 'PUT', body: json({ domaine }) });
  },

  async deleteUser(userId: number): Promise<void> {
    await request(`/api/admin/users/${userId}`, { method: 'DELETE' });
  },
};
