import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = resolve(frontendRoot, "..");
const linkPath = join(repoRoot, ".vercel", "project.json");
const verifiedPath = join(repoRoot, ".vercel", "deployment-target.json");

function fail(reason) {
  throw new Error(`Deployment blocked: ${reason}`);
}

if (!existsSync(linkPath) || !existsSync(verifiedPath)) {
  fail("verify the remote project ID and Root Directory, then create the local deployment-target.json record");
}

let linked;
let verified;
try {
  linked = JSON.parse(readFileSync(linkPath, "utf8"));
  verified = JSON.parse(readFileSync(verifiedPath, "utf8"));
} catch {
  fail("project link or deployment target record is invalid JSON");
}

if (!linked.projectId || !linked.orgId ||
    verified.projectId !== linked.projectId || verified.orgId !== linked.orgId ||
    verified.projectName !== "review-sentiment-web" || verified.rootDirectory !== "frontend") {
  fail("linked project and verified review-sentiment-web target do not match");
}

if ((process.env.VERCEL_PROJECT_ID && process.env.VERCEL_PROJECT_ID !== linked.projectId) ||
    (process.env.VERCEL_ORG_ID && process.env.VERCEL_ORG_ID !== linked.orgId)) {
  fail("VERCEL_PROJECT_ID or VERCEL_ORG_ID overrides the verified target");
}

if (new URL(process.env.NEXT_PUBLIC_API_URL).protocol !== "https:") {
  fail("production deployment requires an HTTPS API origin");
}

const packagePath = join(frontendRoot, "node_modules", "vercel", "package.json");
if (!existsSync(packagePath)) fail("the locked Vercel CLI is not installed; run npm ci");

const cliPackage = JSON.parse(readFileSync(packagePath, "utf8"));
if (cliPackage.version !== "60.0.1" || typeof cliPackage.bin?.vercel !== "string") {
  fail("the installed Vercel CLI does not match the locked version");
}
const cliPath = resolve(dirname(packagePath), cliPackage.bin.vercel);
if (!existsSync(cliPath)) fail("the installed Vercel CLI entry point is missing");

const result = spawnSync(process.execPath, [cliPath, "deploy", "--prod"], {
  cwd: repoRoot,
  stdio: "inherit",
  env: process.env,
});
if (result.error) throw result.error;
process.exit(result.status ?? 1);
