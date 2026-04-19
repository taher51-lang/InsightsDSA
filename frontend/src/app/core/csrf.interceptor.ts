import { HttpClient, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { switchMap, tap } from 'rxjs/operators';

let csrfToken: string | null = null;

export const csrfInterceptor: HttpInterceptorFn = (req, next) => {
  const m = req.method.toUpperCase();
  if (!['POST', 'PUT', 'PATCH', 'DELETE'].includes(m)) {
    return next(req);
  }
  if (req.url.includes('/api/v1/csrf')) {
    return next(req);
  }
  const http = inject(HttpClient);
  const send = (token: string) =>
    next(req.clone({ setHeaders: { 'X-CSRFToken': token } }));
  if (csrfToken) {
    return send(csrfToken);
  }
  return http.get<{ csrf_token: string }>('/api/v1/csrf').pipe(
    tap((r) => {
      csrfToken = r.csrf_token;
    }),
    switchMap((r) => send(r.csrf_token)),
  );
};
