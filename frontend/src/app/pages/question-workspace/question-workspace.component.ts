import { Location } from '@angular/common';
import { Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { ApiService, ChatMessageRow, QuestionDetails } from '../../services/api.service';

@Component({
  selector: 'app-question-workspace',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './question-workspace.component.html',
  styleUrl: './question-workspace.component.css',
})
export class QuestionWorkspaceComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly api = inject(ApiService);
  private readonly location = inject(Location);

  qId: number | null = null;
  detail: QuestionDetails | null = null;
  descParts: string[] = [];
  loadError = '';
  loading = true;

  threadId: string | null = null;
  historyBanner = false;
  chatMessages: { role: 'user' | 'ai'; text: string }[] = [
    { role: 'ai', text: 'Hi! Ask for a hint or walk through the logic.' },
  ];
  chatInput = '';
  chatBusy = false;
  chatErr = '';

  showSolveModal = false;
  solveMinutes = 15;
  solveConfidence: number | null = null;
  solveBusy = false;

  ngOnInit(): void {
    const raw = this.route.snapshot.paramMap.get('qId');
    const id = raw ? Number.parseInt(raw, 10) : NaN;
    if (!Number.isFinite(id) || id < 1) {
      this.loadError = 'Invalid question.';
      this.loading = false;
      return;
    }
    this.qId = id;
    this.api.getQuestionDetails(id).subscribe({
      next: (d) => {
        this.detail = d;
        this.descParts = this.splitDescription(d.description);
        this.loading = false;
        this.loadHistory();
      },
      error: (e) => {
        this.loadError =
          e?.error?.error ?? e?.message ?? 'Could not load this question.';
        this.loading = false;
      },
    });
  }

  private splitDescription(desc: string | null): string[] {
    if (!desc) {
      return ['No description provided.'];
    }
    const parts = desc.split(/(?=Example)/i);
    return parts.length ? parts : [desc];
  }

  private pendingHistory: ChatMessageRow[] | null = null;

  private loadHistory(): void {
    if (!this.qId) {
      return;
    }
    this.api.chatHistory(this.qId).subscribe({
      next: (res) => {
        const h = res.history ?? [];
        if (h.length > 0) {
          this.historyBanner = true;
          this.pendingHistory = h;
        }
      },
      error: () => {},
    });
  }

  resumeHistory(): void {
    const h = this.pendingHistory;
    if (!h?.length) {
      return;
    }
    this.historyBanner = false;
    this.threadId = h[0].thread_id;
    this.chatMessages = [];
    for (const m of h) {
      const role = m.role === 'assistant' || m.role === 'ai' ? 'ai' : 'user';
      this.chatMessages.push({ role, text: m.content });
    }
  }

  startFreshChat(): void {
    this.historyBanner = false;
    this.threadId = crypto.randomUUID();
    this.chatMessages = [
      { role: 'ai', text: 'New thread. What would you like to explore?' },
    ];
  }

  private provider(): string | null {
    return localStorage.getItem('ai_provider');
  }

  sendChat(): void {
    const text = this.chatInput.trim();
    if (!text || !this.qId || this.chatBusy) {
      return;
    }
    if (!this.threadId) {
      this.threadId = crypto.randomUUID();
    }
    this.chatMessages.push({ role: 'user', text });
    this.chatInput = '';
    this.chatBusy = true;
    this.chatErr = '';
    this.api
      .askAi({
        question_id: this.qId,
        query: text,
        thread_id: this.threadId,
        provider: this.provider(),
      })
      .subscribe({
        next: (r) => {
          this.chatBusy = false;
          if (r.answer) {
            this.chatMessages.push({ role: 'ai', text: r.answer });
          } else {
            this.chatMessages.push({
              role: 'ai',
              text: r.error ?? r.message ?? 'No response.',
            });
          }
        },
        error: (e) => {
          this.chatBusy = false;
          const msg =
            e?.error?.message ??
            e?.error?.error ??
            e?.message ??
            'Tutor request failed.';
          this.chatErr = msg;
          this.chatMessages.push({ role: 'ai', text: msg });
        },
      });
  }

  openSolveModal(): void {
    if (!this.detail?.is_solved) {
      this.solveConfidence = null;
      this.solveMinutes = 15;
      this.showSolveModal = true;
    }
  }

  closeSolveModal(): void {
    this.showSolveModal = false;
  }

  setConfidence(v: number): void {
    this.solveConfidence = v;
  }

  submitSolve(): void {
    if (!this.qId || this.solveConfidence === null || this.solveBusy) {
      return;
    }
    const minutes = Number(this.solveMinutes);
    if (!Number.isFinite(minutes) || minutes < 1) {
      return;
    }
    this.solveBusy = true;
    this.api
      .toggleSolve({
        question_id: this.qId,
        confidence: this.solveConfidence,
        time_spent: Math.round(minutes * 60),
        provider: this.provider(),
        thread_id: this.threadId,
      })
      .subscribe({
        next: (r) => {
          this.solveBusy = false;
          if (r.action === 'solved' && this.detail) {
            this.detail = { ...this.detail, is_solved: true };
          }
          this.showSolveModal = false;
        },
        error: () => {
          this.solveBusy = false;
        },
      });
  }

  async resetSolve(): Promise<void> {
    if (!this.qId) {
      return;
    }
    if (!confirm('Reset will wipe SRS progress for this card. Continue?')) {
      return;
    }
    this.api
      .toggleSolve({ question_id: this.qId, thread_id: this.threadId })
      .subscribe({
        next: (r) => {
          if (r.action === 'reset' && this.detail) {
            this.detail = { ...this.detail, is_solved: false };
          }
        },
        error: () => {},
      });
  }

  goBack(): void {
    this.location.back();
  }
}
