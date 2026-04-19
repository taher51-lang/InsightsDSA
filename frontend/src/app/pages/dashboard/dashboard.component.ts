import { Component, inject, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ApiService, DashboardPayload } from '../../services/api.service';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css',
})
export class DashboardComponent implements OnInit {
  private readonly api = inject(ApiService);

  data: DashboardPayload | null = null;
  loadError = '';

  ngOnInit(): void {
    this.api.dashboard().subscribe({
      next: (d) => {
        this.data = d;
      },
      error: (e) => {
        this.loadError =
          e?.error?.error ?? e?.message ?? 'Could not load dashboard.';
      },
    });
  }
}
