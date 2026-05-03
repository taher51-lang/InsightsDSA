import { Component, OnInit, AfterViewInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { AiKeyService } from '../../core/ai-key.service';
import { Chart, registerables } from 'chart.js';

Chart.register(...registerables);

@Component({ selector: 'app-insights', standalone: true, imports: [CommonModule, RouterLink], templateUrl: './insights.component.html', styleUrl: './insights.component.css' })
export class InsightsComponent implements OnInit {
  matrixStats: any[] = [];
  conceptHistory: any = {};
  conceptKeys: string[] = [];
  
  diagnostic = 'Analyzing your data...';
  predictor = 'Gathering data points...';
  
  loading = true;
  loadingAI = false;
  chartInstance: Chart | null = null;

  constructor(private http: HttpClient, public aiKeyService: AiKeyService) {}

  ngOnInit() {
    this.loading = true;
    this.http.get<any>('/api/insights/matrix').subscribe({
      next: (d) => {
        this.matrixStats = d.matrix_stats || [];
        this.conceptHistory = d.concept_history || {};
        this.conceptKeys = Object.keys(this.conceptHistory);
        this.loading = false;
        
        // Wait for DOM to update with canvas
        setTimeout(() => {
          this.renderRadarChart();
        }, 0);

        this.diagnostic = "Data loaded. Analyzing your recent problem-solving patterns to determine core strengths...";
        this.predictor = "Sufficient data points gathered. Preparing readiness score for Tier-1 tech interviews...";
        
        // Auto-fetch AI summary if key is available
        if (this.aiKeyService.hasKey) {
          this.generateAISummary();
        }
      },
      error: () => {
        this.loading = false;
        this.diagnostic = "Server error loading data.";
        this.predictor = "Server error loading data.";
      }
    });
  }

  getConceptMastery(conceptName: string): number {
    const statData = this.matrixStats.find(s => s.label === conceptName);
    return statData ? statData.mastery : 0;
  }

  getConceptBorderColor(masteryScore: number): string {
    if (masteryScore < 40) return '#dc3545';
    if (masteryScore < 70) return '#ffc107';
    return '#0d6efd';
  }

  getConceptTextColorClass(masteryScore: number): string {
    if (masteryScore < 40) return 'text-danger';
    if (masteryScore < 70) return 'text-warning';
    return 'text-success';
  }

  renderRadarChart() {
    const canvas = document.getElementById('radarChart') as HTMLCanvasElement;
    if (!canvas) return;

    if (this.chartInstance) {
      this.chartInstance.destroy();
    }

    const labels = this.matrixStats.map(s => s.label);
    const masteryData = this.matrixStats.map(s => s.mastery);

    this.chartInstance = new Chart(canvas, {
      type: 'radar',
      data: {
        labels: labels,
        datasets: [{
          label: 'Mastery Score (%)',
          data: masteryData,
          fill: true,
          backgroundColor: 'rgba(102, 126, 234, 0.2)',
          borderColor: 'rgb(102, 126, 234)',
          pointBackgroundColor: 'rgb(102, 126, 234)'
        }]
      },
      options: { 
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } }, 
        scales: { 
          r: { 
            min: 0, 
            max: 100,
            ticks: { stepSize: 20, display: false },
            pointLabels: { font: { size: 13, weight: 'bold' }, color: '#495057' }
          } 
        } 
      }
    });
  }

  generateAISummary() {
    if (!this.aiKeyService.hasKey) {
      this.aiKeyService.openSettings();
      return;
    }
    
    this.loadingAI = true;
    this.http.post<any>('/api/insights/ai-summary', { provider: this.aiKeyService.provider }).subscribe({
      next: d => { 
        this.diagnostic = d.diagnostic; 
        this.predictor = d.predictor; 
        this.loadingAI = false; 
      },
      error: err => { 
        this.loadingAI = false;
        if (err.status === 401 || err.status === 402 || err.status === 429) {
           this.aiKeyService.triggerError(err.status);
        } else {
           this.diagnostic = 'Could not generate summary. Check AI API key.'; 
           this.predictor = 'Predictor unavailable.';
        }
      }
    });
  }
}
