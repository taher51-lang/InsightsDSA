import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { AiKeyService } from '../../core/ai-key.service';
declare var bootstrap: any;

@Component({ selector: 'app-profile', standalone: true, imports: [CommonModule, RouterLink, FormsModule], templateUrl: './profile.component.html', styleUrl: './profile.component.css' })
export class ProfileComponent implements OnInit {
  user: any = {};
  logs: any[] = [];
  loading = true;
  streak = 0;
  avatarUrl = '';
  currentPassword = '';
  newPassword = '';
  passwordAlert = '';
  passwordAlertClass = '';
  savingPassword = false;
  constructor(private http: HttpClient, public aiKeyService: AiKeyService) {}
  ngOnInit() {
    this.http.get<any>('/api/profile').subscribe({ next: d => {
      this.user = d.user || {};
      this.logs = d.logs || [];
      this.streak = d.user?.streak || 0;
      this.avatarUrl = `https://ui-avatars.com/api/?name=${(this.user.name||'U').replace(' ','+')}&background=0D8ABC&color=fff&rounded=true&size=85`;
      this.loading = false;
    }, error: () => this.loading = false });
  }
  changePassword() {
    if (!this.currentPassword || !this.newPassword) { this.passwordAlert = 'Please fill in both fields.'; this.passwordAlertClass = 'alert alert-danger py-2 mb-3'; return; }
    this.savingPassword = true;
    this.http.post<any>('/api/change-password', { current_password: this.currentPassword, new_password: this.newPassword }).subscribe({
      next: d => { this.passwordAlert = d.message; this.passwordAlertClass = 'alert alert-success py-2 mb-3'; this.currentPassword = ''; this.newPassword = ''; this.savingPassword = false;
        setTimeout(() => { const el = document.getElementById('changePasswordModal'); if (el) bootstrap.Modal.getInstance(el)?.hide(); this.passwordAlert = ''; }, 2000); },
      error: e => { this.passwordAlert = e.error?.error || 'Server error'; this.passwordAlertClass = 'alert alert-danger py-2 mb-3'; this.savingPassword = false; }
    });
  }
}
