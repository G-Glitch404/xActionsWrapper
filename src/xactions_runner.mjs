import { createBrowser, createPage, loginWithCookie, scrapeTweets } from "xactions"

const mode = process.argv[2]
const target = process.argv[3]
const limit = Number(process.argv[4] || "10")
const stopDateRaw = process.argv[5] || process.env.XACTIONS_STOP_DATE || ""
const stopDate = stopDateRaw ? new Date(`${stopDateRaw}T00:00:00Z`) : null

if (stopDate && Number.isNaN(stopDate.getTime())) {
  throw new Error("invalid stop_date")
}

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

function parseCount(value) {
  const text = String(value || "").trim().replace(/,/g, "")
  if (!text || text === "0") {
    return 0
  }

  const match = text.match(/^(\d+(?:\.\d+)?)([KMB])?$/i)
  if (!match) {
    const direct = Number.parseInt(text, 10)
    return Number.isFinite(direct) ? direct : 0
  }

  const num = Number.parseFloat(match[1])
  const suffix = (match[2] || "").toUpperCase()

  if (suffix === "K") return Math.round(num * 1_000)
  if (suffix === "M") return Math.round(num * 1_000_000)
  if (suffix === "B") return Math.round(num * 1_000_000_000)
  return Math.round(num)
}

