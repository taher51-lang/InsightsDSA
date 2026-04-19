import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { ApiService } from '../../services/api.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './login.component.html',
  styleUrl: './login.component.css',
})
export class LoginComponent {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);

  readonly form = this.fb.nonNullable.group({
    username: ['', Validators.required],
    userpass: ['', Validators.required],
  });

  errorMsg = '';

  submit(): void {
    this.errorMsg = '';
    if (this.form.invalid) {
      return;
    }
    const { username, userpass } = this.form.getRawValue();
    this.api.login(username, userpass).subscribe({
      next: () => void this.router.navigateByUrl('/dashboard'),
      error: (err) => {
        this.errorMsg =
          err?.error?.error ?? err?.message ?? 'Login failed. Try again.';
      },
    });
  }
}
