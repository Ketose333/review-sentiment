const nodeVersion = process.versions.node.split(".").map(Number);
const npmVersion = process.env.npm_config_user_agent?.match(/\bnpm\/(\d+)\.(\d+)\.(\d+)\b/)?.slice(1).map(Number);

const nodeSupported = nodeVersion[0] === 22 && nodeVersion[1] >= 16;
const npmSupported = npmVersion?.[0] === 10;

if (!nodeSupported || !npmSupported) {
  throw new Error("Use Node.js >=22.16.0 <23 and npm >=10 <11. Baseline: Node 22.16.0 / npm 10.9.2.");
}

console.log(`Toolchain: Node ${process.versions.node}, npm ${npmVersion.join(".")} (supported)`);
