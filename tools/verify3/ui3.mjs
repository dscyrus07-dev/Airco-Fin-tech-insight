// verify3 UI e2e on the onb stack (frontend :3400, backend :8401).
// EXTRAS=1: the 7 enable-list banks must appear in the right groups and be
// selectable; one full analyze->confirm->process->report flow per bank;
// screenshots at 360/768/1280. EXTRAS unset: same banks must revert to
// coming_soon / not-selectable.
// Copies of corpus files use neutral names only; the UI renders no statement
// content (filename + bank + verdict only).
import { chromium } from 'playwright'
import { readFileSync, mkdirSync } from 'fs'

const BASE = 'http://localhost:3400'
const API = 'http://localhost:8401'
const OUT = 'X:/Airco Projects/wt-v3/e2e/shots3'
mkdirSync(OUT, { recursive: true })
const EXTRAS = process.env.EXTRAS === '1'
const ENV = {}
for (const line of readFileSync('X:/Airco Projects/Airco Insights fintech/local.env', 'utf-8').split('\n')) {
  const m = line.replace(/\r$/, '').match(/^([A-Z_0-9]+)=(.*)$/)
  if (m) ENV[m[1]] = m[2].trim().replace(/^"|"$/g, '')
}
const USER = ENV.TEST_USER_EMAIL || 'test@airco.com'
const PW = ENV.TEST_USER_PASSWORD || 'Test123!'
const TMP = 'C:/Users/admin/AppData/Local/Temp'

const ENABLE = {
  verified: ['au_sfb', 'bank_of_maharashtra', 'airtel_pb'],
  review_required: ['iob', 'apgv', 'south_indian', 'pnb'],
}
const FLOWS = [
  ['v3_au.pdf', /AU Small Finance/i, 'au'],
  ['v3_bom.pdf', /Maharashtra/i, 'bom'],
  ['v3_airtel.pdf', /Airtel/i, 'airtel'],
  ['v3_iob.pdf', /Indian Overseas/i, 'iob'],
  ['v3_apgv.pdf', /Grameena/i, 'apgv'],
  ['v3_sib.pdf', /South Indian/i, 'sib'],
  ['v3_pnb.pdf', /Punjab National/i, 'pnb'],
]

async function getToken() {
  const body = new URLSearchParams({
    grant_type: 'password', client_id: 'frontend-app',
    client_secret: ENV.KEYCLOAK_CLIENT_SECRET || '',
    username: USER, password: PW, scope: 'openid',
  })
  const tk = await (await fetch('http://localhost:8080/realms/airco-insights/protocol/openid-connect/token',
    { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body })).json()
  if (!tk.access_token) throw new Error('token fail ' + JSON.stringify(tk).slice(0, 120))
  return tk
}

const results = {}
const consoleErrs = []
const bodyText = (page) => page.locator('body').innerText()
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a)

async function shot(page, name) {
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true })
  log('shot:', name)
}

