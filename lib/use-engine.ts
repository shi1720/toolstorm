'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import type { Comparison, Config } from './types';

type Request = {
  resolve: (value: Comparison) => void;
  reject: (reason: Error) => void;
  timer: ReturnType<typeof setTimeout>;
};
const startupError =
  'Python could not start. Check your connection and try again.';

/** One isolated worker; a failed import must be retried in a fresh worker. */
export function useEngine() {
  const worker = useRef<Worker | null>(null);
  const pending = useRef<Map<number, Request>>(new Map());
  const serial = useRef(0);
  const [status, setStatus] = useState<'idle' | 'loading' | 'ready' | 'error'>(
    'idle',
  );
  const dispose = useCallback((message: string) => {
    worker.current?.terminate();
    worker.current = null;
    for (const request of pending.current.values()) {
      clearTimeout(request.timer);
      request.reject(new Error(message));
    }
    pending.current.clear();
  }, []);
  const stop = useCallback(() => {
    dispose('Run cancelled.');
    setStatus('idle');
  }, [dispose]);
  useEffect(() => () => dispose('Lab closed.'), [dispose]);
  const run = useCallback(
    (config: Config) =>
      new Promise<Comparison>((resolve, reject) => {
        if (pending.current.size) {
          reject(new Error('A comparison is already running.'));
          return;
        }
        try {
          if (!worker.current) {
            setStatus('loading');
            const instance = new Worker('/python-worker.js', {
              type: 'module',
            });
            worker.current = instance;
            instance.onmessage = ({ data }) => {
              if (worker.current !== instance) return;
              const request = pending.current.get(data.id);
              if (!request) return;
              if (data.error || !data.result) {
                dispose(
                  'The comparison could not finish. Try again, or run the example locally.',
                );
                setStatus('error');
                return;
              }
              clearTimeout(request.timer);
              pending.current.delete(data.id);
              setStatus('ready');
              request.resolve(data.result);
            };
            instance.onerror = () => {
              if (worker.current !== instance) return;
              dispose(startupError);
              setStatus('error');
            };
          }
          const id = ++serial.current;
          const timer = setTimeout(() => {
            dispose(
              'Python took longer than 90 seconds. Check your connection and try again.',
            );
            setStatus('error');
          }, 90000);
          pending.current.set(id, { resolve, reject, timer });
          worker.current.postMessage({ id, config });
        } catch {
          dispose(startupError);
          setStatus('error');
          reject(new Error(startupError));
        }
      }),
    [dispose],
  );
  return { run, status, stop };
}
