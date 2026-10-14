// rollout UI smoke on the onb stack (frontend :3400, backend :8401).
// 14 flows (one file per served bank, neutral names), a 5-file mixed batch
// (one review-only, one unsupported, one non-enabled, two more), widths
// 360/1280. Screenshots cover the bank-selection/status areas only; the UI
// renders filename + bank + verdict, never statement content.
import { chromium } from 'playwright'
import { readFileSync, mkdirSync } from 'fs'

const BASE = 'http://localhost:3400'
const OUT = 'X:/Airco Projects/wt-ro/e2e/shots_ro'
mkdirSync(OUT, { recursive: true })
const ENV = {}
for (const line of readFileSync('X:/Airco Projects/Airco Insights fintech/local.env', 'utf-8').split('\n')) {
  const m = line.replace(/\r$/, '').match(/^([A-Z_0-9]+)=(.*)$/)
  if (m) ENV[m[1]] = m[2].trim().replace(/^"|"$/g, '')
}
const USER = ENV.TEST_USER_EMAIL || 'test@airco.com'
const PW = ENV.TEST_USER_PASSWORD || 'Test123!'
const TMP = 'C:/Users/admin/AppData/Local/Temp/ro_ui'

const SERVED = {
  verified: ['hdfc', 'sbi', 'axis', 'idfc', 'paytm', 'citibank', 'city_union', 'au_sfb', 'bank_of_maharashtra', 'airtel_pb'],
  review_required: ['iob', 'apgv', 'south_indian', 'pnb'],
}
const FLOWS = [
  ['ro_hdfc.pdf', /HDFC/i, 'hdfc'],
  ['ro_sbi.pdf', /State Bank|SBI/i, 'sbi'],
  ['ro_axis.pdf', /Axis/i, 'axis'],
  ['ro_idfc.pdf', /IDFC/i, 'idfc'],
  ['ro_paytm.pdf', /Paytm/i, 'paytm'],
  ['ro_citibank.pdf', /Citibank|Citi/i, 'citi'],
  ['ro_city_union.pdf', /City Union/i, 'cityu'],
  ['ro_au_sfb.pdf', /AU Small Finance/i, 'au'],
  ['ro_bank_of_maharashtra.pdf', /Maharashtra/i, 'bom'],
  ['ro_airtel_pb.pdf', /Airtel/i, 'airtel'],
  ['ro_iob.pdf', /Indian Overseas/i, 'iob'],
  ['ro_apgv.pdf', /Grameena/i, 'apgv'],
  ['ro_south_indian.pdf', /South Indian/i, 'sib'],
  ['ro_pnb.pdf', /Punjab National/i, 'pnb'],
]
const MIXED = [
  'ro_iob.pdf',        // review-only
  'ro_yes.pdf',        // unsupported
  'ro_federal.pdf',    // non-enabled (coming_soon)
  'ro_hdfc.pdf',       // verified
  'ro_kotak.pdf',      // legacy
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
const shot = (page, name) => page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true }).then(() => log('shot:', name))

