import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../services/auth.services';
import { RoomService } from '../../services/room.services';

@Component({
  selector: 'app-usuario',
  imports: [FormsModule, RouterLink],
  templateUrl: './usuario.html',
  styleUrl: './usuario.css',
})
export class Usuario implements OnInit {

  name = '';
  email = '';
  photoUrl = signal<string | null>(null);

  currentPassword = '';
  newPassword = '';

  // Mensajes de estado por sección.
  nameMsg = signal<string | null>(null);
  photoMsg = signal<string | null>(null);
  passMsg = signal<string | null>(null);
  passError = signal(false);

  saving = signal(false);

  constructor(
    protected authService: AuthService,
    protected roomService: RoomService,
  ) {}

  async ngOnInit() {
    const u = this.authService.user();
    if (!u) return;
    this.name = u.displayName ?? '';
    this.email = u.email ?? '';
    // Trae la foto guardada en el backend.
    try {
      const data = await this.roomService.getUser(u.uid);
      this.photoUrl.set(this.roomService.photoSrc(data?.photoUrl));
    } catch {
      /* el backend puede no estar disponible aún */
    }
  }

  initial(): string {
    return (this.name || this.email || '?').charAt(0).toUpperCase();
  }

  async saveName() {
    const name = this.name.trim();
    if (!name) return;
    this.saving.set(true);
    this.nameMsg.set(null);
    try {
      await this.authService.updateName(name);
      this.nameMsg.set('Nombre actualizado ✓');
    } catch {
      this.nameMsg.set('No se pudo actualizar el nombre');
    } finally {
      this.saving.set(false);
    }
  }

  async onPhotoSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    const u = this.authService.user();
    if (!file || !u) return;

    this.photoMsg.set('Subiendo...');
    try {
      const url = await this.roomService.uploadPhoto(u.uid, file);
      this.photoUrl.set(this.roomService.photoSrc(url));
      this.photoMsg.set('Foto actualizada ✓');
    } catch {
      this.photoMsg.set('No se pudo subir la foto');
    }
  }

  async changePassword() {
    if (!this.currentPassword || this.newPassword.length < 6) {
      this.passError.set(true);
      this.passMsg.set('La nueva contraseña debe tener al menos 6 caracteres.');
      return;
    }
    this.saving.set(true);
    this.passMsg.set(null);
    try {
      await this.authService.changePassword(this.currentPassword, this.newPassword);
      this.passError.set(false);
      this.passMsg.set('Contraseña cambiada ✓');
      this.currentPassword = '';
      this.newPassword = '';
    } catch (err: any) {
      this.passError.set(true);
      this.passMsg.set(this.mapError(err?.code));
    } finally {
      this.saving.set(false);
    }
  }

  private mapError(code?: string): string {
    switch (code) {
      case 'auth/invalid-credential':
      case 'auth/wrong-password':
        return 'La contraseña actual no es correcta.';
      case 'auth/weak-password':
        return 'La nueva contraseña es demasiado débil.';
      default:
        return 'No se pudo cambiar la contraseña.';
    }
  }
}
