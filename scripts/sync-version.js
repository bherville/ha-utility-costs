const fs = require("fs");
const path = require("path");

const packagePath = path.join(__dirname, "..", "package.json");
const manifestPath = path.join(
  __dirname,
  "..",
  "custom_components",
  "ha_utility_costs",
  "manifest.json"
);

// Read version from package.json
const pkg = JSON.parse(fs.readFileSync(packagePath, "utf8"));
const version = pkg.version;

// Update manifest.json
const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
manifest.version = version;
fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + "\n");

console.log(`Synced manifest.json to version ${version}`);
