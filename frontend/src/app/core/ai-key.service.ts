import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Subject } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class AiKeyService {

  /** Fires to open the AI Settings modal */
  readonly showSettings$ = new Subject<void>();

  /** Fires to open the AI Error modal with an HTTP status code */
  readonly showError$ = new Subject<number>();

  constructor(private http: HttpClient) {}

  // ── localStorage helpers ──────────────────────────────────────

  get hasKey(): boolean {
    return !!localStorage.getItem('ai_api_key');
  }

  get provider(): string {
    return localStorage.getItem('ai_provider') || 'gemini';
  }

  get isMuted(): boolean {
    return localStorage.getItem('mute_api_modal') === 'true';
  }

  mute(): void {
    localStorage.setItem('mute_api_modal', 'true');
  }

  // ── Save key to server + localStorage ─────────────────────────

  /** Sends the real key to the backend (encrypted into Redis),
   *  then writes "PROTECTED_ON_SERVER" to localStorage so the
   *  frontend gate (`hasKey`) still works.
   *  Returns a promise that resolves on success. */
  saveKey(provider: string, apiKey: string): Promise<void> {
    return new Promise((resolve, reject) => {
      this.http.post<any>('/api/set-key', { api_key: apiKey, provider })
        .subscribe({
          next: () => {
            localStorage.setItem('ai_provider', provider);
            localStorage.setItem('ai_api_key', 'PROTECTED_ON_SERVER');
            localStorage.removeItem('mute_api_modal');
            resolve();
          },
          error: err => reject(err)
        });
    });
  }

  // ── Clear key (hard reset on 401/402) ─────────────────────────

  clearKey(): void {
    localStorage.removeItem('ai_api_key');
    localStorage.removeItem('ai_provider');
  }

  // ── Modal triggers ────────────────────────────────────────────

  openSettings(): void {
    this.showSettings$.next();
  }

  /** Trigger the error modal. For 401/402 this also clears
   *  the stored key so the lock overlay reappears. */
  triggerError(status: number): void {
    if (status === 401 || status === 402) {
      this.clearKey();
    }
    this.showError$.next(status);
  }

  // ── Auto-pop gatekeeper (call on page init) ───────────────────

  /** If no key is configured and the user hasn't muted the modal,
   *  automatically open the settings modal. */
  gatekeeperCheck(): void {
    if (!this.hasKey && !this.isMuted) {
      this.openSettings();
    }
  }
}
