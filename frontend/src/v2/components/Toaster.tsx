import * as React from 'react';
import { Toaster as SonnerToaster } from 'sonner';

export function Toaster(): React.ReactElement {
  return (
    <SonnerToaster
      position="bottom-right"
      richColors
      closeButton
      toastOptions={{
        style: {
          fontFamily:
            'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, sans-serif',
          borderRadius: '12px',
        },
      }}
    />
  );
}
