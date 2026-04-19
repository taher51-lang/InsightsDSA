import { Component, inject, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ApiService, RetentionPayload } from '../../services/api.service';

@Component({
  selector: 'app-memory',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './memory.component.html',
  styleUrl: './memory.component.css',
})
export class MemoryComponent implements OnInit {
  private readonly api = inject(ApiService);

  data: RetentionPayload | null = null;
  loadError = '';

  ngOnInit(): void {
    this.api.retention().subscribe({
      next: (d) => {
        this.data = d;
      },
      error: (e) => {
        this.loadError =
          e?.error?.error ?? e?.message ?? 'Could not load retention data.';
      },
    });
  }

  signalLabel(n: number): string {
    if (n >= 4) {
      return 'Strong';
    }
    if (n === 3) {
      return 'Stable';
    }
    if (n === 2) {
      return 'Building';
    }
    if (n === 1) {
      return 'Early';
    }
    return '—';
  }
}
