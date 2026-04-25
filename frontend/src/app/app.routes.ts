import { Routes } from '@angular/router';
import { authGuard } from './core/auth.guard';

export const routes: Routes = [
  { path: '', loadComponent: () => import('./pages/landing/landing.component').then(m => m.LandingComponent) },
  { path: 'login', loadComponent: () => import('./pages/auth/auth.component').then(m => m.AuthComponent) },
  { path: 'loginpage', redirectTo: 'login' },
  { path: 'dashboard', canActivate: [authGuard], loadComponent: () => import('./pages/dashboard/dashboard.component').then(m => m.DashboardComponent) },
  { path: 'questions/:conceptId', canActivate: [authGuard], loadComponent: () => import('./pages/questions/questions.component').then(m => m.QuestionsComponent) },
  { path: 'question/:qId', canActivate: [authGuard], loadComponent: () => import('./pages/workspace/workspace.component').then(m => m.WorkspaceComponent) },
  { path: 'memory', canActivate: [authGuard], loadComponent: () => import('./pages/retention/retention.component').then(m => m.RetentionComponent) },
  { path: 'roadmap', canActivate: [authGuard], loadComponent: () => import('./pages/roadmap/roadmap.component').then(m => m.RoadmapComponent) },
  { path: 'resource', canActivate: [authGuard], loadComponent: () => import('./pages/resource/resource.component').then(m => m.ResourceComponent) },
  { path: 'profile', canActivate: [authGuard], loadComponent: () => import('./pages/profile/profile.component').then(m => m.ProfileComponent) },
  { path: 'insights', canActivate: [authGuard], loadComponent: () => import('./pages/insights/insights.component').then(m => m.InsightsComponent) },
  { path: 'journey', canActivate: [authGuard], loadComponent: () => import('./pages/journey/journey.component').then(m => m.JourneyComponent) },
  { path: 'about', loadComponent: () => import('./pages/about/about.component').then(m => m.AboutComponent) },
  { path: '**', redirectTo: '' },
];
