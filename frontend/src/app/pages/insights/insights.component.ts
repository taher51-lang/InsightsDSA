import { KeyValuePipe } from '@angular/common';
import { Component, inject, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  ApiService,
  ConsistencyPayload,
  InsightsMatrixPayload,
} from '../../services/api.service';

@Component({
  selector: 'app-insights',
  standalone: true,
  imports: [KeyValuePipe, FormsModule],
  templateUrl: './insights.component.html',
  styleUrl: './insights.component.css',
})
export class InsightsComponent implements OnInit {
  private readonly api = inject(ApiService);

  matrix: InsightsMatrixPayload | null = null;
  consistency: ConsistencyPayload | null = null;
  loadError = '';
  aiProvider = 'gemini';
  diagnostic = '';
  predictor = '';
  aiBusy = false;
  aiErr = '';

  ngOnInit(): void {
    this.api.insightsMatrix().subscribe({
      next: (m) => {
        this.matrix = m;
      },
      error: (e) => {
        this.loadError =
          e?.error?.error ?? e?.message ?? 'Could not load insights matrix.';
      },
    });
    this.api.consistency().subscribe({
      next: (c) => {
        this.consistency = c;
      },
      error: () => {
        this.consistency = null;
      },
    });
  }

  loadAiSummary(): void {
    this.aiBusy = true;
    this.aiErr = '';
    this.diagnostic = '';
    this.predictor = '';
    this.api.insightsAiSummary({ provider: this.aiProvider }).subscribe({
      next: (r) => {
        this.aiBusy = false;
        this.diagnostic = r.diagnostic ?? '';
        this.predictor = r.predictor ?? '';
      },
      error: (e) => {
        this.aiBusy = false;
        this.aiErr = e?.error?.error ?? e?.message ?? 'AI summary failed.';
      },
    });
  }
}