async function analyzeAll(page, files) {
  await page.goto(BASE + '/dashboard', { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(1500)
  await page.locator('input[type="file"]').setInputFiles(files)
  await page.waitForTimeout(400)
  await page.locator('button:has-text("Analyze")').first().click()
  await page.waitForFunction(
    () => /Confirm all detected|is not enabled yet|isn't fully supported|Why we think so|Use selected bank/i.test(document.body.textContent),
    null, { timeout: 120000 })
  await page.waitForTimeout(800)
}

async function processAll(page) {
  const btn = page.locator('button:has-text("Process confirmed")')
  try {
    await btn.first().waitFor({ state: 'visible', timeout: 60000 })
    await page.waitForFunction(
      () => { const b = [...document.querySelectorAll('button')].find(x => x.textContent.includes('Process confirmed')); return b && !b.disabled },
      null, { timeout: 60000 })
    await btn.first().click()
  } catch (e) { log('processAll: nothing processable'); return }
  const t0 = Date.now()
  while (Date.now() - t0 < 240000) {
    const txt = await bodyText(page)
    if (/Report/i.test(txt) && (await page.locator('button:has-text("New Statement")').count())) break
    await page.waitForTimeout(2500)
  }
  try {
    await page.waitForFunction(
      () => /Transactions|Monthly Analysis|Independently verified|Needs review|not processed|needs review/i.test(document.body.textContent),
      null, { timeout: 90000 })
  } catch {}
}

async function startOver(page) {
  const ns = page.locator('button:has-text("New Statement")')
  if (await ns.count()) { await ns.first().click(); await page.waitForTimeout(800); return }
  await page.goto(BASE + '/dashboard', { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(1200)
}

const browser = await chromium.launch({ channel: 'chrome' })
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } })
const page = await ctx.newPage()
page.on('pageerror', (e) => consoleErrs.push('pageerror: ' + String(e).slice(0, 200)))
page.on('console', (m) => { if (m.type() === 'error') consoleErrs.push(m.text().slice(0, 200)) })

const tk = await getToken()
await page.goto(BASE, { waitUntil: 'domcontentloaded' })
await page.evaluate(([at, rt]) => {
  sessionStorage.setItem('kc_token', at)
  sessionStorage.setItem('kc_refresh_token', rt || '')
  document.cookie = `kc_token=${encodeURIComponent(at)}; Path=/; SameSite=Lax`
  if (rt) document.cookie = `kc_refresh_token=${encodeURIComponent(rt)}; Path=/; SameSite=Lax`
}, [tk.access_token, tk.refresh_token || ''])

// ---------- catalog states (Node-side; localhost:8401 hangs on IPv6) ----------
const catalog = await (await fetch('http://127.0.0.1:8401/api/statements/banks',
  { headers: { Authorization: 'Bearer ' + tk.access_token } })).json()
results.servable_count = catalog.banks.length
results.all_banks_count = catalog.all_banks.length
for (const id of [...ENABLE.verified, ...ENABLE.review_required]) {
  const b = catalog.all_banks.find(x => x.id === id) || {}
  results['state_' + id] = b.support_state
  results['selectable_' + id] = catalog.banks.some(x => x.id === id)
}
log('catalog:', results.servable_count, 'servable /', results.all_banks_count, 'all')
log('states:', JSON.stringify(Object.fromEntries(Object.entries(results).filter(([k]) => k.startsWith('state_')))))

// ---------- panel + picker ----------
await page.goto(BASE + '/dashboard', { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(2000)
const panelToggle = page.locator('summary,button').filter({ hasText: /Supported banks|bank list/i }).first()
if (await panelToggle.count()) { await panelToggle.click().catch(() => {}); await page.waitForTimeout(400) }
const fullToggle = page.locator('summary,button').filter({ hasText: /full bank list/i }).first()
if (await fullToggle.count()) { await fullToggle.click().catch(() => {}); await page.waitForTimeout(400) }
let txt = await bodyText(page)
results.panel_all_groups = /Verified/i.test(txt) && /Review required/i.test(txt) && /Coming soon/i.test(txt)
await shot(page, EXTRAS ? 'v3-panel-1280-extras' : 'v3-panel-1280')
for (const [w, h] of [[768, 900], [360, 800]]) {
  await page.setViewportSize({ width: w, height: h })
  await page.waitForTimeout(500)
  await shot(page, `v3-panel-${w}${EXTRAS ? '-extras' : ''}`)
  results['no_hscroll_' + w] = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)
}
await page.setViewportSize({ width: 1280, height: 900 })
results.picker_optgroups = await page.locator('optgroup').count()
results.picker_disabled = await page.locator('select option[disabled]').count()

if (EXTRAS) {
  // ---------- one flow per enabled bank ----------
  for (const [file, bankRe, tag] of FLOWS) {
    log('flow:', tag)
    try {
      await analyzeAll(page, [`${TMP}/${file}`])
      txt = await bodyText(page)
      results[tag + '_detected'] = bankRe.test(txt)
      results[tag + '_review_tag'] = /always needs review/i.test(txt)
      await shot(page, `v3-review-${tag}-1280`)
      const rowConfirm = page.locator('button').filter({ hasText: /^Confirm$/ }).first()
      if (await rowConfirm.count()) { await rowConfirm.click(); await page.waitForTimeout(800) }
      const bulk = page.locator('button:has-text("Confirm all detected")')
      if (await bulk.count() && await bulk.first().isEnabled()) { await bulk.first().click(); await page.waitForTimeout(800) }
      await processAll(page)
      txt = await bodyText(page)
      results[tag + '_report'] = /Report/i.test(txt) && bankRe.test(txt)
      results[tag + '_verified_tag'] = /Independently verified\s*:?\s*yes|VERIFIED/i.test(txt)
      results[tag + '_needs_review_notice'] = /needs review|Needs review/i.test(txt)
      await shot(page, `v3-result-${tag}-1280`)
    } catch (e) {
      results[tag + '_error'] = String(e).slice(0, 140)
    }
    await startOver(page)
  }
}

console.log('\n=== RESULTS ===')
for (const [k, v] of Object.entries(results)) console.log(k, '=', v)
console.log('console errors:', consoleErrs.length ? consoleErrs.slice(0, 10) : 'none')
await browser.close()
