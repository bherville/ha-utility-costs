const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const manifestPath = path.join(
  __dirname,
  "..",
  "custom_components",
  "ha_utility_costs",
  "manifest.json"
);
const packagePath = path.join(__dirname, "..", "package.json");

// Read package.json version
const pkg = JSON.parse(fs.readFileSync(packagePath, "utf8"));
const version = pkg.version;

// Update manifest.json
const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
manifest.version = version;
fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + "\n");

console.log(`Updated manifest.json to version ${version}`);

// Create git tag
try {
  execSync(`git tag -a v${version} -m "Release v${version}"`, {
    stdio: "inherit",
  });
  execSync("git push --tags", { stdio: "inherit" });
  console.log(`Created and pushed tag v${version}`);
} catch (error) {
  console.log("Tag may already exist or push failed:", error.message);
}
