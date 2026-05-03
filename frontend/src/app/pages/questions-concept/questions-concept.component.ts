import { NgClass } from '@angular/common';
import { Component, inject, OnInit } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import {
  ApiService,
  ConceptQuestionsPayload,
  ConceptQuestionRow,
} from '../../services/api.service';

@Component({
  selector: 'app-questions-concept',
  standalone: true,
  imports: [RouterLink, NgClass],
  templateUrl: './questions-concept.component.html',
  styleUrl: './questions-concept.component.css',
})
export class QuestionsConceptComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly api = inject(ApiService);

  conceptId: number | null = null;
  data: ConceptQuestionsPayload | null = null;
  loadError = '';

  ngOnInit(): void {
    const raw = this.route.snapshot.paramMap.get('conceptId');
    const id = raw ? Number.parseInt(raw, 10) : NaN;
    if (!Number.isFinite(id) || id < 1) {
      this.loadError = 'Invalid concept.';
      return;
    }
    this.conceptId = id;
    this.api.conceptQuestions(id).subscribe({
      next: (d) => {
        this.data = d;
      },
      error: (e) => {
        this.loadError =
          e?.error?.error ?? e?.message ?? 'Could not load problems for this concept.';
      },
    });
  }

  badgeClass(diff: string): string {
    if (diff === 'Easy') {
      return 'bg-success-subtle text-success border border-success';
    }
    if (diff === 'Medium') {
      return 'bg-warning-subtle text-warning-emphasis border border-warning';
    }
    if (diff === 'Hard') {
      return 'bg-danger-subtle text-danger border border-danger';
    }
    return 'bg-secondary-subtle border border-secondary';
  }

  trackById(_i: number, q: ConceptQuestionRow): number {
    return q.id;
  }

  solvedCount(): number {
    if (!this.data) {
      return 0;
    }
    return this.data.questions.filter((q) => q.is_solved).length;
  }
}
