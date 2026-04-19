import { Component, inject, OnInit } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ApiService, ProfilePayload } from '../../services/api.service';

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [ReactiveFormsModule],
  templateUrl: './profile.component.html',
  styleUrl: './profile.component.css',
})
export class ProfileComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);

  data: ProfilePayload | null = null;
  loadError = '';
  pwdMsg = '';
  pwdErr = '';
  keyMsg = '';
  keyErr = '';

  readonly pwdForm = this.fb.nonNullable.group({
    current_password: ['', Validators.required],
    new_password: ['', [Validators.required, Validators.minLength(8)]],
  });

  readonly keyForm = this.fb.nonNullable.group({
    api_key: ['', Validators.required],
    provider: ['gemini', Validators.required],
  });

  ngOnInit(): void {
    this.api.profile().subscribe({
      next: (d) => {
        this.data = d;
      },
      error: (e) => {
        this.loadError =
          e?.error?.error ?? e?.message ?? 'Could not load profile.';
      },
    });
  }

  submitPassword(): void {
    this.pwdMsg = '';
    this.pwdErr = '';
    if (this.pwdForm.invalid) {
      return;
    }
    const v = this.pwdForm.getRawValue();
    this.api.changePassword(v).subscribe({
      next: (r) => {
        if (r.success) {
          this.pwdMsg = r.message ?? 'Password updated.';
          this.pwdForm.reset();
        } else {
          this.pwdErr = r.error ?? 'Update failed.';
        }
      },
      error: (e) => {
        this.pwdErr = e?.error?.error ?? e?.message ?? 'Update failed.';
      },
    });
  }

  submitKey(): void {
    this.keyMsg = '';
    this.keyErr = '';
    if (this.keyForm.invalid) {
      return;
    }
    const v = this.keyForm.getRawValue();
    this.api.setApiKey(v).subscribe({
      next: (r) => {
        if (r.status === 'success') {
          this.keyMsg = 'API key saved (server-side, encrypted).';
          localStorage.setItem('ai_provider', v.provider);
          this.keyForm.patchValue({ api_key: '' });
        } else {
          this.keyErr = r.message ?? 'Could not save key.';
        }
      },
      error: (e) => {
        this.keyErr = e?.error?.message ?? e?.error?.error ?? 'Could not save key.';
      },
    });
  }

  badgeClass(color: string): string {
    return `text-bg-${color}`;
  }
}
