/**
 * Copy Phase 5 static UI into frontend/public for Vercel (standard static root).
 */
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.join(__dirname, "..");
const dest = path.join(frontendRoot, "public");
const srcDir = path.join(frontendRoot, "..", "src", "phase5", "public");

async function pathExists(p) {
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

if (!(await pathExists(srcDir))) {
  console.error(`sync-public: missing source ${srcDir}`);
  process.exit(1);
}

await fs.rm(dest, { recursive: true, force: true });
await copyRecursive(srcDir, dest);
console.log(`sync-public: ${srcDir} -> ${dest}`);
