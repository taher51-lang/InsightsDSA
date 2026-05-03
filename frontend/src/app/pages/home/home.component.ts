import { Component, inject, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ApiService } from '../../services/api.service';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './home.component.html',
  styleUrl: './home.component.css',
})
export class HomeComponent implements OnInit {
  private readonly api = inject(ApiService);

  /** When true, primary CTA goes to the app instead of login. */
  authenticated = false;

  ngOnInit(): void {
    this.api.authMe().subscribe({
      next: (m) => {
        this.authenticated = !!m.authenticated;
      },
      error: () => {
        this.authenticated = false;
      },
    });
  }
}
