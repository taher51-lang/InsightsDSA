import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-admin',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './admin.component.html',
  styleUrl: './admin.component.css'
})
export class AdminComponent implements OnInit {
  users: any[] = [];
  loading = true;
  error = '';
  
  targetUser: any = null;
  resetSuccess = '';
  resetError = '';

  constructor(private http: HttpClient) {}

  ngOnInit() {
    this.fetchUsers();
  }

  fetchUsers() {
    this.loading = true;
    this.http.get<any[]>('/api/admin/users').subscribe({
      next: (data) => {
        this.users = data;
        this.loading = false;
      },
      error: (err) => {
        this.error = 'Failed to load users. Admin access required.';
        this.loading = false;
      }
    });
  }

  confirmReset(user: any) {
    this.targetUser = user;
    this.resetSuccess = '';
    this.resetError = '';
    // Show modal manually or via data-bs-toggle in HTML
  }

  resetUser() {
    if (!this.targetUser) return;

    this.http.post<any>(`/api/admin/users/${this.targetUser.id}/reset`, {}).subscribe({
      next: (res) => {
        this.resetSuccess = res.message;
        this.fetchUsers();
        setTimeout(() => this.targetUser = null, 2000);
      },
      error: (err) => {
        this.resetError = 'Failed to reset user data.';
      }
    });
  }
}
