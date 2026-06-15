import { Injectable, inject, signal } from '@angular/core';
import {
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  signOut,
  onAuthStateChanged,
  updateProfile,
  updatePassword,
  reauthenticateWithCredential,
  EmailAuthProvider,
  User,
} from 'firebase/auth';
import { auth } from '../firebase';
import { RoomService } from './room.services';

@Injectable({
  providedIn: 'root',
})
export class AuthService {

  private roomService = inject(RoomService);

  // Usuario actual (null si no hay sesión). Se actualiza en tiempo real.
  user = signal<User | null>(null);

  // Se resuelve cuando Firebase reporta el estado inicial de sesión.
  // El guard lo espera para no rechazar al usuario antes de tiempo.
  readonly ready: Promise<void>;

  constructor() {
    this.ready = new Promise<void>((resolve) => {
      let first = true;
      onAuthStateChanged(auth, (user) => {
        this.user.set(user);
        if (user) {
          // Registra al usuario en el backend (MySQL) y lo marca conectado.
          // El estado "desconectado" lo gestiona el backend al cerrarse el WebSocket.
          this.roomService.syncUser({
            uid: user.uid,
            email: user.email ?? '',
            displayName: user.displayName ?? user.email ?? 'Usuario',
            online: true,
          }).catch(() => {});
        }
        if (first) {
          first = false;
          resolve();
        }
      });
    });
  }

  // Registra un usuario nuevo con email y contraseña.
  async register(email: string, password: string, displayName?: string) {
    const cred = await createUserWithEmailAndPassword(auth, email, password);
    if (displayName) {
      await updateProfile(cred.user, { displayName });
    }
    return cred.user;
  }

  // Inicia sesión con email y contraseña.
  async login(email: string, password: string) {
    const cred = await signInWithEmailAndPassword(auth, email, password);
    return cred.user;
  }

  // Actualiza el nombre visible y lo re-sincroniza con el backend.
  async updateName(name: string) {
    const u = this.user();
    if (!u) return;
    await updateProfile(u, { displayName: name });
    this.user.set(auth.currentUser);
    await this.roomService.syncUser({
      uid: u.uid,
      email: u.email ?? '',
      displayName: name,
      online: true,
    });
  }

  // Cambia la contraseña. Firebase exige reautenticación reciente,
  // por eso pedimos también la contraseña actual.
  async changePassword(currentPassword: string, newPassword: string) {
    const u = this.user();
    if (!u || !u.email) throw new Error('Sin sesión');
    const cred = EmailAuthProvider.credential(u.email, currentPassword);
    await reauthenticateWithCredential(u, cred);
    await updatePassword(u, newPassword);
  }

  // Cierra la sesión actual.
  async logout() {
    await signOut(auth);
  }

  isLoggedIn() {
    return this.user() !== null;
  }
}
