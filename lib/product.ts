import manifest from '../package.json';

/** Distribution and browser engine versions are checked together in CI. */
export const version = manifest.version;
export const repository = 'https://github.com/shi1720/toolstorm';
export const install = `pip install "toolstorm @ git+${repository}.git@v${version}"`;
