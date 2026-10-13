// UI bank-states E2E on the onb stack (frontend :3400, backend :8401).
// Synthetic PDFs only. Verifies: grouped picker, per-state flows, not-enabled
// rows, review-required notice, screenshots at 360/768/1280.
// Phase A (extras unset): verified HDFC, legacy Kotak override, YES/RBL not-enabled, mixed batch.
// Phase B (run with EXTRAS=1 after backend recreated with ONB_EXTRA_SERVE_BANKS=iob):
// review-required IOB flow + persistent notice.
import { chromium } from 'playwright'
import { readFileSync, mkdirSync } from 'fs'

const BASE = 'http://localhost:3400'
const API = 'http://localhost:8401'
const OUT = 'X:/Airco Projects/wt-ui/e2e/shots'
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
const UE = 'X:/Airco Projects/wt-ue/e2e_pdfs'

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

async function shot(page, name) {
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true })
  console.log('shot:', name)
}

async function analyzeAll(page, files) {
  await page.goto(BASE + '/dashboard', { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(1500)
  const input = page.locator('input[type="file"]')
  await input.setInputFiles(files)
  await page.waitForTimeout(400)
  await page.locator('button:has-text("Analyze")').first().click()
  await page.waitForFunction(
    () => /Confirm all detected|is not enabled yet|isn't fully supported|Why we think so|Use selected bank/i.test(document.body.textContent),
    null, { timeout: 120000 })
  await page.waitForTimeout(800)
}

async function confirmAll(page) {
  const btn = page.locator('button:has-text("Confirm all detected")')
  if (await btn.count() && await btn.first().isEnabled()) {
    await btn.first().click()
    try {
      await page.waitForFunction(
        () => /Process confirmed \([1-9]/.test(document.body.textContent), null, { timeout: 60000 })
    } catch {}
    await page.waitForTimeout(300)
  }
}

async function processAll(page) {
  const btn = page.locator('button:has-text("Process confirmed")')
  try {
    await btn.first().waitFor({ state: 'visible', timeout: 60000 })
    await page.waitForFunction(
      () => { const b = [...document.querySelectorAll('button')].find(x => x.textContent.includes('Process confirmed')); return b && !b.disabled },
      null, { timeout: 60000 })
    await btn.first().click()
  } catch (e) { console.log('processAll: no processable docs or timeout'); return }
  const t0 = Date.now()
  while (Date.now() - t0 < 180000) {
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
  const so = page.locator('button:has-text("Start over")')
  if (await ns.count()) { await ns.first().click(); await page.waitForTimeout(600); return }
  if (await so.count()) { await so.first().click(); await page.waitForTimeout(600); return }
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

// ---------- catalog sanity via the page's own fetch ----------
const catalog = await page.evaluate(async (api) => {
  const t = sessionStorage.getItem('kc_token')
  const r = await fetch(api + '/api/statements/banks', { headers: { Authorization: 'Bearer ' + t } })
  return r.json()
}, API)
results.catalog_all_banks = Array.isArray(catalog.all_banks) ? catalog.all_banks.length : -1
results.catalog_banks = catalog.banks.length
results.iob_state = (catalog.all_banks.find(b => b.id === 'iob') || {}).support_state
console.log('catalog:', results.catalog_banks, 'servable /', results.catalog_all_banks, 'all; iob:', results.iob_state)

// ---------- leg A0: upload page — support panel + grouped picker ----------
await page.goto(BASE + '/dashboard', { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(2000)
let txt = await bodyText(page)
results.upload_has_supported_copy = /Supported bank/i.test(txt)
// open the supported-banks panel (details/summary or button)
const panelToggle = page.locator('summary,button').filter({ hasText: /Supported banks|supported banks|bank list/i }).first()
if (await panelToggle.count()) { await panelToggle.click().catch(() => {}); await page.waitForTimeout(400) }
txt = await bodyText(page)
results.panel_groups = /Verified/i.test(txt) && /Coming soon/i.test(txt)
results.panel_has_unsupported_visible = /Deutsche|RBL|SBM|TMB|Fino/i.test(txt)
await shot(page, EXTRAS ? 'panel-1280-extras' : 'panel-1280')
// picker: check a bank select exists with optgroups
const detSum = page.locator('summary').filter({ hasText: /Details/i }).first()
if (await detSum.count()) { await detSum.click().catch(() => {}); await page.waitForTimeout(400) }
try {
  await page.waitForFunction(() => document.querySelectorAll('optgroup').length > 0, null, { timeout: 15000 })
} catch {}
results.picker_optgroups = await page.locator('optgroup').count()
results.picker_disabled_opts = await page.locator('select option[disabled]').count()
console.log('optgroups:', results.picker_optgroups, 'disabled opts:', results.picker_disabled_opts)

// narrow screenshots for responsiveness
await page.setViewportSize({ width: 768, height: 900 })
await page.waitForTimeout(500)
await shot(page, EXTRAS ? 'panel-768-extras' : 'panel-768')
results.no_hscroll_768 = await page.evaluate(() => document.documentElement.scrollWidth <= 769)
await page.setViewportSize({ width: 360, height: 800 })
await page.waitForTimeout(500)
await shot(page, EXTRAS ? 'panel-360-extras' : 'panel-360')
results.no_hscroll_360 = await page.evaluate(() => document.documentElement.scrollWidth <= 361)
await page.setViewportSize({ width: 1280, height: 900 })

if (!EXTRAS) {
  // ---------- leg A1: verified flow (hdfc) ----------
  await analyzeAll(page, [`${UE}/hdfc_ok.pdf`])
  txt = await bodyText(page)
  results.a1_detected = /HDFC Bank/.test(txt)
  await shot(page, 'review-hdfc-1280')
  await confirmAll(page)
  await processAll(page)
  txt = await bodyText(page)
  results.a1_report = /HDFC|Report/i.test(txt)
  await shot(page, 'result-hdfc-1280')
  await startOver(page)

  // ---------- leg A2: legacy flow (kotak manual select) ----------
  await analyzeAll(page, [`${UE}/kotak_override.pdf`])
  txt = await bodyText(page)
  const kotakSel = page.locator('select').first()
  if (await kotakSel.count()) {
    await kotakSel.selectOption({ label: /Kotak/i }).catch(async () => {
      await kotakSel.selectOption({ value: 'kotak' }).catch(() => {})
    })
    await page.waitForTimeout(500)
    txt = await bodyText(page)
    results.a2_override_warn = /may fail|validation|overrid/i.test(txt)
  }
  await shot(page, 'review-kotak-1280')
  await confirmAll(page); await processAll(page)
  txt = await bodyText(page)
  results.a2_report = /Report|Kotak/i.test(txt)
  await shot(page, 'result-kotak-1280')
  await startOver(page)

  // ---------- leg A3: not-enabled rows (YES coming_soon + RBL unsupported) ----------
  await analyzeAll(page, [`${TMP}/synth_yes.pdf`, `${TMP}/synth_rbl.pdf`])
  txt = await bodyText(page)
  results.a3_yes_not_enabled = /Yes Bank is not enabled yet/i.test(txt)
  results.a3_rbl_not_enabled = /RBL Bank is not enabled yet/i.test(txt)
  results.a3_no_confirm = !(await page.locator('button:has-text("Confirm all detected")').first().isEnabled().catch(() => false))
  await shot(page, 'review-notenabled-1280')
  await page.setViewportSize({ width: 360, height: 800 }); await page.waitForTimeout(400)
  await shot(page, 'review-notenabled-360')
  results.no_hscroll_review_360 = await page.evaluate(() => document.documentElement.scrollWidth <= 361)
  await page.setViewportSize({ width: 1280, height: 900 })
  await startOver(page)

  // ---------- leg A4: mixed batch ----------
  await analyzeAll(page, [`${UE}/hdfc_ok.pdf`, `${TMP}/synth_yes.pdf`, `${UE}/kotak_override.pdf`])
  txt = await bodyText(page)
  results.a4_mixed = /HDFC Bank/.test(txt) && /not enabled yet/i.test(txt)
  await shot(page, 'review-mixed-768')
  await confirmAll(page); await processAll(page)
  txt = await bodyText(page)
  results.a4_processed = /Report/i.test(txt)
  await startOver(page)
} else {
  // ---------- leg B1: review_required flow (iob under extras) ----------
  results.b1_iob_catalog = results.iob_state // expect 'review_required'
  await analyzeAll(page, [`${TMP}/synth_iob.pdf`])
  txt = await bodyText(page)
  results.b1_detected_or_review = /Indian Overseas/i.test(txt) && /REVIEW/i.test(txt)
  results.b1_needs_review_tag = /always needs review/i.test(txt)
  await shot(page, 'review-iob-extras-1280')
  // REVIEW rows confirm individually (no bulk confirm)
  const rowConfirm = page.locator('button').filter({ hasText: /^Confirm$/ }).first()
  if (await rowConfirm.count()) { await rowConfirm.click(); await page.waitForTimeout(800) }
  await confirmAll(page); await processAll(page)
  txt = await bodyText(page)
  results.b1_needs_review_notice = /needs review|Needs review/i.test(txt)
  await shot(page, 'result-iob-extras-1280')
  await page.setViewportSize({ width: 768, height: 900 }); await page.waitForTimeout(400)
  await shot(page, 'result-iob-extras-768')
  await startOver(page)

  // ---------- leg B2: verified still works under extras ----------
  await analyzeAll(page, [`${UE}/hdfc_ok.pdf`])
  txt = await bodyText(page)
  results.b2_hdfc_detected = /HDFC Bank/.test(txt)
  await confirmAll(page); await processAll(page)
  txt = await bodyText(page)
  results.b2_report = /Report/i.test(txt)
}

console.log('\n=== RESULTS ===')
for (const [k, v] of Object.entries(results)) console.log(k, '=', v)
console.log('console errors:', consoleErrs.length ? consoleErrs.slice(0, 10) : 'none')
await browser.close()
