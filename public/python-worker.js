// Execute the shipped Python package. No JavaScript replica of the fault engine.
// This worker accepts only bounded demo configuration, never executable code.
let runtime;
async function initialize() {
  const { loadPyodide } = await import('https://cdn.jsdelivr.net/pyodide/v314.0.6/full/pyodide.mjs');
  const py = await loadPyodide({indexURL:'https://cdn.jsdelivr.net/pyodide/v314.0.6/full/'});
  const response = await fetch('/engine.bundle.json');
  if (!response.ok) throw new Error('Could not load ToolStorm package');
  const files = await response.json();
  py.FS.mkdirTree('/home/pyodide/toolstorm');
  for (const [name, code] of Object.entries(files)) {
    if (!/^toolstorm\/[a-z_]+\.py$/.test(name) || typeof code !== 'string') throw new Error('Invalid engine bundle');
    py.FS.writeFile('/home/pyodide/' + name, code);
  }
  py.runPython('import json\nfrom toolstorm.demo import run_comparison');
  return py;
}
self.onmessage = async ({data}) => {
  const {id, config} = data;
  try {
    runtime ??= initialize().catch(error => { runtime = undefined; throw error; });
    const py = await runtime;
    if (config === null) {self.postMessage({id, ready:true}); return;}
    if (!config || Object.keys(config).some(key => !['scenario','seed','probability','max_calls'].includes(key))) {
      throw new Error('Invalid run configuration');
    }
    py.globals.set('_config_json', JSON.stringify(config));
    const result = py.runPython('json.dumps(run_comparison(**json.loads(_config_json)))');
    py.globals.delete('_config_json');
    self.postMessage({id, result: JSON.parse(result)});
  } catch (error) {
    self.postMessage({id, error: String(error?.message || 'Python worker failed')});
  }
};
