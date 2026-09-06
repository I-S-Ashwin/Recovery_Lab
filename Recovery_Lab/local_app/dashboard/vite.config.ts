import { sites } from '@openai/sites-vite-plugin';
import tailwindcss from '@tailwindcss/postcss';
import vinext from 'vinext';
import { defineConfig } from 'vite';

// Static export is served by Python locally; no Cloudflare worker is used here.
export default defineConfig({
  css: { postcss: { plugins: [tailwindcss()] } },
  server: {
    host: '127.0.0.1', port: 5174, strictPort: true,
    proxy: { '/v1': 'http://127.0.0.1:8078', '/health': 'http://127.0.0.1:8078', '/ready': 'http://127.0.0.1:8078' },
  },
  plugins: [vinext(), sites()],
});
