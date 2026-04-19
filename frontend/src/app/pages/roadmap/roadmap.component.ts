import { Component, inject, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ApiService, RoadmapConceptRow } from '../../services/api.service';

@Component({
  selector: 'app-roadmap',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './roadmap.component.html',
  styleUrl: './roadmap.component.css',
})
export class RoadmapComponent implements OnInit {
  private readonly api = inject(ApiService);

  rows: RoadmapConceptRow[] = [];
  loadError = '';

  ngOnInit(): void {
    this.api.roadmapData().subscribe({
      next: (r) => {
        this.rows = r;
      },
      error: (e) => {
        this.loadError =
          e?.error?.error ?? e?.message ?? 'Could not load roadmap.';
      },
    });
  }
}
