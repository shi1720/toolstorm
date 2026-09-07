import { Lab } from '@/components/lab';
import { readConfig } from '@/lib/config';
export default async function Home({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { config, policy } = readConfig(await searchParams);
  return (
    <Lab
      key={JSON.stringify([config, policy])}
      initialConfig={config}
      initialPolicy={policy}
    />
  );
}
