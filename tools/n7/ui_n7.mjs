// n7 UI smoke on the onb stack (frontend :3400, backend :8401).
// One flow per N7 candidate bank, bank-panel counts vs API, review-only labels,
// UNSUPPORTED + coming-soon rows, mixed batch, widths 360/1280, console errors.
// Screenshots cover status areas only; filenames are neutral.
import { chromium } from 'playwright'
import { readFileSync, mkdirSync } from 'fs'

const BASE = 'http://localhost:3400'
const OUT = 'X:/Airco Projects/wt-n7/e2e/shots_n7'
mkdirSync(OUT, { recursive: true })
const ENV = {}
for (const line of readFileSync('X:/Airco Projects/Airco Insights fintech/local.env', 'utf-8').split('\n')) {
  const m = line.replace(/\r$/, '').match(/^([A-Z_0-9]+)=(.*)$/)
  if (m) ENV[m[1]] = m[2].trim().replace(/^"|"$/g, '')
}
const USER = ENV.TEST_USER_EMAIL || 'test@airco.com'
const PW = ENV.TEST_USER_PASSWORD || 'Test123!'
const TMP = 'C:/Users/admin/AppData/Local/Temp/n7_ui'

const CANDS = ['bank_of_baroda', 'canara', 'icici', 'indian_bank', 'karnataka', 'kotak']
const FLOWS = [
  ['n7_bank_of_baroda.pdf', /Bank of Baroda|Baroda/i, 'bob'],
  ['n7_canara.pdf', /Canara/i, 'canara'],
  ['n7_icici.pdf', /ICICI/i, 'icici'],
  ['n7_indian_bank.pdf', /Indian Bank/i, 'indian_bank'],
  ['n7_karnataka.pdf', /Karnataka/i, 'karnataka'],
  ['n7_kotak.pdf', /Kotak/i, 'kotak'],
]
const MIXED = ['n7_iob.pdf', 'n7_yes.pdf', 'n7_federal.pdf', 'n7_hdfc.pdf', 'n7_canara.pdf']

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

// catalog: candidate states + counts
const catalog = await (await fetch('http://127.0.0.1:8401/api/statements/banks',
  { headers: { Authorization: 'Bearer ' + tk.access_token } })).json()
results.servable_count = catalog.banks.length
results.all_banks_count = catalog.all_banks.length
for (const id of CANDS) {
  const b = catalog.all_banks.find(x => x.id === id) || {}
  results['state_' + id] = b.support_state
  results['served_' + id] = catalog.banks.some(x => x.id === id && x.v2_served)
}
for (const id of ['union', 'bank_of_india', 'federal', 'yes']) {
  const b = catalog.all_banks.find(x => x.id === id) || {}
  results['state_' + id] = b.support_state
}
log('catalog:', results.servable_count, 'servable /', results.all_banks_count, 'all')
log('cand states:', JSON.stringify(CANDS.map(id => [id, results['state_' + id], results['served_' + id]])))

// bank panel vs API counts at 1280 + 360
await page.goto(BASE + '/dashboard', { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(2000)
const panelToggle = page.locator('summary,button').filter({ hasText: /Supported banks|bank list/i }).first()
if (await panelToggle.count()) { await panelToggle.click().catch(() => {}); await page.waitForTimeout(400) }
const fullToggle = page.locator('summary,button').filter({ hasText: /full bank list/i }).first()
if (await fullToggle.count()) { await fullToggle.click().catch(() => {}); await page.waitForTimeout(400) }
let txt = await bodyText(page)
results.panel_groups = /Verified/i.test(txt) && /Review required/i.test(txt) && /Coming soon/i.test(txt) && /Legacy/i.test(txt) && /not supported/i.test(txt)
for (const id of CANDS) results['panel_' + id] = new RegExp(id === 'bank_of_baroda' ? 'Baroda' : id === 'indian_bank' ? 'Indian Bank' : id, 'i').test(txt)
results.panel_verified_api = catalog.banks.filter(b => b.support_state === 'verified' || b.v2_served).length
await shot(page, 'n7-panel-1280')
await page.setViewportSize({ width: 360, height: 800 })
await page.waitForTimeout(500)
await shot(page, 'n7-panel-360')
results.no_hscroll_360 = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)
await page.setViewportSize({ width: 1280, height: 900 })
results.picker_optgroups = await page.locator('optgroup').count()

// one flow per candidate
for (const [file, bankRe, tag] of FLOWS) {
  log('flow:', tag)
  try {
    await analyzeAll(page, [`${TMP}/${file}`])
    txt = await bodyText(page)
    results[tag + '_detected'] = bankRe.test(txt)
    await shot(page, `n7-review-${tag}-1280`)
    const sel = page.locator('select').first()
    if (await sel.count() && !(await page.locator('button').filter({ hasText: /^Confirm$/ }).count())) {
      await sel.selectOption({ label: new RegExp(bankRe) }).catch(async () => {
        const opts = await sel.locator('option').allInnerTexts()
        const hit = opts.findIndex(o => bankRe.test(o))
        if (hit >= 0) await sel.selectOption({ index: hit })
      })
      await page.waitForTimeout(400)
      const useSel = page.locator('button:has-text("Use selected bank")').first()
      if (await useSel.count()) { await useSel.click(); await page.waitForTimeout(800) }
    }
    const rowConfirm = page.locator('button').filter({ hasText: /^Confirm$/ }).first()
    if (await rowConfirm.count()) { await rowConfirm.click(); await page.waitForTimeout(800) }
    const bulk = page.locator('button:has-text("Confirm all detected")')
    if (await bulk.count() && await bulk.first().isEnabled()) { await bulk.first().click(); await page.waitForTimeout(800) }
    await processAll(page)
    txt = await bodyText(page)
    results[tag + '_report'] = /Report/i.test(txt)
    results[tag + '_verdict_seen'] = /VERIFIED|Needs review|needs review/i.test(txt)
    await shot(page, `n7-result-${tag}-1280`)
  } catch (e) {
    results[tag + '_error'] = String(e).slice(0, 140)
  }
  await startOver(page)
}

// mixed batch
log('mixed batch')
try {
  await analyzeAll(page, MIXED.map(f => `${TMP}/${f}`))
  txt = await bodyText(page)
  results.mixed_iob_review_tag = /Indian Overseas[\s\S]{0,120}(needs review|confirm)/i.test(txt)
  results.mixed_yes_notenabled = /Yes Bank[\s\S]{0,160}not enabled/i.test(txt)
  results.mixed_federal_notenabled = /Federal[\s\S]{0,160}(not enabled|coming soon)/i.test(txt)
  results.mixed_hdfc_detected = /HDFC/i.test(txt)
  results.mixed_canara_detected = /Canara/i.test(txt)
  await shot(page, 'n7-mixed-1280')
  results.mixed_confirmable = await page.locator('button').filter({ hasText: /^Confirm$/ }).count()
  await page.setViewportSize({ width: 360, height: 800 })
  await page.waitForTimeout(400)
  await shot(page, 'n7-mixed-360')
  results.mixed_no_hscroll_360 = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)
  await page.setViewportSize({ width: 1280, height: 900 })
} catch (e) {
  results.mixed_error = String(e).slice(0, 160)
}

console.log('\n=== RESULTS ===')
for (const [k, v] of Object.entries(results)) console.log(k, '=', v)
console.log('console errors:', consoleErrs.length ? consoleErrs.slice(0, 10) : 'none')
await browser.close()
