// Cross-runtime contract: the browser bundle must produce the CPython results.
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { loadPyodide } from 'pyodide';

const files = JSON.parse(readFileSync('public/engine.bundle.json', 'utf8'));
for (const [name, code] of Object.entries(files)) {
  assert.equal(
    code,
    readFileSync(`src/${name}`, 'utf8'),
    `Stale browser module: ${name}`,
  );
}
const scenarios = [
  'lost_ack',
  'rate_limit',
  'schema_drift',
  'timeout',
  'latency',
  'blackout',
];
const configs = scenarios.flatMap((scenario) =>
  [0, 0.5, 1].flatMap((probability) =>
    [42, 1729].map((seed) => ({ scenario, probability, seed, max_calls: 8 })),
  ),
);
const python =
  process.env.TOOLSTORM_PYTHON ||
  (existsSync('.venv/bin/python') ? '.venv/bin/python' : 'python');
const source = spawnSync(
  python,
  [
    '-c',
    'import json,sys;from toolstorm.demo import run_comparison;print(json.dumps([run_comparison(**c) for c in json.loads(sys.stdin.read())]))',
  ],
  {
    input: JSON.stringify(configs),
    encoding: 'utf8',
    maxBuffer: 16 * 1024 * 1024,
  },
);
assert.equal(source.status, 0, source.stderr);
const expected = JSON.parse(source.stdout);
const manifest = JSON.parse(readFileSync('package.json', 'utf8'));
assert.equal(
  expected[0].engine_version,
  manifest.version,
  'Python and website release versions differ',
);
const py = await loadPyodide();
py.FS.mkdirTree('/home/pyodide/toolstorm');
for (const [name, code] of Object.entries(files))
  py.FS.writeFile(`/home/pyodide/${name}`, code);
py.globals.set('_configs_json', JSON.stringify(configs));
const actual = JSON.parse(
  py.runPython(
    'import json\nfrom toolstorm.demo import run_comparison\njson.dumps([run_comparison(**c) for c in json.loads(_configs_json)])',
  ),
);
assert.deepEqual(actual, expected, 'Browser Python and CPython diverged');
const initial = JSON.parse(readFileSync('lib/default-run.json', 'utf8'));
const initialIndex = configs.findIndex(
  (c) => c.scenario === 'lost_ack' && c.probability === 1 && c.seed === 42,
);
assert.deepEqual(initial, expected[initialIndex], 'Initial example is stale');
console.log(
  `PASS: ${configs.length} configurations × 3 policies match exactly across CPython and Pyodide, including traces and digests.`,
);
