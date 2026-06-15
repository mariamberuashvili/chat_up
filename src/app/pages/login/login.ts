import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../services/auth.services';

@Component({
  selector: 'app-login',
  imports: [FormsModule, RouterLink],
  templateUrl: './login.html',
  styleUrl: './login.css',
})
export class Login {

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
      await this.authService.login(this.email, this.password);
      this.router.navigate(['/chat']);
    } catch (err: any) {
      this.error.set(this.mapError(err?.code));
    } finally {
      this.loading.set(false);
    }
  }

  private mapError(code?: string): string {
    switch (code) {
      case 'auth/invalid-email':
        return 'El correo no es válido.';
      case 'auth/user-not-found':
      case 'auth/wrong-password':
      case 'auth/invalid-credential':
        return 'Correo o contraseña incorrectos.';
      default:
        return 'No se pudo iniciar sesión. Inténtalo de nuevo.';
    }
  }
}
