import { useEffect } from 'react';

// Light or dark from the operating system (prefers-color-scheme), applied
// as the `dark` class on <html> that the tokens use (src/styles/globals.css).
// Nothing is stored in the browser (HR1).
export function useSystemTheme(): void {
  useEffect(() => {
    const query = window.matchMedia('(prefers-color-scheme: dark)');
    const apply = () => document.documentElement.classList.toggle('dark', query.matches);
    apply();
    query.addEventListener('change', apply);
    return () => query.removeEventListener('change', apply);
  }, []);
}
