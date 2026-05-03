import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { AiKeyService } from '../../core/ai-key.service';

@Component({ selector: 'app-retention', standalone: true, imports: [CommonModule, RouterLink, FormsModule], templateUrl: './retention.component.html', styleUrl: './retention.component.css' })
export class RetentionComponent implements OnInit {
  queue: any[] = [];
  stats: any[] = [];
  loading = true;
  
  currentReviewItem: any = null;
  reviewTimeMinutes: number = 5;
  private reviewModal: any;

  constructor(private http: HttpClient, private aiKeyService: AiKeyService) {}
  
  ngOnInit() {
    this.loadData();
  }

  ngAfterViewInit() {
    const el = document.getElementById('reviewModal');
    // @ts-ignore
    if (el && typeof bootstrap !== 'undefined') this.reviewModal = new bootstrap.Modal(el);
  }

  loadData() {
    this.loading = true;
    this.http.get<any>('/api/v1/retention').subscribe({ 
      next: d => { this.queue = d.queue || []; this.stats = d.stats || []; this.loading = false; }, 
      error: () => this.loading = false 
    });
  }

  openReviewModal(item: any) {
    this.currentReviewItem = item;
    this.reviewTimeMinutes = 5;
    this.reviewModal?.show();
  }

  submitReview(quality: number) {
    if (!this.reviewTimeMinutes || this.reviewTimeMinutes <= 0) {
        alert("Please enter the time spent reviewing this problem.");
        return;
    }

    const payload = {
        question_id: this.currentReviewItem.question_id,
        quality: quality,
        time_spent: this.reviewTimeMinutes * 60,
        provider: this.aiKeyService.provider
    };

    this.http.post<any>('/api/review', payload).subscribe({
      next: (res) => {
        if (res.status === 'success') {
          this.reviewModal?.hide();
          this.loadData();
        }
      },
      error: (err) => {
        console.error("Review Sync Error:", err);
        alert("Failed to save review. Please check your connection.");
      }
    });
  }

  // --- Similar Modal Logic ---
  loadingSimilar: boolean = false;
  similarQuestions: any[] = [];
  private similarModal: any;

  openSimilarModal(item: any) {
    this.similarQuestions = [];
    this.loadingSimilar = true;
    
    if (!this.similarModal) {
      const el = document.getElementById('similarModal');
      // @ts-ignore
      if (el && typeof bootstrap !== 'undefined') this.similarModal = new bootstrap.Modal(el);
    }
    
    this.similarModal?.show();

    this.http.get<any[]>(`/api/get_similar/${item.question_id}`).subscribe({
      next: (data) => {
        this.similarQuestions = data || [];
        this.loadingSimilar = false;
      },
      error: (err) => {
        console.error("Error fetching similar questions:", err);
        this.loadingSimilar = false;
      }
    });
  }

  closeSimilarModal() {
    this.similarModal?.hide();
  }

  getSignalBadge(signal: number): string {
    if (signal >= 4) return 'bg-success';
    if (signal >= 3) return 'bg-primary';
    if (signal >= 2) return 'bg-warning';
    return 'bg-danger';
  }
  getSignalLabel(signal: number): string {
    if (signal >= 4) return 'Strong';
    if (signal >= 3) return 'Good';
    if (signal >= 2) return 'Weak';
    if (signal >= 1) return 'Fading';
    return 'New';
  }
}
