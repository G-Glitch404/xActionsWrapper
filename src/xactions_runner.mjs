import { spawn } from "node:child_process"

const username = process.argv[2]
const limit = process.argv[3] || "10"

if (!username) {
  throw new Error("missing username")
}

const child = spawn(
  "npx",
  ["xactions", "tweets", username, "--limit", limit],
  {
    stdio: ["ignore", "pipe", "pipe"],
    env: {
      ...process.env,
      XACTIONS_AUTH_TOKEN: process.env.XACTIONS_AUTH_TOKEN || "",
      XACTIONS_CONFIG_DIR: process.env.XACTIONS_CONFIG_DIR || "/data/.xactions",
    },
  }
)

let stdout = ""
let stderr = ""

child.stdout.on("data", chunk => {
  stdout += chunk.toString()
})

child.stderr.on("data", chunk => {
  stderr += chunk.toString()
})

child.on("close", code => {
  if (code !== 0) {
    process.stderr.write(stderr || "xactions failed")
    process.exit(code || 1)
  }
  process.stdout.write(stdout.trim())
})
