import { defineConfig, loadEnv } from 'vite';
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const proxy = { '/api': { target: env.API_TARGET || 'http://127.0.0.1:8000', changeOrigin: true, rewrite: path => path.replace(/^\/api/, '') } };
  return { server: { host: '127.0.0.1', port: 5173, strictPort: true, proxy }, preview: { host: '127.0.0.1', port: 4173, proxy } };
});
