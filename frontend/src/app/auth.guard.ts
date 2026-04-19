import { inject } from '@angular/core';
import { CanMatchFn, Router, UrlTree } from '@angular/router';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { ApiService } from './services/api.service';

export const authCanMatch: CanMatchFn = (): Observable<boolean | UrlTree> => {
  const api = inject(ApiService);
  const router = inject(Router);
  return api.authMe().pipe(
    map((m) => (m.authenticated ? true : router.parseUrl('/login'))),
  );
};
