import { useState, useCallback } from 'react';

export function useBrowseFolder() {
  const [browsing, setBrowsing] = useState(false);
  const browse = useCallback(async (): Promise<string> => {
    setBrowsing(true);
    try { const r = await fetch('/api/browse-folder'); const data = await r.json(); return data.path || ''; }
    catch { return ''; }
    finally { setBrowsing(false); }
  }, []);
  return { browse, browsing };
}
