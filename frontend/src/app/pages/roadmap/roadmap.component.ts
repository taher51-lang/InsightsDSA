import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';

@Component({ selector: 'app-roadmap', standalone: true, imports: [CommonModule, RouterLink], templateUrl: './roadmap.component.html', styleUrl: './roadmap.component.css' })
export class RoadmapComponent implements OnInit {
  concepts: any[] = [];
  constructor(private http: HttpClient) {}
  ngOnInit() {
    this.http.get<any[]>('/api/roadmap-data').subscribe(d => this.concepts = d);
  }
  getProgress(c: any): number { return c.solved_count > 0 ? Math.min(100, c.solved_count * 10) : 0; }
}