try {
  const page = await createPage(browser)

  if (authToken) {
    await loginWithCookie(page, authToken)
  }

  let items = []

  if (mode === "tweets") {
    items = await scrapeTweets(page, target, { limit })
  } else if (mode === "scrape_timeline" || mode === "list_timeline") {
    await page.goto(target, { waitUntil: "networkidle2" })

    items = await page.evaluate(async (wantedLimit, stopDate) => {
      const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

      const parseCount = (value) => {
        const text = String(value || "").trim().replace(/,/g, "")
        if (!text || text === "0") {
          return 0
        }

        const match = text.match(/^(\d+(?:\.\d+)?)([KMB])?$/i)
        if (!match) {
          const direct = Number.parseInt(text, 10)
          return Number.isFinite(direct) ? direct : 0
        }

        const num = Number.parseFloat(match[1])
        const suffix = (match[2] || "").toUpperCase()

        if (suffix === "K") return Math.round(num * 1_000)
        if (suffix === "M") return Math.round(num * 1_000_000)
        if (suffix === "B") return Math.round(num * 1_000_000_000)
        return Math.round(num)
      }

      const cleanText = (value) => String(value || "").replace(/\s+/g, " ").trim()

      const extractUserInfo = (tweet) => {
        const userBox = tweet.querySelector('[data-testid="User-Name"]')
        const raw = cleanText(userBox?.innerText || userBox?.textContent || "")
        const handleMatch = raw.match(/@([A-Za-z0-9_]{1,15})/)

        let account_name = cleanText(raw.split("@")[0] || "").replace(/\s+[·•|].*$/, "").trim()
        let username = handleMatch ? handleMatch[1] : ""

        if (!account_name && username) {
          account_name = username
        }

        return { account_name, username }
      }

      const extractVerified = (tweet) => {
        const userBox = tweet.querySelector('[data-testid="User-Name"]')
        if (!userBox) {
          return false
        }

        return Boolean(
          userBox.querySelector('svg[aria-label="Verified account"]') ||
          userBox.querySelector('[data-testid="icon-verified"]')
        )
      }

      const extractTweetId = (tweet) => {
        const link = tweet.querySelector('a[href*="/status/"]')
        if (!link) {
          return ""
        }

        const href = link.getAttribute("href") || ""
        const match = href.match(/\/status\/(\d+)/)
        return match ? match[1] : ""
      }

      const extractTweetUrl = (tweet) => {
        const link = tweet.querySelector('a[href*="/status/"]')
        if (!link) {
          return ""
        }

        const href = link.getAttribute("href") || ""
        if (!href) {
          return ""
        }

        if (href.startsWith("http://") || href.startsWith("https://")) {
          return href
        }

        return `https://x.com${href}`
      }

      const extractMedia = (tweet) => {
        const hasContainer = Boolean(tweet.querySelector('[data-testid="tweetPhoto"]'))
        const videoImage = tweet.querySelector('img[alt="Embedded video"]')
        const photoImage = tweet.querySelector('img[alt="Image"]')

        const has_video = Boolean(videoImage)
        const has_photo = Boolean(photoImage) || (hasContainer && !has_video)
        const has_media = has_photo || has_video

        return {
          has_media,
          has_photo,
          has_video,
        }
      }

      const extractHashtags = (tweet) => {
        const tags = new Set()

        const tagLinks = tweet.querySelectorAll('a[href*="/hashtag/"]')
        for (const link of tagLinks) {
          const href = link.getAttribute("href") || ""
          const match = href.match(/\/hashtag\/([^/?]+)/i)
          if (match && match[1]) {
            tags.add(decodeURIComponent(match[1]).replace(/^#/, ""))
          }
        }

        const text = cleanText(tweet.querySelector('[data-testid="tweetText"]')?.innerText || "")
        const textTags = text.match(/#([A-Za-z0-9_]+)/g) || []
        for (const tag of textTags) {
          tags.add(tag.slice(1))
        }

        return [...tags]
      }

      const extractEngagement = (tweet) => {
        const group = tweet.querySelector('div[role="group"][aria-label]')
        const aria = cleanText(group?.getAttribute("aria-label") || "")

        const metrics = {
          replies: 0,
          reposts: 0,
          likes: 0,
          bookmarks: 0,
          views: 0,
        }

        if (!aria) {
          return metrics
        }

        const parts = aria.split(",").map((part) => part.trim())

        for (const part of parts) {
          const lower = part.toLowerCase()

          if (lower.includes("reply")) {
            const num = part.replace(/reply|replies/gi, "").trim()
            metrics.replies = parseCount(num)
          } else if (lower.includes("repost")) {
            const num = part.replace(/repost|reposts/gi, "").trim()
            metrics.reposts = parseCount(num)
          } else if (lower.includes("like")) {
            const num = part.replace(/like|likes/gi, "").trim()
            metrics.likes = parseCount(num)
          } else if (lower.includes("bookmark")) {
            const num = part.replace(/bookmark|bookmarks/gi, "").trim()
            metrics.bookmarks = parseCount(num)
          } else if (lower.includes("view")) {
            const num = part.replace(/view|views/gi, "").trim()
            metrics.views = parseCount(num)
          }
        }

        return metrics
      }

      const extractTweet = (tweet) => {
        const body = cleanText(tweet.querySelector('[data-testid="tweetText"]')?.innerText || tweet.querySelector('[data-testid="tweetText"]')?.textContent || "")
        const time = tweet.querySelector("time")?.getAttribute("datetime") || ""
        const { account_name, username } = extractUserInfo(tweet)
        const verified = extractVerified(tweet)
        const tweet_id = extractTweetId(tweet)
        const tweet_url = extractTweetUrl(tweet)
        const media = extractMedia(tweet)
        const engagement = extractEngagement(tweet)
        const hashtags = extractHashtags(tweet)

        return {
          tweet_id,
          tweet_url,
          account_name,
          username,
          verified,
          body,
          time,
          hashtags,
          ...media,
          ...engagement,
        }
      }

      const seen = new Set()
      let stableRounds = 0
      let reachedStopDate = false
      const emit = (item) => process.stdout.write(JSON.stringify(item) + "\n")

      const collect = () => {
        const tweetNodes = document.querySelectorAll('article[data-testid="tweet"]')
        for (const tweet of tweetNodes) {
          const item = extractTweet(tweet)
          if (!item.tweet_id) continue
          if (seen.has(item.tweet_id)) continue
          if (!item.body) continue
          if (stopDate && item.time) {
            const tweetTime = new Date(item.time)
            if (!Number.isNaN(tweetTime.getTime()) && tweetTime < stopDate) {
              reachedStopDate = true
              break
            }
          }

          seen.add(item.tweet_id)
          emit(item)
        }
      }

      collect()

      while (results.length < wantedLimit && stableRounds < 4 && !reachedStopDate) {
        window.scrollTo(0, document.body.scrollHeight)
        await sleep(1500)

        const before = results.length
        collect()

        if (results.length === before) {
          stableRounds += 1
        } else {
          stableRounds = 0
        }
      }

      return results.slice(0, wantedLimit)
    }, limit, stopDate)
  } else {
    throw new Error(`unsupported mode: ${mode}`)
  }

  process.stdout.write(JSON.stringify(items))
} finally {
  await browser.close()
}
