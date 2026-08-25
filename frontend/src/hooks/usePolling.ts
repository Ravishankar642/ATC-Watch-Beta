import { useCallback, useEffect, useRef, useState } from "react";
import { ApiAuthError } from "../services/api";

interface PollResult<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
  unauthorized: boolean;
}

/**
 * Polls `fetcher` every `intervalMs` (default matches the VATSIM feed's own
 * 15s regeneration cadence — polling faster would just re-fetch the same
 * data and waste battery/mobile data). Automatically pauses while the tab
 * or installed app is backgrounded, and resumes immediately on foreground.
 */
export function usePolling<T>(fetcher: () => Promise<T>, intervalMs = 15000): PollResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);
  const [unauthorized, setUnauthorized] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const tick = useCallback(async () => {
    if (document.visibilityState !== "visible") return;
    try {
      const result = await fetcherRef.current();
      setData(result);
      setError(null);
      setUnauthorized(false);
    } catch (e) {
      if (e instanceof ApiAuthError) {
        setUnauthorized(true);
      } else {
        setError(e as Error);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    tick();
    timerRef.current = setInterval(tick, intervalMs);

    const onVisibility = () => {
      if (document.visibilityState === "visible") tick();
    };
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [tick, intervalMs]);

  return { data, error, loading, unauthorized };
}
