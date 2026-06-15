import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../services/auth.services';

@Component({
  selector: 'app-register',
  imports: [FormsModule, RouterLink],
  templateUrl: './register.html',
  styleUrl: './register.css',
})
export class Register {

  name = '';
  email = '';
  password = '';

  error = signal<string | null>(null);
  loading = signal(false);

  constructor(
    private authService: AuthService,
    private router: Router,
  ) {}

  async onSubmit() {
    this.error.set(null);
    this.loading.set(true);

    try {
      await this.authService.register(this.email, this.password, this.name);
      this.router.navigate(['/chat']);
    } catch (err: any) {
      this.error.set(this.mapError(err?.code));
    } finally {
      this.loading.set(false);
    }
  }

  private mapError(code?: string): string {
    switch (code) {
      case 'auth/email-already-in-use':
        return 'Ese correo ya está registrado.';
      case 'auth/invalid-email':
        return 'El correo no es válido.';
      case 'auth/weak-password':
        return 'La contraseña debe tener al menos 6 caracteres.';
      default:
        return 'No se pudo crear la cuenta. Inténtalo de nuevo.';
    }
  }
}
