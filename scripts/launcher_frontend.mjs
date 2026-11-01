// Use the project's installed Vite and existing config; never download dependencies.
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
process.env.DEMODOCTOR_API_URL = 'http://127.0.0.1:8765';
const { createServer } = await import(pathToFileURL(path.join(root, 'web/node_modules/vite/dist/node/index.js')).href);
const server = await createServer({
  root: path.join(root, 'web'),
  configFile: path.join(root, 'web/vite.config.ts'),
  server: { host: '127.0.0.1', port: 5173, strictPort: true, open: false },
  plugins: [{
    name: 'demodoctor-launcher-identity',
    configureServer(server) {
      server.middlewares.use('/__demodoctor_launcher', (_req, res) => {
        res.setHeader('Content-Type', 'application/json');
        res.end(JSON.stringify({ protocol: 1, kind: 'frontend', root, pid: process.pid,
          instance: process.env.DEMODOCTOR_LAUNCH_INSTANCE,
          api: process.env.DEMODOCTOR_API_URL, offline: true }));
      });
    },
  }],
});
await server.listen();
server.printUrls();
