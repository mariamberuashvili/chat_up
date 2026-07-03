import { Injectable, signal } from '@angular/core';
import { API_BASE } from '../api.config';

export interface AppUser {
  uid: string;
  email: string;
  displayName: string;
  photoUrl?: string | null;
  online: boolean;
}

export interface PdfInfo {
  id: string;
  filename: string;
}

export interface Room {
  id: string;
  type: 'dm' | 'group';
  name: string;
  members: string[];
  lastMessage?: string;
  lastMessageAt?: number;
  aiEnabled?: boolean;
}

export interface ChatMessage {
  cid: string;          // id de cliente, para deduplicar entre WS y el historial
  roomId: string;
  text: string;
  senderUid: string;
  senderName: string;
  createdAt?: number;
}

@Injectable({
  providedIn: 'root',
})
export class RoomService {
 deleteRoom(roomId: string): Promise<any> {
  return this.post('/rooms/delete', {
    roomId
  });
}

  // Room que la página de usuarios pide abrir al entrar al chat.
  pendingRoom = signal<Room | null>(null);

  // Registra/actualiza al usuario en el backend y lo marca conectado.
  syncUser(user: AppUser): Promise<unknown> {
    return this.post('/users/sync', {
      uid: user.uid,
      email: user.email,
      displayName: user.displayName,
    });
  }

  // Directorio de todos los usuarios (con su presencia).
  getUsers(): Promise<AppUser[]> {
    return this.get('/users');
  }

  // Datos de un usuario concreto.
  getUser(uid: string): Promise<AppUser> {
    return this.get(`/users/${encodeURIComponent(uid)}`);
  }

  // Sube la foto de perfil del usuario y devuelve su URL relativa.
  async uploadPhoto(uid: string, file: File): Promise<string> {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${API_BASE}/users/${encodeURIComponent(uid)}/photo`, {
      method: 'POST',
      body: form,
    });
    if (!res.ok) throw new Error(`POST photo -> ${res.status}`);
    const data = await res.json();
    return data.photoUrl as string;
  }

  // Convierte una ruta relativa de foto (/uploads/..) en URL absoluta.
  photoSrc(url?: string | null): string | null {
    if (!url) return null;
    return url.startsWith('http') ? url : `${API_BASE}${url}`;
  }

  // Rooms a los que pertenece el usuario.
  getMyRooms(uid: string): Promise<Room[]> {
    return this.get(`/rooms?uid=${encodeURIComponent(uid)}`);
  }

  // Abre (o crea si no existe) el DM entre dos usuarios.
  openDm(me: AppUser, other: AppUser): Promise<Room> {
    return this.post('/rooms/dm', { meUid: me.uid, otherUid: other.uid });
  }

  // Crea un grupo nuevo con los miembros indicados (incluye al creador).
  createGroup(name: string, memberUids: string[]): Promise<Room> {
    return this.post('/rooms/group', { name, members: memberUids });
  }

  // Añade miembros a un grupo ya existente. Devuelve la lista de miembros actualizada.
  addGroupMembers(roomId: string, memberUids: string[]): Promise<{ id: string; members: string[] }> {
    return this.post('/rooms/group/members', { roomId, members: memberUids });
  }

  // Saca al usuario del grupo. Devuelve la lista de miembros actualizada.
  leaveGroup(roomId: string, uid: string): Promise<{ id: string; members: string[] }> {
    return this.post('/rooms/group/leave', { roomId, uid });
  }

  // Carga el historial de mensajes de un room (orden cronológico).
  loadMessages(roomId: string): Promise<ChatMessage[]> {
    return this.get(`/rooms/${encodeURIComponent(roomId)}/messages`);
  }

  // Abre (o reutiliza) el chat personal con la IA.
  openAiChat(uid: string): Promise<Room> {
    return this.post('/rooms/ai', { uid });
  }

  // Activa o desactiva la IA en una sala. Devuelve { aiEnabled: boolean }.
  toggleRoomAI(roomId: string): Promise<{ aiEnabled: boolean }> {
    return this.post(`/rooms/${encodeURIComponent(roomId)}/ai-toggle`, {});
  }

  // Sube un PDF al chat de IA y lo indexa para RAG (hasta 3 PDFs por chat).
  async uploadPdf(roomId: string, file: File): Promise<{ ok: boolean; chunks: number; filename: string; totalPdfs: number; maxPdfs: number }> {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${API_BASE}/rooms/${encodeURIComponent(roomId)}/pdf`, {
      method: 'POST',
      body: form,
    });
    if (!res.ok) {
      let detail = `Error ${res.status}`;
      try { detail = (await res.json()).detail ?? detail; } catch {}
      throw new Error(detail);
    }
    return res.json();
  }

  // Lista los PDFs subidos en un chat de IA.
  listPdfs(roomId: string): Promise<{ pdfs: PdfInfo[]; maxPdfs: number }> {
    return this.get(`/rooms/${encodeURIComponent(roomId)}/pdf`);
  }

  // Borra un PDF del chat de IA por su id.
  async deletePdf(roomId: string, docId: string): Promise<{ ok: boolean; pdfs: PdfInfo[] }> {
    const res = await fetch(`${API_BASE}/rooms/${encodeURIComponent(roomId)}/pdf/${encodeURIComponent(docId)}`, {
      method: 'DELETE',
    });
    if (!res.ok) {
      let detail = `Error ${res.status}`;
      try { detail = (await res.json()).detail ?? detail; } catch {}
      throw new Error(detail);
    }
    return res.json();
  }

  // --- Helpers HTTP ---

  private async get(path: string): Promise<any> {
    const res = await fetch(`${API_BASE}${path}`);
    if (!res.ok) throw new Error(`GET ${path} -> ${res.status}`);
    return res.json();
  }

  private async post(path: string, body: unknown): Promise<any> {
    const res = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`POST ${path} -> ${res.status}`);
    return res.json();
  }
}
