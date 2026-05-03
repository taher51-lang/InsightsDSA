import { HttpInterceptorFn } from '@angular/common/http';
import { HttpClient } from '@angular/common/http';
import { inject } from '@angular/core';
import { switchMap, of, catchError } from 'rxjs';

let csrfToken: string | null = null;

export const csrfInterceptor: HttpInterceptorFn = (req, next) => {
  const method = req.method.toUpperCase();
  if (['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    return next(req);
  }

  const http = inject(HttpClient);

  const handleRequest = (token: string) => {
    return next(req.clone({ setHeaders: { 'X-CSRFToken': token } })).pipe(
      catchError(err => {
        if (err.status === 400 && err.error && (typeof err.error === 'string' && err.error.includes('CSRF') || err.message?.includes('CSRF'))) {
          csrfToken = null;
          return http.get<{ csrf_token: string }>('/api/v1/csrf').pipe(
            switchMap(res => {
              csrfToken = res.csrf_token;
              return next(req.clone({ setHeaders: { 'X-CSRFToken': csrfToken! } }));
            })
          );
        }
        throw err;
      })
    );
  };

  if (csrfToken) {
    return handleRequest(csrfToken);
  }

  return http.get<{ csrf_token: string }>('/api/v1/csrf').pipe(
    catchError(() => of({ csrf_token: '' })),
    switchMap(res => {
      csrfToken = res.csrf_token;
      if (!csrfToken) {
        return next(req);
      }
      return handleRequest(csrfToken);
    })
  );
};
