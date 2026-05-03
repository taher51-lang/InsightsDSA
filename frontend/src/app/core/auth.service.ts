import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of, tap } from 'rxjs';
import { catchError, map } from 'rxjs/operators';

export interface AuthUser {
  authenticated: boolean;
  user_id?: number;
  user_name?: string;
  email?: string;
  profile_pic?: string;
  is_admin?: boolean;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private _user: AuthUser | null = null;

  constructor(private http: HttpClient) {}

  check(): Observable<AuthUser> {
    return this.http.get<AuthUser>('/api/v1/auth/me').pipe(
      tap(u => this._user = u),
      catchError(() => {
        this._user = { authenticated: false };
        return of(this._user);
      })
    );
  }

  get user(): AuthUser | null { return this._user; }

  get isLoggedIn(): boolean { return !!this._user?.authenticated; }

  login(username: string, userpass: string): Observable<any> {
    return this.http.post('/login', { username, userpass });
  }

  register(name: string, username: string, email: string, userpass: string): Observable<any> {
    return this.http.post('/register', { name, username, email, userpass });
  }
}
