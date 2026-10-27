const BRIDGE = "http://127.0.0.1:8765";
const BRIDGE_HEADERS = { "X-Onur-Helper": "1" };
let busy = false;

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function extractPage(source) {
  function priceText(element) {
    if (source !== "Akakçe") return (element.innerText || element.textContent || "").trim();
    const copy = element.cloneNode(true);
    copy.querySelectorAll("span").forEach((node) => node.remove());
    return (copy.textContent || "").trim();
  }
  const normalizedTitle = document.title.toLocaleLowerCase("tr-TR");
  const bodyStart = (document.body?.innerText || "").slice(0, 800).toLocaleLowerCase("tr-TR");
  const blocked = [
    "bir dakika",
    "just a moment",
    "attention required",
    "güvenlik doğrulaması",
    "sorry, you have been blocked"
  ].some((marker) => normalizedTitle.includes(marker) || bodyStart.includes(marker));

  const selector = source === "Akakçe"
    ? "#APL > li, ul.pl_v8 > li, li.w"
    : "article, [data-test-id='product-card'], [class*='ProductCard'], [class*='productCard'], li[class*='product']";
  const titleSelector = source === "Akakçe"
    ? ".pn_v8, h3, h2, a[title]"
    : "[data-test-id='product-title'], h3, h2, a[title], a[aria-label]";
  const priceSelector = source === "Akakçe"
    ? "span.pt_v8, span.pt_v9, span.pr_v8, .p-price"
    : "[data-test-id='price'], .price, [class*='price'], [class*='Price']";

  let nodes = [...document.querySelectorAll(selector)];
  if (source === "Akakçe" && nodes.length === 0 && document.querySelector("h1")) {
    for (const script of document.querySelectorAll("script[type='application/ld+json']")) {
      try {
        const data = JSON.parse(script.textContent);
        const candidates = Array.isArray(data) ? data : [data];
        for (const candidate of candidates) {
          const offer = candidate?.offers;
          const price = offer?.lowPrice ?? offer?.price;
          if (candidate?.name && price) {
            return {
              blocked,
              title: document.title,
              url: location.href,
              cards: [{
                text: `${candidate.name} ${price} TL`,
                titles: [candidate.name],
                prices: [`${price} TL`],
                href: location.href
              }]
            };
          }
        }
      } catch (_) {
        // Ignore unrelated or malformed structured-data blocks.
      }
    }
  }
  if (source === "Cimri" && nodes.length === 0) {
    nodes = [...document.querySelectorAll("h2, h3")]
      .map((heading) => {
        let candidate = heading;
        for (let depth = 0; candidate && depth < 5; depth += 1) {
          if (/\d[\d.\s]*([,]\d{1,2})?\s*TL/i.test(candidate.innerText || "")) {
            return candidate;
          }
          candidate = candidate.parentElement;
        }
        return null;
      })
      .filter(Boolean);
  }

  const seen = new Set();
  const cards = [];
  for (const node of nodes) {
    const text = (node.innerText || "").trim();
    if (!text || seen.has(text)) continue;
    const titles = [...node.querySelectorAll(titleSelector)]
      .flatMap((element) => [
        element.innerText,
        element.getAttribute("title"),
        element.getAttribute("aria-label")
      ])
      .filter(Boolean)
      .map((value) => value.trim());
    const prices = source === "Cimri"
      ? (text.match(/\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?\s*TL/gi) || [])
      : [...node.querySelectorAll(priceSelector)].map(priceText).filter(Boolean);
    const link = node.querySelector("a[href]");
    seen.add(text);
    cards.push({
      text: text.slice(0, 2000),
      titles: [...new Set(titles)].slice(0, 12),
      prices: [...new Set(prices)].slice(0, 12),
      href: link?.href || location.href
    });
    if (cards.length >= 40) break;
  }
  return { blocked, title: document.title, url: location.href, cards };
}

async function waitForTab(tabId, timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const tab = await chrome.tabs.get(tabId);
    if (tab.status === "complete") return;
    await delay(400);
  }
}

async function readJob(job) {
  const tab = await chrome.tabs.create({ url: job.url, active: false });
  try {
    await waitForTab(tab.id);
    let last = null;
    for (let attempt = 0; attempt < 12; attempt += 1) {
      await delay(1000);
      const results = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: extractPage,
        args: [job.source]
      });
      last = results?.[0]?.result || null;
      if (last && !last.blocked && last.cards.length > 0) return last;
    }
    return last || { blocked: false, cards: [], url: job.url, title: "" };
  } finally {
    await chrome.tabs.remove(tab.id).catch(() => {});
  }
}

async function poll() {
  if (busy) return;
  busy = true;
  try {
    const response = await fetch(`${BRIDGE}/next`, {
      cache: "no-store",
      headers: BRIDGE_HEADERS
    });
    if (response.status === 204) return;
    if (!response.ok) throw new Error(`Bridge HTTP ${response.status}`);
    const job = await response.json();
    let result;
    try {
      result = await readJob(job);
    } catch (error) {
      result = { blocked: false, cards: [], url: job.url, error: String(error) };
    }
    await fetch(`${BRIDGE}/result`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...BRIDGE_HEADERS },
      body: JSON.stringify({ id: job.id, ...result })
    });
  } catch (_) {
    // The local app is normally offline; the alarm will try again later.
  } finally {
    busy = false;
    setTimeout(poll, 1000);
  }
}

chrome.runtime.onInstalled.addListener(poll);
chrome.runtime.onStartup.addListener(poll);
chrome.alarms.create("poll-local-price-app", { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "poll-local-price-app") poll();
});
poll();
