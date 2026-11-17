// Vite 8 turns TSX into JS with its built-in oxc (no @vitejs/plugin-react: not on this machine, 03 §12.2).
export default {
  oxc: { jsx: { runtime: "automatic" } },
  build: { outDir: "dist", emptyOutDir: true, assetsInlineLimit: 0, sourcemap: false },
  server: { proxy: { "/api": process.env.VIEW_DEV_API || "http://127.0.0.1:18767" } },
};
