export type Scenario =
  | 'lost_ack'
  | 'rate_limit'
  | 'schema_drift'
  | 'timeout'
  | 'latency'
  | 'blackout';
export type Policy = 'optimistic' | 'retry' | 'resilient';
export type Config = {
  scenario: Scenario;
  seed: number;
  probability: number;
  max_calls: number;
};
export type Call = {
  id: number;
  tool: string;
  ordinal: number;
  parent_id: number | null;
  key: string;
  started: number;
  elapsed: number;
  status: string;
  fault: string | null;
  kind: string | null;
  executed: boolean;
  injected: boolean;
  arguments: unknown;
  output: unknown;
  error: { type: string; known: boolean; retry_after?: number } | null;
  capture_error: boolean;
};
export type Effect = {
  name: string;
  key: string;
  call_id: number;
  at: number;
  identity: number;
  redacted: boolean;
};
export type Run = {
  scenario: Scenario;
  policy: Policy;
  seed: number;
  config: Config;
  outcome: { completed: boolean; reason?: string; receipt?: unknown };
  shipments: { shipment_id: string; order_id: string; warehouse: string }[];
  report: {
    schema_version: number;
    seed: number;
    clock: string;
    calls: Call[];
    effects: Effect[];
    rules: unknown[];
    coverage: Record<
      string,
      { eligible: number; selected: number; triggered: number }
    >;
    budget_rejections: number;
    capture: boolean;
  };
  contract: {
    passed: boolean;
    checks: { name: string; passed: boolean; detail: string }[];
  };
  stats: { calls: number; effects: number; faults: number; elapsed: number };
  digest: string;
};
export type Comparison = {
  schema_version: number;
  engine_version: string;
  scenario: Scenario;
  config: Config;
  runs: Run[];
};
