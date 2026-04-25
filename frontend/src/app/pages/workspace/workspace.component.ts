import { Component, OnInit, AfterViewInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { AiKeyService } from '../../core/ai-key.service';
import { marked } from 'marked';
import DOMPurify from 'dompurify';

declare var bootstrap: any;

@Component({
  selector: 'app-workspace',
  standalone: true,
  imports: [CommonModule, RouterLink, FormsModule],
  templateUrl: './workspace.component.html',
  styleUrl: './workspace.component.css',
})
export class WorkspaceComponent implements OnInit, AfterViewInit {
  qId = 0;
  qTitle = 'Loading...';
  qDiff = '--';
  qDesc = '';
  qLink = '#';
  isSolved = false;
  loading = true;
  chatMessages: {role: string; content: string; id?: string}[] = [{role: 'ai', content: '👋 Hi! I\'m your DSA tutor. How can I help you with this problem?'}];
  aiInput = '';
  selectedConf: number | null = null;
  timeSpent = 15;
  currentThreadId: string | null = null;
  showHistoryBanner = false;
  savedHistoryData: any[] = [];

  private solveModal: any;

  constructor(private http: HttpClient, private route: ActivatedRoute, public aiKeyService: AiKeyService) {}

  ngOnInit() {
    this.qId = Number(this.route.snapshot.paramMap.get('qId'));
    this.http.get<any>(`/api/get_question_details/${this.qId}`).subscribe({
      next: data => {
        this.qTitle = data.title;
        this.qDiff = data.difficulty;
        this.qLink = data.link || '#';
        this.isSolved = data.is_solved;
        const desc = data.description || '';
        if (!desc) { this.qDesc = '<span class="text-muted">No description provided.</span>'; }
        else {
          const parts = desc.split(/(?=Example)/i);
          this.qDesc = parts.map((part: string, i: number) =>
            i === 0 ? part : `<div class="mt-4 p-3 bg-light border-start border-primary border-4 rounded">${part}</div>`
          ).join('');
        }
        this.loading = false;
        this.loadChatHistory();
      },
      error: () => { this.qTitle = 'Error Loading'; this.loading = false; }
    });

    // Check if AI gate is open
    this.aiKeyService.gatekeeperCheck();
  }

  ngAfterViewInit() {
    const el = document.getElementById('solveModal');
    if (el) this.solveModal = new bootstrap.Modal(el);
  }

  goBack() { history.back(); }

  onSolveClick() {
    if (!this.isSolved) { this.solveModal?.show(); }
    else {
      if (confirm('Resetting will wipe your SRS streak. History stays safe. Continue?')) {
        this.runToggleSolve({action: 'reset'});
      }
    }
  }

  selectConf(val: number) { this.selectedConf = val; }

  get canSubmitModal(): boolean { return this.selectedConf !== null && this.timeSpent > 0; }

  onModalSubmit() {
    if (!this.canSubmitModal) return;
    this.runToggleSolve({action: 'solve', confidence: this.selectedConf, time_spent: this.timeSpent * 60, provider: this.aiKeyService.provider});
    this.solveModal?.hide();
  }

  private runToggleSolve(payload: any) {
    this.http.post<any>('/api/toggle_solve', {question_id: this.qId, ...payload}).subscribe({
      next: res => { this.isSolved = res.action === 'solved'; },
      error: () => alert('Database sync failed.')
    });
  }

  sendMessage() {
    if (!this.aiKeyService.hasKey) return;
    
    const text = (document.getElementById('ai-input') as HTMLTextAreaElement)?.value?.trim();
    if (!text) return;
    this.chatMessages.push({role: 'user', content: text});
    (document.getElementById('ai-input') as HTMLTextAreaElement).value = '';
    if (!this.currentThreadId) this.currentThreadId = crypto.randomUUID();
    const loaderId = 'loader-' + Date.now();
    this.chatMessages.push({role: 'ai', content: '<div class="spinner-border spinner-border-sm text-primary"></div> Analyzing...', id: loaderId});
    this.scrollChat();
    this.http.post<any>('/api/ask_ai', {question_id: this.qId, query: text, provider: this.aiKeyService.provider, thread_id: this.currentThreadId}).subscribe({
      next: data => {
        const idx = this.chatMessages.findIndex(m => m.id === loaderId);
        if (idx >= 0) this.chatMessages.splice(idx, 1);
        
        // Render Markdown and Sanitize
        const rawHtml = marked.parse(data.answer) as string;
        const parsed = DOMPurify.sanitize(rawHtml);
        
        this.chatMessages.push({role: 'ai', content: parsed});
        this.scrollChat();
      },
      error: (err) => {
        const idx = this.chatMessages.findIndex(m => m.id === loaderId);
        if (idx >= 0) {
           this.chatMessages.splice(idx, 1);
        }
        
        if (err.status === 401 || err.status === 402 || err.status === 429) {
           this.aiKeyService.triggerError(err.status);
        } else {
           this.chatMessages.push({role: 'ai', content: 'Tutor is currently offline.'});
        }
      }
    });
  }

  onKeyPress(e: KeyboardEvent) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.sendMessage(); } }

  private scrollChat() { setTimeout(() => { const el = document.getElementById('chat-flow'); if (el) el.scrollTop = el.scrollHeight; }, 50); }

  private loadChatHistory() {
    this.http.get<any>(`/api/chat_history/${this.qId}`).subscribe({
      next: data => {
        if (data.history?.length > 0) { this.savedHistoryData = data.history; this.showHistoryBanner = true; }
      }
    });
  }

  resumeChat() {
    this.showHistoryBanner = false;
    this.currentThreadId = this.savedHistoryData[0]?.thread_id || crypto.randomUUID();
    this.savedHistoryData.forEach(msg => {
      const uiRole = msg.role === 'assistant' ? 'ai' : 'user';
      let content = msg.content;
      if (uiRole === 'ai') {
        const rawHtml = marked.parse(msg.content) as string;
        content = DOMPurify.sanitize(rawHtml);
      }
      this.chatMessages.push({role: uiRole, content});
    });
    this.scrollChat();
  }

  startFresh() {
    this.showHistoryBanner = false;
    this.currentThreadId = crypto.randomUUID();
  }
}
