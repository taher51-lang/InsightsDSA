import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';

@Component({ selector: 'app-journey', standalone: true, imports: [CommonModule, RouterLink], templateUrl: './journey.component.html', styleUrl: './journey.component.css' })
export class JourneyComponent implements OnInit {
  milestones: any[] = [];
  constructor(private http: HttpClient) {}
  ngOnInit() { this.http.get<any[]>('/api/user-journey').subscribe(d => this.milestones = d); }
}
