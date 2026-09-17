'use client';
import { useState, useSyncExternalStore } from 'react';
import { useSearchParams } from 'next/navigation';
import { Lab } from './lab';
import { readConfig } from '@/lib/config';

const subscribe = () => () => {};

// Render the same recorded example on the server and during hydration. The
// query hook only mounts in the browser, so export never enters an SSR bailout.
export function URLConfiguredLab() {
  const ready = useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );
  if (ready) return <BrowserConfiguredLab />;
  const { config, policy } = readConfig({});
  return (
    <Lab initialConfig={config} initialPolicy={policy} interactive={false} />
  );
}

function BrowserConfiguredLab() {
  const params = useSearchParams();
  const queryString = params.toString();
  const [identity, setIdentity] = useState({
    query: queryString,
    generation: 0,
    sharedQuery: null as string | null,
  });
  let generation = identity.generation;
  if (identity.query !== queryString) {
    // Sharing updates the address without discarding the executed evidence.
    // Real navigation, including returning Home, starts a fresh lab instance.
    if (identity.sharedQuery !== queryString) generation++;
    setIdentity({ query: queryString, generation, sharedQuery: null });
  }
  const query: Record<string, string | string[] | undefined> = {};
  for (const key of params.keys()) {
    const values = params.getAll(key);
    query[key] = values.length === 1 ? values[0] : values;
  }
  const { config, policy } = readConfig(query);
  return (
    <Lab
      key={generation}
      initialConfig={config}
      initialPolicy={policy}
      onBeforeShare={(query) => {
        setIdentity((current) => ({
          ...current,
          sharedQuery: query === queryString ? null : query,
        }));
      }}
    />
  );
}
