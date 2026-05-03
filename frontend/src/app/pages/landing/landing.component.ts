import { Component, inject, OnInit, AfterViewInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'app-landing',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './landing.component.html',
  styleUrl: './landing.component.css',
})
export class LandingComponent implements OnInit, AfterViewInit {
  private readonly auth = inject(AuthService);
  authenticated = false;
  isAdmin = false;

  ngOnInit() {
    this.auth.check().subscribe({
      next: (m) => {
        this.authenticated = !!m.authenticated;
        this.isAdmin = !!m.is_admin;
      },
      error: () => {
        this.authenticated = false;
        this.isAdmin = false;
      }
    });
  }

  ngAfterViewInit() {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) entry.target.classList.add('visible');
      });
    }, { threshold: 0.1 });
    document.querySelectorAll('.animate-on-load').forEach(el => observer.observe(el));
  }
}
