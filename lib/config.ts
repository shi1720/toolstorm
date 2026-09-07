import type { Config, Policy, Scenario } from './types';
const scenarios: Scenario[] = [
  'lost_ack',
  'rate_limit',
  'schema_drift',
  'timeout',
  'latency',
  'blackout',
];
const policies: Policy[] = ['optimistic', 'retry', 'resilient'];
export function readConfig(
  query: Record<string, string | string[] | undefined>,
): { config: Config; policy: Policy } {
  const value = (key: string, fallback: string) =>
    typeof query[key] === 'string' ? (query[key] as string) : fallback;
  const scenario = value('scenario', 'lost_ack') as Scenario,
    seed = Number(value('seed', '42')),
    probability = Number(value('p', '1')),
    budget = Number(value('budget', '8')),
    policy = value('policy', 'retry') as Policy;
  return {
    config: {
      scenario: scenarios.includes(scenario) ? scenario : 'lost_ack',
      seed:
        Number.isSafeInteger(seed) && seed >= 0 && seed <= 999999 ? seed : 42,
      probability:
        Number.isFinite(probability) && probability >= 0 && probability <= 1
          ? probability
          : 1,
      max_calls:
        Number.isInteger(budget) && budget >= 1 && budget <= 20 ? budget : 8,
    },
    policy: policies.includes(policy) ? policy : 'retry',
  };
}
