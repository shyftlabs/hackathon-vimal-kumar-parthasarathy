'use client';

import { useEffect } from 'react';

/**
 * Browser extensions (MetaMask, etc.) inject scripts into every page and can throw
 * uncaught errors like "Failed to connect to MetaMask" from `chrome-extension://…`.
 * In dev, Next.js's error overlay catches those and shows them as if they were app
 * errors. This swallows ONLY extension-originated errors (capture phase, before the
 * overlay's handler) — real application errors are untouched and still surface.
 */
function isExtensionNoise(text: string): boolean {
  return (
    /chrome-extension:\/\//i.test(text) ||
    /moz-extension:\/\//i.test(text) ||
    /Failed to connect to MetaMask/i.test(text) ||
    /\bmetamask\b/i.test(text)
  );
}

export default function SuppressExtensionErrors() {
  useEffect(() => {
    const onError = (e: ErrorEvent) => {
      const text = `${e.message ?? ''} ${e.filename ?? ''} ${e.error?.stack ?? ''}`;
      if (isExtensionNoise(text)) {
        e.stopImmediatePropagation();
        e.preventDefault();
      }
    };
    const onRejection = (e: PromiseRejectionEvent) => {
      const r = e.reason as { message?: string; stack?: string } | string | undefined;
      const text = typeof r === 'string' ? r : `${r?.message ?? ''} ${r?.stack ?? ''}`;
      if (isExtensionNoise(text)) {
        e.stopImmediatePropagation();
        e.preventDefault();
      }
    };
    // Capture phase so we run before Next.js's dev overlay handler.
    window.addEventListener('error', onError, true);
    window.addEventListener('unhandledrejection', onRejection, true);
    return () => {
      window.removeEventListener('error', onError, true);
      window.removeEventListener('unhandledrejection', onRejection, true);
    };
  }, []);

  return null;
}
