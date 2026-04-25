import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from './auth.service';
import { map } from 'rxjs/operators';

export const adminGuard = () => {
  const auth = inject(AuthService);
  const router = inject(Router);

  return auth.check().pipe(
    map(u => {
      if (u.authenticated && u.is_admin) {
        return true;
      }
      router.navigate(['/']);
      return false;
    })
  );
};
