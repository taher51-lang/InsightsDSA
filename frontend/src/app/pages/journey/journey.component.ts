import { DatePipe } from '@angular/common';
import { Component, inject, OnInit } from '@angular/core';
import { ApiService, JourneyRow } from '../../services/api.service';

@Component({
  selector: 'app-journey',
  standalone: true,
  imports: [DatePipe],
  templateUrl: './journey.component.html',
  styleUrl: './journey.component.css',
})
export class JourneyComponent implements OnInit {
  private readonly api = inject(ApiService);

  rows: JourneyRow[] = [];
  loadError = '';

  ngOnInit(): void {
    this.api.userJourney().subscribe({
      next: (r) => {
        this.rows = r;
      },
      error: (e) => {
        this.loadError =
          e?.error?.error ?? e?.message ?? 'Could not load journey.';
      },
    });
  }
}
