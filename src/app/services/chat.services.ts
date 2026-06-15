import { Injectable, signal } from '@angular/core';
import { WS_URL } from '../api.config';

export type ConnectionStatus =
  'disconnected' | 'connecting' | 'connected' | 'error';

@Injectable({
  providedIn: 'root'
})
export class ChatService {

  private socket?: WebSocket;

  status = signal<ConnectionStatus>('disconnected');

  // 🟢 NUEVO: eventos globales
  messages = signal<any>([]);

  connect(uid: string, onMessage: (msg: any) => void) {

    if (this.socket && this.socket.readyState <= WebSocket.OPEN) {
      return;
    }

    this.status.set('connecting');

    this.socket = new WebSocket(
      `${WS_URL}/chat?uid=${encodeURIComponent(uid)}`
    );

    this.socket.onopen = () => {
      this.status.set('connected');
    };

    this.socket.onmessage = (event) => {

      const data = JSON.parse(event.data);

      // guardamos eventos globales
      this.messages.update(list => [...list, data]);

      onMessage(data);
    };

    this.socket.onerror = () => {
      this.status.set('error');
    };

    this.socket.onclose = () => {
      this.status.set('disconnected');
    };
  }

  send(data: any) {

    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      return;
    }

    this.socket.send(JSON.stringify(data));
  }

  disconnect() {
    this.socket?.close();
    this.socket = undefined;
  }

  // 🟢 NUEVO: marcar como leído
  markAsRead(roomId: string, uid: string) {
    this.send({
      type: 'read',
      roomId,
      uid
    });
  }

  // 🟢 NUEVO: eliminar chat
  deleteChat(roomId: string, senderUid: string) {
    this.send({
      type: 'delete',
      roomId,
      senderUid
    });
  }
}