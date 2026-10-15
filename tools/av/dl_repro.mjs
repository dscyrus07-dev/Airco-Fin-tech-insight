// Focused repro: report-page Download Excel -> what URL/status does it hit?
import { chromium } from 'playwright'
import { mkdirSync } from 'fs'

const FE = 'http://localhost:3600'
const KC = 'http://localhost:8080'
const OUT = 'X:/Airco Projects/wt-av/tools/av/.local/shots'
const KIT = 'X:/Airco Projects/wt-av/tools/final/demo_pdfs'
mkdirSync(OUT, { recursive: true })
const USER = process.env.TEST_USER_EMAIL, PW = process.env.TEST_USER_PASSWORD
const SECRET = process.env.KC_FE_SECRET

async function token() {
  const body = new URLSearchParams({ grant_type: 'password', client_id: 'frontend-app',
    client_secret: SECRET, username: USER, password: PW, scope: 'openid' })
  const r = await fetch(`${KC}/realms/airco-insights/protocol/openid-connect/token`,
    { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body })
  return r.json()
}

const browser = await chromium.launch({ channel: 'chrome' })
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, acceptDownloads: true })
const page = await ctx.newPage()
const hits = []
page.on('response', (r) => { if (/\/api\/(jobs|download)\//.test(r.url())) hits.push(`${r.status()} ${r.url()}`) })

const tk = await token()
await page.goto(FE, { waitUntil: 'domcontentloaded' })
await page.evaluate(([at, rt]) => {
  sessionStorage.setItem('kc_token', at); sessionStorage.setItem('kc_refresh_token', rt || '')
  document.cookie = `kc_token=${encodeURIComponent(at)}; Path=/; SameSite=Lax`
  if (rt) document.cookie = `kc_refresh_token=${encodeURIComponent(rt)}; Path=/; SameSite=Lax`
}, [tk.access_token, tk.refresh_token || ''])

await page.goto(FE + '/dashboard', { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(1500)
await page.locator('input[type="file"]').setInputFiles([`${KIT}/demo_hdfc.pdf`])
await page.locator('button:has-text("Analyze")').first().click()
await page.waitForFunction(() => /Confirm all detected|Use selected bank|review/i.test(document.body.textContent), null, { timeout: 240000 })
await page.waitForTimeout(800)
const conf = page.locator('button').filter({ hasText: /^Confirm$/ }).first()
if (await conf.count()) { await conf.click(); await page.waitForTimeout(500) }
const bulk = page.locator('button:has-text("Confirm all detected")')
if (await bulk.count() && await bulk.first().isEnabled()) await bulk.first().click()
const proc = page.locator('button:has-text("Process confirmed")')
if (await proc.count()) await proc.first().click()
await page.waitForFunction(() => /Categorization Complete|Download Excel|failed/i.test(document.body.textContent), null, { timeout: 300000 }).catch(() => {})
await page.waitForTimeout(1500)

// dump every download-ish control
const els = await page.locator('a,button').evaluateAll(nodes =>
  nodes.filter(n => /download|xlsx|excel/i.test(n.textContent + ' ' + (n.getAttribute('href') || '') + ' ' + (n.getAttribute('aria-label') || '')))
    .map(n => ({ tag: n.tagName, text: n.textContent.trim().slice(0, 40), href: n.getAttribute('href'), aria: n.getAttribute('aria-label'), disabled: n.disabled ?? null })))
console.log('DL CONTROLS:', JSON.stringify(els, null, 1))
await shot_dl(page)

async function shot_dl(p) { await p.screenshot({ path: `${OUT}/dl_area.png`, fullPage: true }).catch(() => {}) }

// click the real Download Excel anchor
const a = page.locator('a[href*="/api/jobs/"]').first()
if (await a.count()) {
  const href = await a.getAttribute('href')
  console.log('anchor href:', href)
  const [dl, resp] = await Promise.all([
    page.waitForEvent('download', { timeout: 15000 }).catch(() => null),
    page.waitForResponse(r => /download/.test(r.url()), { timeout: 15000 }).catch(() => null),
    a.click(),
  ])
  console.log('download event:', !!dl, dl ? dl.suggestedFilename() : '')
  console.log('response:', resp ? `${resp.status()} ${resp.url()}` : 'none')
  if (resp) console.log('body head:', (await resp.text().catch(() => '')).slice(0, 120))
} else console.log('no /api/jobs/ anchor found')

console.log('ALL HITS:', hits.slice(-8))
await browser.close()
