'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import type { Comparison, Config } from './types';

type Pending = {
  resolve: (value: Comparison) => void;
  reject: (reason: Error) => void;
  timer: ReturnType<typeof setTimeout>;
};
export function useEngine() {
  const worker = useRef<Worker | null>(null),
    pending = useRef<Map<number, Pending>>(new Map()),
    serial = useRef(0);
  const [status, setStatus] = useState<'idle' | 'loading' | 'ready' | 'error'>(
    'idle',
  );
  const stop = useCallback(() => {
    worker.current?.terminate();
    worker.current = null;
    for (const req of pending.current.values()) {
      clearTimeout(req.timer);
      req.reject(new Error('Run cancelled.'));
    }
    pending.current.clear();
    setStatus('idle');
  }, []);
  useEffect(
    () => () => {
      worker.current?.terminate();
      worker.current = null;
      for (const req of pending.current.values()) {
        clearTimeout(req.timer);
        req.reject(new Error('Lab closed'));
      }
      pending.current.clear();
    },
    [],
  );
  const run = useCallback(
    (config: Config) =>
      new Promise<Comparison>((resolve, reject) => {
        if (!worker.current) {
          setStatus('loading');
          const w = new Worker('/python-worker.js', { type: 'module' });
          worker.current = w;
          w.onmessage = ({ data }) => {
            const req = pending.current.get(data.id);
            if (!req) return;
            clearTimeout(req.timer);
            pending.current.delete(data.id);
            if (data.error) {
              setStatus('error');
              req.reject(new Error(data.error));
            } else {
              setStatus('ready');
              req.resolve(data.result);
            }
          };
          w.onerror = () => {
            setStatus('error');
            for (const req of pending.current.values()) {
              clearTimeout(req.timer);
              req.reject(
                new Error(
                  'Python could not start. Check your connection and try again.',
                ),
              );
            }
            pending.current.clear();
            w.terminate();
            worker.current = null;
          };
        }
        const id = ++serial.current;
        const timer = setTimeout(() => {
          pending.current.delete(id);
          worker.current?.terminate();
          worker.current = null;
          setStatus('error');
          reject(
            new Error(
              'Python took too long to load. Please retry on a stable connection.',
            ),
          );
        }, 90000);
        pending.current.set(id, { resolve, reject, timer });
        worker.current.postMessage({ id, config });
      }),
    [],
  );
  return { run, status, stop };
}
