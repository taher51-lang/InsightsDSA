import { Routes } from '@angular/router';
import { authCanMatch } from './auth.guard';
import { AuthShellComponent } from './layout/auth-shell.component';
import { AboutPageComponent } from './pages/about-page/about-page.component';
import { DashboardComponent } from './pages/dashboard/dashboard.component';
import { HomeComponent } from './pages/home/home.component';
import { InsightsComponent } from './pages/insights/insights.component';
import { JourneyComponent } from './pages/journey/journey.component';
import { LoginComponent } from './pages/login/login.component';
import { MemoryComponent } from './pages/memory/memory.component';
import { ProfileComponent } from './pages/profile/profile.component';
import { QuestionWorkspaceComponent } from './pages/question-workspace/question-workspace.component';
import { QuestionsConceptComponent } from './pages/questions-concept/questions-concept.component';
import { ResourceComponent } from './pages/resource/resource.component';
import { RoadmapComponent } from './pages/roadmap/roadmap.component';

export const routes: Routes = [
  { path: '', pathMatch: 'full', component: HomeComponent },
  { path: 'login', component: LoginComponent },
  { path: 'about', component: AboutPageComponent },
  {
    path: '',
    component: AuthShellComponent,
    canMatch: [authCanMatch],
    children: [
      { path: 'dashboard', component: DashboardComponent },
      { path: 'memory', component: MemoryComponent },
      { path: 'roadmap', component: RoadmapComponent },
      { path: 'resource', component: ResourceComponent },
      { path: 'profile', component: ProfileComponent },
      { path: 'journey', component: JourneyComponent },
      { path: 'insights', component: InsightsComponent },
      { path: 'questions/:conceptId', component: QuestionsConceptComponent },
      { path: 'question/:qId', component: QuestionWorkspaceComponent },
    ],
  },
  { path: '**', redirectTo: '' },
];