async function analyzeAll(page, files) {
  await page.goto(BASE + '/dashboard', { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(1500)
  await page.locator('input[type="file"]').setInputFiles(files)
  await page.waitForTimeout(400)
  await page.locator('button:has-text("Analyze")').first().click()
  await page.waitForFunction(
    () => /Confirm all detected|is not enabled yet|isn't fully supported|Why we think so|Use selected bank/i.test(document.body.textContent),
    null, { timeout: 180000 })
  await page.waitForTimeout(800)
}

async function processAll(page) {
  const btn = page.locator('button:has-text("Process confirmed")')
  try {
    await btn.first().waitFor({ state: 'visible', timeout: 90000 })
    await page.waitForFunction(
      () => { const b = [...document.querySelectorAll('button')].find(x => x.textContent.includes('Process confirmed')); return b && !b.disabled },
      null, { timeout: 90000 })
    await btn.first().click()
  } catch (e) { log('processAll: nothing processable'); return }
  const t0 = Date.now()
  while (Date.now() - t0 < 300000) {
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

// catalog states (Node-side fetch; page-side localhost:8401 hangs on IPv6)
const catalog = await (await fetch('http://127.0.0.1:8401/api/statements/banks',
  { headers: { Authorization: 'Bearer ' + tk.access_token } })).json()
results.servable_count = catalog.banks.length
results.all_banks_count = catalog.all_banks.length
for (const id of [...SERVED.verified, ...SERVED.review_required]) {
  const b = catalog.all_banks.find(x => x.id === id) || {}
  results['state_' + id] = b.support_state
  results['served_' + id] = catalog.banks.some(x => x.id === id && x.v2_served)
}
for (const id of ['yes', 'federal', 'kotak']) {
  const b = catalog.all_banks.find(x => x.id === id) || {}
  results['state_' + id] = b.support_state
}
log('catalog:', results.servable_count, 'servable /', results.all_banks_count, 'all')
log('states:', JSON.stringify(Object.fromEntries(Object.entries(results).filter(([k]) => k.startsWith('state_')))))

// panel + picker at 1280 and 360
await page.goto(BASE + '/dashboard', { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(2000)
const panelToggle = page.locator('summary,button').filter({ hasText: /Supported banks|bank list/i }).first()
if (await panelToggle.count()) { await panelToggle.click().catch(() => {}); await page.waitForTimeout(400) }
const fullToggle = page.locator('summary,button').filter({ hasText: /full bank list/i }).first()
if (await fullToggle.count()) { await fullToggle.click().catch(() => {}); await page.waitForTimeout(400) }
let txt = await bodyText(page)
results.panel_groups = /Verified/i.test(txt) && /Review required/i.test(txt) && /Coming soon/i.test(txt) && /Legacy/i.test(txt) && /not supported/i.test(txt)
results.panel_shows_rollout_comingsoon = /AU Small Finance[\s\S]{0,80}coming soon|Airtel[\s\S]{0,80}coming soon|Maharashtra[\s\S]{0,80}coming soon/i.test(txt)
await shot(page, 'ro-panel-1280')
await page.setViewportSize({ width: 360, height: 800 })
await page.waitForTimeout(500)
await shot(page, 'ro-panel-360')
results.no_hscroll_360 = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)
await page.setViewportSize({ width: 1280, height: 900 })
results.picker_optgroups = await page.locator('optgroup').count()
results.picker_disabled = await page.locator('select option[disabled]').count()

// one flow per served bank
for (const [file, bankRe, tag] of FLOWS) {
  log('flow:', tag)
  try {
    await analyzeAll(page, [`${TMP}/${file}`])
    txt = await bodyText(page)
    results[tag + '_detected'] = bankRe.test(txt)
    results[tag + '_coming_soon_shown'] = new RegExp(bankRe.source + '[\\s\\S]{0,120}coming soon', 'i').test(txt)
    await shot(page, `ro-review-${tag}-1280`)
    const rowConfirm = page.locator('button').filter({ hasText: /^Confirm$/ }).first()
    if (await rowConfirm.count()) { await rowConfirm.click(); await page.waitForTimeout(800) }
    const bulk = page.locator('button:has-text("Confirm all detected")')
    if (await bulk.count() && await bulk.first().isEnabled()) { await bulk.first().click(); await page.waitForTimeout(800) }
    await processAll(page)
    txt = await bodyText(page)
    results[tag + '_report'] = /Report/i.test(txt)
    results[tag + '_verdict_seen'] = /VERIFIED|Needs review|needs review/i.test(txt)
    await shot(page, `ro-result-${tag}-1280`)
  } catch (e) {
    results[tag + '_error'] = String(e).slice(0, 140)
  }
  await startOver(page)
}

// mixed batch: 5 files
log('mixed batch')
try {
  await analyzeAll(page, MIXED.map(f => `${TMP}/${f}`))
  txt = await bodyText(page)
  results.mixed_iob_review_tag = /Indian Overseas[\s\S]{0,120}(needs review|confirm)/i.test(txt)
  results.mixed_yes_notenabled = /Yes Bank[\s\S]{0,160}not enabled/i.test(txt)
  results.mixed_federal_notenabled = /Federal[\s\S]{0,160}(not enabled|coming soon)/i.test(txt)
  results.mixed_hdfc_detected = /HDFC/i.test(txt)
  await shot(page, 'ro-mixed-1280')
  // non-enabled must NOT be selectable: YES/FEDERAL rows carry no Confirm
  results.mixed_confirmable = await page.locator('button').filter({ hasText: /^Confirm$/ }).count()
  await page.setViewportSize({ width: 360, height: 800 })
  await page.waitForTimeout(400)
  await shot(page, 'ro-mixed-360')
  results.mixed_no_hscroll_360 = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)
  await page.setViewportSize({ width: 1280, height: 900 })
} catch (e) {
  results.mixed_error = String(e).slice(0, 160)
}

console.log('\n=== RESULTS ===')
for (const [k, v] of Object.entries(results)) console.log(k, '=', v)
console.log('console errors:', consoleErrs.length ? consoleErrs.slice(0, 10) : 'none')
await browser.close()
