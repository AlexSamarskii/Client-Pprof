// Explicit process configuration only: neither Vite config nor env files load.
import { createRequire } from "node:module";
import path from "node:path";
import { pathToFileURL } from "node:url";

const frontend = path.resolve(import.meta.dirname, "../frontend");
const require = createRequire(path.join(frontend, "package.json"));
const { createServer } = await import(pathToFileURL(require.resolve("vite")));
const { default: react } = await import(
  pathToFileURL(require.resolve("@vitejs/plugin-react"))
);
const { default: tailwindcss } = await import(
  pathToFileURL(require.resolve("@tailwindcss/vite"))
);
const server = await createServer({
  root: frontend,
  configFile: false,
  envDir: false,
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.join(frontend, "src") } },
  server: {
    host: "127.0.0.1",
    port: Number(process.env.CP_FRONTEND_PORT ?? 5173),
    strictPort: true,
  },
});
await server.listen();
server.printUrls();
for (const signal of ["SIGTERM", "SIGINT"]) {
  process.once(signal, async () => {
    await server.close();
    process.exit(0);
  });
}
