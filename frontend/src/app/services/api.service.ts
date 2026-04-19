import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

export interface AuthMe {
  authenticated: boolean;
  user_id?: number;
  user_name?: string;
  email?: string;
  profile_pic?: string;
}

export interface DashboardConcept {
  id: number;
  title: string;
  icon: string;
  questions_path: string;
}

export interface DashboardPayload {
  user_name: string;
  concepts: DashboardConcept[];
  chart_data: number[];
  total_solved: number;
  retention_pct: number;
  days_label: string;
  days_color: string;
  memory_path: string;
}

export interface ConceptQuestionRow {
  id: number;
  title: string;
  difficulty: string;
  link: string;
  is_solved: boolean;
}

export interface ConceptQuestionsPayload {
  concept: { id: number; title: string; icon: string };
  questions: ConceptQuestionRow[];
}

export interface RetentionQueueItem {
  question_id: number;
  question_title: string;
  question_link: string;
  concept_title: string;
  days_interval: number | null;
}

export interface RetentionStatRow {
  name: string;
  solved: number;
  signal: number;
}

export interface RetentionPayload {
  queue: RetentionQueueItem[];
  stats: RetentionStatRow[];
}

export interface RoadmapConceptRow {
  id: number;
  title: string;
  solved_count: number;
}

export interface ProfileLogRow {
  problem: string;
  concept: string;
  difficulty: string;
  color: string;
  date: string;
}

export interface ProfilePayload {
  user: {
    name: string;
    username: string;
    email: string;
    streak: number;
  };
  logs: ProfileLogRow[];
}

export interface JourneyRow {
  title: string;
  icon: string;
  achieved_at: string | null;
  count: number;
}

export interface MatrixStatRow {
  label: string;
  count: number;
  mastery: number;
  clarity: number;
}

export interface InsightsMatrixPayload {
  status: string;
  matrix_stats: MatrixStatRow[];
  concept_history: Record<
    string,
    { title: string; time: string; autonomy: string }[]
  >;
}

export interface QuestionDetails {
  id: number;
  title: string;
  description: string | null;
  difficulty: string;
  link: string;
  is_solved: boolean;
}

export interface ChatMessageRow {
  role: string;
  content: string;
  thread_id: string;
}

export interface ChatHistoryPayload {
  history: ChatMessageRow[];
}

export interface UserStatsPayload {
  total_solved: number;
  streak: number;
}

export interface ConsistencyPayload {
  score: number;
  active_days: number;
  solves: number;
  reviews: number;
}

@Injectable({
  providedIn: 'root',
})
export class ApiService {
  private readonly http = inject(HttpClient);

  authMe(): Observable<AuthMe> {
    return this.http.get<AuthMe>('/api/v1/auth/me');
  }

  dashboard(): Observable<DashboardPayload> {
    return this.http.get<DashboardPayload>('/api/v1/dashboard');
  }

  retention(): Observable<RetentionPayload> {
    return this.http.get<RetentionPayload>('/api/v1/retention');
  }

  conceptQuestions(conceptId: number): Observable<ConceptQuestionsPayload> {
    return this.http.get<ConceptQuestionsPayload>(
      `/api/v1/concepts/${conceptId}/questions`,
    );
  }

  roadmapData(): Observable<RoadmapConceptRow[]> {
    return this.http.get<RoadmapConceptRow[]>('/api/roadmap-data');
  }

  profile(): Observable<ProfilePayload> {
    return this.http.get<ProfilePayload>('/api/profile');
  }

  userStats(): Observable<UserStatsPayload> {
    return this.http.get<UserStatsPayload>('/api/user_stats');
  }

  consistency(): Observable<ConsistencyPayload> {
    return this.http.get<ConsistencyPayload>('/api/consistency');
  }

  userJourney(): Observable<JourneyRow[]> {
    return this.http.get<JourneyRow[]>('/api/user-journey');
  }

  insightsMatrix(): Observable<InsightsMatrixPayload> {
    return this.http.get<InsightsMatrixPayload>('/api/insights/matrix');
  }

  insightsAiSummary(body: { provider?: string }): Observable<{
    diagnostic?: string;
    predictor?: string;
    error?: string;
  }> {
    return this.http.post('/api/insights/ai-summary', body);
  }

  getQuestionDetails(qId: number): Observable<QuestionDetails> {
    return this.http.get<QuestionDetails>(`/api/get_question_details/${qId}`);
  }

  chatHistory(questionId: number): Observable<ChatHistoryPayload> {
    return this.http.get<ChatHistoryPayload>(`/api/chat_history/${questionId}`);
  }

  askAi(body: {
    question_id: number;
    query: string;
    thread_id: string;
    provider: string | null;
  }): Observable<{ answer?: string; error?: string; message?: string }> {
    return this.http.post('/api/ask_ai', body);
  }

  toggleSolve(body: {
    question_id: number;
    confidence?: number | null;
    time_spent?: number | null;
    provider?: string | null;
  }): Observable<{ status?: string; action?: string; error?: string }> {
    return this.http.post('/api/toggle_solve', body);
  }

  changePassword(body: {
    current_password: string;
    new_password: string;
  }): Observable<{ success?: boolean; message?: string; error?: string }> {
    return this.http.post('/api/change-password', body);
  }

  setApiKey(body: { api_key: string; provider: string }): Observable<{
    status?: string;
    message?: string;
  }> {
    return this.http.post('/api/set-key', body);
  }

  login(username: string, userpass: string): Observable<{ message?: string }> {
    return this.http.post<{ message?: string }>('/login', { username, userpass });
  }
}
