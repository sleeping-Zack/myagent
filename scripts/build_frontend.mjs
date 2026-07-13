import { copyFile, mkdir } from "node:fs/promises";

await mkdir("static/vendor", { recursive: true });
await Promise.all([
  copyFile("node_modules/marked/marked.min.js", "static/vendor/marked.min.js"),
  copyFile("node_modules/dompurify/dist/purify.min.js", "static/vendor/purify.min.js")
]);
