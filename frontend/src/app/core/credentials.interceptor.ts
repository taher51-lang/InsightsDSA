import { HttpInterceptorFn } from '@angular/common/http';

/** Send session cookies on same-origin API and auth requests to Flask. */
export const credentialsInterceptor: HttpInterceptorFn = (req, next) => {
  if (req.url.startsWith("http://") || req.url.startsWith("https://")) {
    return next(req);
  }
  return next(req.clone({ withCredentials: true }));
};
