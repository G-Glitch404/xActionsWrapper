import { createBrowser, createPage, loginWithCookie, scrapeTweets } from "xactions"

const mode = process.argv[2]
const target = process.argv[3]
const limit = Number(process.argv[4] || "10")

if (!mode) {
  throw new Error("missing mode")
}

if (!target) {
  throw new Error("missing target")
}

const authToken =
  process.env.XACTIONS_AUTH_TOKEN ||
  process.env.XACTIONS_SESSION_COOKIE ||
  ""

const browser = await createBrowser({
  headless: true,
  args: ["--no-sandbox", "--disable-setuid-sandbox"],
  protocolTimeout: 1200000,
})

try {
  const page = await createPage(browser)

  if (authToken) {
    await loginWithCookie(page, authToken)
  }

  let items = []

  if (mode === "tweets") {
    items = await scrapeTweets(page, target, { limit })
  } else if (mode === "list_timeline") {
    await page.goto(target, { waitUntil: "networkidle2" })

    items = await page.evaluate(async (wantedLimit) => {
      const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
      const seen = new Set()
      const results = []
      let stableRounds = 0

      const collect = () => {
        const tweetNodes = document.querySelectorAll('article[data-testid="tweet"]')
        for (const tweet of tweetNodes) {
          const text = tweet.querySelector('[data-testid="tweetText"]')?.innerText || ""
          const user = tweet.querySelector('[data-testid="User-Name"]')?.innerText || ""
          const time = tweet.querySelector("time")?.getAttribute("datetime") || ""
          const key = `${user}|${time}|${text}`
          if (text && !seen.has(key)) {
            seen.add(key)
            results.push({ user, text, time })
          }
        }
      }

      collect()

      while (results.length < wantedLimit && stableRounds < 4) {
        window.scrollTo(0, document.body.scrollHeight)
        await sleep(2000)
        const before = results.length
        collect()
        if (results.length === before) {
          stableRounds += 1
        } else {
          stableRounds = 0
        }
      }

      return results.slice(0, wantedLimit)
    }, limit)
  } else {
    throw new Error(`unsupported mode: ${mode}`)
  }

  process.stdout.write(JSON.stringify(items))
} finally {
  await browser.close()
}
