import { Component, OnInit, AfterViewInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';

declare var Chart: any;

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css',
})
export class DashboardComponent implements OnInit, AfterViewInit {
  userName = '';
  concepts: any[] = [];
  chartData: number[] = [0.5, 0.5, 0.5];
  retentionPct = 0;
  daysLabel = 'Start Now';
  daysColor = 'text-primary';
  totalSolved = 0;
  pulseScore = '--';
  pulseActiveDays = '--';
  pulseReviews = '--';
  pulseBarWidth = '0%';
  pulseBarClass = 'progress-bar bg-dark';

  constructor(private http: HttpClient) {}

  ngOnInit() {
    this.http.get<any>('/api/v1/dashboard').subscribe(data => {
      this.userName = data.user_name || sessionStorage.getItem('name') || '';
      this.concepts = data.concepts || [];
      this.chartData = data.chart_data || [0.5, 0.5, 0.5];
      this.retentionPct = data.retention_pct || 0;
      this.daysLabel = data.days_label || 'Start Now';
      this.daysColor = data.days_color || 'text-primary';
      this.totalSolved = data.total_solved || 0;
      setTimeout(() => this.renderChart(), 100);
    });
    this.http.get<any>('/api/consistency').subscribe(data => {
      if (data.score !== undefined) {
        this.pulseScore = data.score;
        this.pulseActiveDays = data.active_days;
        this.pulseReviews = data.reviews;
        setTimeout(() => {
          this.pulseBarWidth = data.score + '%';
          if (data.score >= 80) this.pulseBarClass = 'progress-bar bg-success';
          else if (data.score >= 50) this.pulseBarClass = 'progress-bar bg-warning';
          else this.pulseBarClass = 'progress-bar bg-danger';
        }, 200);
      }
    });
  }

  ngAfterViewInit() {
    // Initialize tooltips
    const list = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    list.forEach((el: any) => new (window as any).bootstrap.Tooltip(el));
  }

  openRoadmap() {
    window.location.href = '/journey';
  }

  private renderChart() {
    const ctx = (document.getElementById('progressChart') as HTMLCanvasElement)?.getContext('2d');
    if (!ctx) return;
    new Chart(ctx, {
      type: 'bar',
      data: {
        labels: ['Short', 'Medium', 'Long'],
        datasets: [{
          label: 'Questions',
          data: this.chartData,
          backgroundColor: ['#dc3545', '#ffc107', '#198754'],
          borderRadius: 6,
          barThickness: 50
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, grid: { display: false } }, x: { grid: { display: false } } }
      }
    });
  }
}
