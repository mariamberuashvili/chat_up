import { Routes } from '@angular/router';
import { authGuard } from './guards/auth.guard';

export const routes: Routes = [
   {
    path: '',
    redirectTo: 'login',
    pathMatch: 'full'
  },

  {
    path: 'login',
    loadComponent: () =>
      import('./pages/login/login').then(m => m.Login)
  },

  {
    path: 'register',
    loadComponent: () =>
      import('./pages/register/register').then(m => m.Register)
  }, 
  {
    path: 'chat',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./pages/chat/chat').then(m => m.Chat)
  }, 
  {
    path: 'usuario',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./pages/usuario/usuario').then(m => m.Usuario)
  }
];