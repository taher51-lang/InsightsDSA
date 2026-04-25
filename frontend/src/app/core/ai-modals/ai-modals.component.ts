import { Component, OnInit, OnDestroy, AfterViewInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subscription } from 'rxjs';
import { AiKeyService } from '../ai-key.service';

declare var bootstrap: any;

@Component({
  selector: 'app-ai-modals',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './ai-modals.component.html',
  styleUrls: ['./ai-modals.component.css']
})
export class AiModalsComponent implements OnInit, OnDestroy, AfterViewInit {
  private subs = new Subscription();

  // Settings Modal State
  provider = 'gemini';
  apiKey = '';
  isSaving = false;

  // Error Modal State
  errorStatus: number = 0;
  errorTitle = 'Action Required';
  errorMessage = 'Something went wrong.';
  errorIconClass = 'bg-danger bg-opacity-10 text-danger';
  errorIconHtml = '<i class="bi bi-shield-lock-fill fs-3"></i>';

  private settingsModal: any;
  private errorModal: any;

  constructor(private aiKeyService: AiKeyService) {}

  ngOnInit() {
    this.provider = this.aiKeyService.provider;

    this.subs.add(this.aiKeyService.showSettings$.subscribe(() => {
      this.provider = this.aiKeyService.provider;
      this.apiKey = '';
      this.settingsModal?.show();
    }));

    this.subs.add(this.aiKeyService.showError$.subscribe(status => {
      this.showErrorModal(status);
    }));
  }

  ngAfterViewInit() {
    const sEl = document.getElementById('aiSettingsModal');
    if (sEl) this.settingsModal = new bootstrap.Modal(sEl);

    const eEl = document.getElementById('aiErrorModal');
    if (eEl) this.errorModal = new bootstrap.Modal(eEl);
  }

  ngOnDestroy() {
    this.subs.unsubscribe();
  }

  get keyPlaceholder(): string {
    return this.provider === 'gemini' ? 'AIzaSy...' : 'sk-proj-...';
  }

  async saveSettings() {
    if (!this.apiKey.trim()) {
      alert('Please enter a valid API key.');
      return;
    }
    this.isSaving = true;
    try {
      await this.aiKeyService.saveKey(this.provider, this.apiKey.trim());
      this.apiKey = '';
      this.settingsModal?.hide();
    } catch (e) {
      console.error(e);
      alert('Could not save key to server. Please try again.');
    } finally {
      this.isSaving = false;
    }
  }

  muteSettings() {
    this.aiKeyService.mute();
    this.settingsModal?.hide();
  }

  private showErrorModal(status: number) {
    this.errorStatus = status;
    if (status === 429) {
      this.errorTitle = 'Limit Reached';
      this.errorMessage = "You're sending requests faster than the AI can process. Please wait a minute before trying again.";
      this.errorIconClass = 'bg-warning bg-opacity-10 text-warning';
      this.errorIconHtml = '<i class="bi bi-clock-history fs-3"></i>';
    } else {
      const isQuota = status === 402;
      this.errorTitle = isQuota ? 'Quota Exhausted' : 'Invalid API Key';
      this.errorMessage = isQuota
        ? 'Your AI provider balance is empty. Please top up or provide a new key.'
        : 'Your API key is invalid or has expired. Please re-configure your engine.';
      this.errorIconClass = 'bg-danger bg-opacity-10 text-danger';
      this.errorIconHtml = '<i class="bi bi-shield-lock-fill fs-3"></i>';
    }
    this.errorModal?.show();
  }

  handleHardReset() {
    this.errorModal?.hide();
    this.aiKeyService.openSettings();
  }
}
