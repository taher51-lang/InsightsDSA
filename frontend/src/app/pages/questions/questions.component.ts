import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';

@Component({
  selector: 'app-questions',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './questions.component.html',
  styleUrl: './questions.component.css',
})
export class QuestionsComponent implements OnInit {
  conceptId = 0;
  questions: any[] = [];
  loading = true;

  constructor(private http: HttpClient, private route: ActivatedRoute) {}

  ngOnInit() {
    this.conceptId = Number(this.route.snapshot.paramMap.get('conceptId'));
    this.http.get<any[]>(`/api/get_questions/${this.conceptId}`).subscribe({
      next: data => { this.questions = data; this.loading = false; },
      error: () => { this.loading = false; }
    });
  }
}
