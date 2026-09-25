import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

// The app resolves "@/..." through tsconfig paths; tests need the same alias because
// runtime imports (not just type imports) now cross that boundary.
export default defineConfig({
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
});
