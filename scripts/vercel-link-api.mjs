/**
 * When Vercel deploys from the repo root (Root Directory unset), serverless routes
 * must live at ./api. Copy frontend/api → api after the static build.
 * Skipped when frontend/api is already the project api root (Root Directory = frontend).
 */
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.join(__dirname, "..");
const srcApi = path.join(repoRoot, "frontend", "api");
const destApi = path.join(repoRoot, "api");

async function exists(p) {
  try {
    await fs.access(p);
    return true;
  } catch {
    return false;
  }
}

async function copyRecursive(from, to) {
  await fs.mkdir(to, { recursive: true });
  const entries = await fs.readdir(from, { withFileTypes: true });
  for (const ent of entries) {
    const fp = path.join(from, ent.name);
    const tp = path.join(to, ent.name);
    if (ent.isDirectory()) {
      await copyRecursive(fp, tp);
    } else if (ent.isFile()) {
      await fs.copyFile(fp, tp);
    }
  }
}

if (!(await exists(srcApi))) {
  console.error("vercel-link-api: missing", srcApi);
  process.exit(1);
}

await fs.rm(destApi, { recursive: true, force: true });
await copyRecursive(srcApi, destApi);
console.log(`vercel-link-api: ${srcApi} -> ${destApi}`);
