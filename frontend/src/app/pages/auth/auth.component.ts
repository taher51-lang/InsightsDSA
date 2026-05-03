import { Component } from '@angular/core';
import { Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-auth',
  standalone: true,
  imports: [FormsModule, CommonModule],
  templateUrl: './auth.component.html',
  styleUrl: './auth.component.css',
})
export class AuthComponent {
  rightPanelActive = false;
  // Login fields
  loginUsername = '';
  loginPassword = '';
  // Register fields
  regName = '';
  regUsername = '';
  regEmail = '';
  regPassword = '';
  // Validation
  nameError = false;
  userError = false;
  emailError = false;
  passError = false;
  passStrength = 0;
  passBarWidth = '0%';
  passBarClass = 'progress-bar bg-danger';

  constructor(private http: HttpClient, private router: Router) {}

  activateSignUp(e?: Event) { if (e) e.preventDefault(); this.rightPanelActive = true; }
  activateSignIn(e?: Event) { if (e) e.preventDefault(); this.rightPanelActive = false; }

  handleLogin() {
    if (!this.loginUsername || !this.loginPassword) return;
    this.http.post<any>('/login', { username: this.loginUsername, userpass: this.loginPassword }).subscribe({
      next: (data) => {
        if (data.name) sessionStorage.setItem('name', data.name);
        setTimeout(() => this.router.navigate(['/dashboard']), 500);
      },
      error: (err) => alert(err.error?.error || 'Login failed'),
    });
  }

  handleRegistration() {
    const nameRegex = /[a-zA-Z0-9\s]{3,}/;
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    const passRegex = /^(?=.*[A-Za-z])(?=.*\d).{6,}$/;
    if (!nameRegex.test(this.regUsername) || !emailRegex.test(this.regEmail) || !passRegex.test(this.regPassword)) {
      alert('Please fix the errors in the form before signing up!');
      return;
    }
    this.http.post<any>('/register', { name: this.regName, username: this.regUsername, email: this.regEmail, userpass: this.regPassword }).subscribe({
      next: () => {
        sessionStorage.setItem('name', this.regName);
        this.router.navigate(['/dashboard']);
      },
      error: (err) => alert(err.error?.error || 'Registration failed'),
    });
  }

  onUsernameInput() {
    this.userError = !/[a-zA-Z0-9\s]{3,}/.test(this.regUsername);
  }
  onEmailInput() {
    this.emailError = !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(this.regEmail);
  }
  onPasswordInput() {
    const val = this.regPassword;
    let strength = 0;
    if (val.length > 6) strength++;
    if (val.match(/[A-Z]/)) strength++;
    if (val.match(/[0-9]/)) strength++;
    if (strength <= 1) { this.passBarWidth = '33%'; this.passBarClass = 'progress-bar bg-danger'; }
    else if (strength === 2) { this.passBarWidth = '66%'; this.passBarClass = 'progress-bar bg-warning'; }
    else { this.passBarWidth = '100%'; this.passBarClass = 'progress-bar bg-success'; }
    this.passError = !/^(?=.*[A-Za-z])(?=.*\d).{6,}$/.test(val);
  }
  onNameInput() {
    this.nameError = !/[a-zA-Z\s]{3,}/.test(this.regName);
  }
}
