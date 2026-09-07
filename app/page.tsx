import { Lab } from '@/components/lab';
import { readConfig } from '@/lib/config';
export default async function Home({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { config, policy } = readConfig(await searchParams);
  return <Lab initialConfig={config} initialPolicy={policy} />;
}
