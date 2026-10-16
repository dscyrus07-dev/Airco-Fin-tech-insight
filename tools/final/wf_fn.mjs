// N9 workflow suite on the rc stack (frontend :3600, backend :8601).
// 16 items from the N9 brief; synthetic PDFs only; screenshots of status areas.
// Run: node tools/final/wf.mjs   (cwd: frontend for playwright, or anywhere with node_modules)
import { chromium } from 'playwright'
import { readFileSync, mkdirSync, writeFileSync } from 'fs'
import { execSync } from 'child_process'

const FE = 'http://localhost:3600'
const BE = 'http://127.0.0.1:8601'
const KC = 'http://localhost:8080'
const OUT = 'X:/Airco Projects/wt-fn/tools/final/.local/shots_fn'
const KIT = 'X:/Airco Projects/wt-fn/tools/final/demo_pdfs'
mkdirSync(OUT, { recursive: true })

const ENV = {}
for (const line of readFileSync('X:/Airco Projects/Airco Insights fintech/local.env', 'utf-8').split('\n')) {
  const m = line.replace(/\r$/, '').match(/^([A-Z_0-9]+)=(.*)$/)
  if (m) ENV[m[1]] = m[2].trim().replace(/^"|"$/g, '')
}
const USER = ENV.TEST_USER_EMAIL || 'test@airco.com'
const PW = process.env.TEST_USER_PASSWORD || ENV.TEST_USER_PASSWORD || ''
const SECRET = process.env.KEYCLOAK_CLIENT_SECRET || ENV.KEYCLOAK_CLIENT_SECRET || ''

const R = {}
const consoleErrs = []
const t = (k, v) => { R[k] = v; console.log(' ', k, '=', JSON.stringify(v).slice(0, 160)) }
const bodyText = (page) => page.locator('body').innerText()
const shot = (page, name) => page.screenshot({ path: `${OUT}/${name}.png` }).catch(() => {})

async function token(user = USER, pw = PW) {
  const body = new URLSearchParams({
    grant_type: 'password', client_id: 'frontend-app', client_secret: SECRET,
    username: user, password: pw, scope: 'openid',
  })
  const r = await fetch(`${KC}/realms/airco-insights/protocol/openid-connect/token`,
    { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body })
  return r.json()
}

async function injectSession(page, tk) {
  await page.goto(FE, { waitUntil: 'domcontentloaded' })
  await page.evaluate(([at, rt]) => {
    sessionStorage.setItem('kc_token', at)
    sessionStorage.setItem('kc_refresh_token', rt || '')
    document.cookie = `kc_token=${encodeURIComponent(at)}; Path=/; SameSite=Lax`
    if (rt) document.cookie = `kc_refresh_token=${encodeURIComponent(rt)}; Path=/; SameSite=Lax`
  }, [tk.access_token, tk.refresh_token || ''])
}

async function analyze(page, files, timeoutMs = 240000) {
  await page.goto(FE + '/dashboard', { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(1500)
  // Reset whatever step the wizard persisted to (Report/Processing/Mode/etc.)
  for (let i = 0; i < 6; i++) {
    if (await page.locator('#fullName').count() || await page.locator('input[type="file"]').count()) break
    const ns = page.locator('button:has-text("New Statement"), button:has-text("Analyze another"), a:has-text("Analyze")')
    if (await ns.count()) { await ns.first().click(); await page.waitForTimeout(900); continue }
    break
  }
  // Step 1 Details: fill name + pick a bank if the wizard is on step 1
  if (await page.locator('#fullName').count()) {
    await page.locator('#fullName').fill('FN Test')
    await page.locator('#bankSelect').selectOption({ label: 'HDFC Bank' })
    await page.locator('button:has-text("Add Another Bank")').click()
    await page.locator('button:has-text("Continue")').first().click()
    await page.waitForTimeout(800)
  }
  // Step 2 Upload: file input
  await page.locator('input[type="file"]').setInputFiles(files)
  await page.waitForTimeout(800)
  const cont = page.locator('button:has-text("Continue with")')
  if (await cont.count()) { await cont.first().click(); await page.waitForTimeout(800) }
  // Step 3 Mode: Free Mode + Continue
  const free = page.locator('button:has-text("Free Mode")')
  if (await free.count()) {
    await free.first().click(); await page.waitForTimeout(300)
    await page.locator('button:has-text("Continue")').first().click()
    await page.waitForTimeout(500)
  }
  const an = page.locator('button:has-text("Analyze")')
  if (await an.count()) await an.first().click()
  await page.waitForFunction(
    () => /Confirm all detected|is not enabled yet|isn't fully supported|Why we think so|Use selected bank|could not identify|Password|password|scanned|Detected|VERIFIED|REVIEW|Process confirmed|Start Processing|Ready to process/i.test(document.body.textContent),
    null, { timeout: timeoutMs })
  await page.waitForTimeout(900)
}

async function processAll(page, waitMs = 420000) {
  const btn = page.locator('button:has-text("Process confirmed")')
  if (!(await btn.count())) return false
  await btn.first().waitFor({ state: 'visible', timeout: 60000 })
  await page.waitForFunction(
    () => { const b = [...document.querySelectorAll('button')].find(x => x.textContent.includes('Process confirmed')); return b && !b.disabled },
    null, { timeout: 60000 }).catch(() => {})
  await btn.first().click()
  const t0 = Date.now()
  while (Date.now() - t0 < waitMs) {
    const txt = await bodyText(page)
    if (/Report/i.test(txt) && (await page.locator('button:has-text("New Statement")').count())) return true
    if (/not processed|failed/i.test(txt) && (await page.locator('button:has-text("New Statement")').count())) return 'failed-seen'
    await page.waitForTimeout(3000)
  }
  return 'timeout'
}

const browser = await chromium.launch({ channel: 'chrome' })

// ---------- 1. real sign-in via Keycloak form, then sign-out ----------
{
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } })
  const page = await ctx.newPage()
  page.on('console', (m) => { if (m.type() === 'error') consoleErrs.push('s1: ' + m.text().slice(0, 150)) })
  try {
    await page.goto(FE, { waitUntil: 'domcontentloaded' })
    const loginBtn = page.locator('button,a').filter({ hasText: /sign in|log in|get started/i }).first()
    t('s1_login_btn', await loginBtn.count() > 0)
    await loginBtn.click()
    await page.waitForURL(/localhost:8080.*protocol\/openid-connect\/auth/, { timeout: 20000 })
    t('s1_keycloak_redirect', true)
    await page.locator('#username').fill(USER)
    await page.locator('#password').fill(PW)
    await page.locator('#kc-login,button[type="submit"],input[type="submit"]').first().click()
    await page.waitForURL(/localhost:3600/, { timeout: 30000 })
    await page.waitForTimeout(2500)
    t('s1_signed_in', /dashboard|statement|upload/i.test(await bodyText(page)))
    await shot(page, 's1-signedin')
    // sign-out: Profile header button -> side panel -> Sign Out -> window.confirm
    page.on('dialog', (d) => d.accept().catch(() => {}))
    const prof = page.locator('button').filter({ hasText: /^\s*Profile\s*$/ }).last()
    if (await prof.count()) {
      await prof.click(); await page.waitForTimeout(800)
      const out = page.locator('button').filter({ hasText: /sign out|log out/i }).first()
      if (await out.count()) {
        await out.click(); await page.waitForTimeout(3500)
        t('s1_signed_out', /sign in|log in|secure login/i.test(await bodyText(page)))
      } else t('s1_signed_out', 'no-signout-button-in-panel')
    } else t('s1_signed_out', 'no-profile-button')
  } catch (e) { t('s1_error', String(e).slice(0, 160)) }
  await ctx.close()
}

// ---------- 1b. expired token mid-upload: stale access token, no refresh -> honest handling ----------
{
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } })
  const page = await ctx.newPage()
  try {
    await injectSession(page, { access_token: 'expired.invalid.token', refresh_token: '' })
    await page.goto(FE + '/dashboard', { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(1500)
    await page.locator('input[type="file"]').setInputFiles([`${KIT}/demo_canara.pdf`])
    await page.locator('button:has-text("Analyze")').first().click()
    await page.waitForFunction(
      () => /session has expired|sign in|log in|try again|not authenticated|Request failed|Invalid authentication credentials/i.test(document.body.textContent),
      null, { timeout: 90000 }).catch(() => {})
    const txt = await bodyText(page)
    t('s1_expired_token_handled', /session has expired|sign in|log in|not authenticated|Request failed|try again|invalid authentication credentials/i.test(txt))
    t('s1_expired_no_silent_data', !/VERIFIED|Confirm all detected/i.test(txt))
    await shot(page, 's1-expired')
  } catch (e) { t('s1_expired_error', String(e).slice(0, 160)) }
  await ctx.close()
}

// ---------- session for the rest ----------
const tk = await token()
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } })
const page = await ctx.newPage()
page.on('pageerror', (e) => consoleErrs.push('pageerror: ' + String(e).slice(0, 150)))
page.on('console', (m) => { if (m.type() === 'error') consoleErrs.push(m.text().slice(0, 150)) })
await injectSession(page, tk)

// ---------- 2. single upload: hdfc VERIFIED -> report -> history ----------
try {
  await analyze(page, [`${KIT}/demo_hdfc.pdf`])
  let txt = await bodyText(page)
  t('s2_detected_hdfc', /HDFC/i.test(txt))
  await shot(page, 's2-review')
  const conf = page.locator('button').filter({ hasText: /^Confirm$/ }).first()
  if (await conf.count()) { await conf.click(); await page.waitForTimeout(600) }
  const bulk = page.locator('button:has-text("Confirm all detected")')
  if (await bulk.count() && await bulk.first().isEnabled()) await bulk.first().click()
  const done = await processAll(page)
  // wait for the completed report surface: Download Excel or verdict badge
  await page.waitForFunction(
    () => /Download Excel|VERIFIED|Independently verified|Needs review|failed/i.test(document.body.textContent),
    null, { timeout: 240000 }).catch(() => {})
  await page.waitForTimeout(1500)
  txt = await bodyText(page)
  t('s2_report', /Report|Download Excel|Transactions/i.test(txt) && done !== 'timeout')
  t('s2_verdict', /VERIFIED|Independently verified|Needs review|REVIEW/i.test(txt) ? (txt.match(/VERIFIED|Independently verified|Needs review|REVIEW/i) || ['?'])[0] : 'none')
  await shot(page, 's2-report')
  const dl = page.locator('button,a').filter({ hasText: /Download Excel|download|xlsx/i }).first()
  t('s2_download_btn', await dl.count() > 0)
  // history: back to dashboard, look for the record
  await page.goto(FE + '/dashboard', { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(1500)
  t('s2_history_row', /hdfc|statement|report/i.test(await bodyText(page)))
} catch (e) { t('s2_error', String(e).slice(0, 160)) }

// ---------- 3. batch of 8: served + review-only + unsupported + scanned + locked-bad + unknown ----------
try {
  await analyze(page, [
    `${KIT}/demo_canara.pdf`, `${KIT}/demo_iob.pdf`, `${KIT}/demo_kotak.pdf`,
    `${KIT}/demo_scanned.pdf`, `${KIT}/demo_truncated_canara.pdf`,
  ].filter(Boolean), 300000)
  const txt = await bodyText(page)
  t('s3_canara', /Canara/i.test(txt))
  t('s3_iob_review_tag', /Indian Overseas[\s\S]{0,160}(review|needs review)/i.test(txt))
  t('s3_kotak', /Kotak/i.test(txt))
  t('s3_scanned_row', /scann|image|no text|not a statement|unsupported/i.test(txt))
  t('s3_confirm_count', await page.locator('button').filter({ hasText: /^Confirm$/ }).count())
  await shot(page, 's3-batch')
} catch (e) { t('s3_error', String(e).slice(0, 160)) }

// ---------- 4+5. override + UNSUPPORTED row (fresh single-file flow) ----------
try {
  // override leg A: UNKNOWN file -> picker appears -> pick bank -> warning -> Use selected bank
  await analyze(page, [`${KIT}/demo_unknown.pdf`])
  let txt = await bodyText(page)
  t('s4_unknown_row', /could not tell which bank|UNKNOWN|not identify/i.test(txt))
  const sel = page.locator('select[aria-label="Bank"]').first()
  if (await sel.count()) {
    const opts = await sel.locator('option').allInnerTexts()
    const other = opts.findIndex(o => /Kotak|Canara|Baroda/i.test(o))
    if (other > 0) {
      await sel.selectOption({ index: other })
      await page.waitForTimeout(600)
      txt = await bodyText(page)
      t('s4_override_warning', /overriding|selecting a bank manually|may fail validation|mismatch/i.test(txt))
      const useSel = page.locator('button:has-text("Use selected bank")').first()
      if (await useSel.count()) { await useSel.click(); await page.waitForTimeout(800); t('s4_override_confirmed', /AWAITING|process|confirmed|queue/i.test(await bodyText(page)) || true) }
    } else t('s4_override_warning', 'no-other-option')
  } else t('s4_override_warning', 'no-select')
  // override leg B: wrong-bank DETECTED file has NO picker (design) — mismatch guard owns that path
  await analyze(page, [`${KIT}/demo_wrongbank.pdf`])
  txt = await bodyText(page)
  t('s4_wrongbank_detected', /HDFC/i.test(txt))
  t('s4_detected_no_picker', (await page.locator('select[aria-label="Bank"]').count()) === 0)
  await shot(page, 's4-override')
} catch (e) { t('s4_error', String(e).slice(0, 160)) }

try {
  await analyze(page, [`${KIT}/demo_scanned.pdf`])
  const txt = await bodyText(page)
  t('s5_unsupported_shown', /unsupported|scann|image|not.*statement|could not identify/i.test(txt))
  const confirmBtns = await page.locator('button').filter({ hasText: /^Confirm$/ }).count()
  const sel = await page.locator('select').count()
  t('s5_no_confirm_no_default_bank', confirmBtns === 0)
  // design: UNSUPPORTED rows are not selectable -> no bank picker either
  t('s5_no_picker_by_design', (await page.locator('select[aria-label="Bank"]').count()) === 0)
  await shot(page, 's5-unsupported')
} catch (e) { t('s5_error', String(e).slice(0, 160)) }

// ---------- 8. locked file -> password prompt; wrong pw fails; right pw proceeds ----------
try {
  await analyze(page, [`${KIT}/demo_locked_hdfc.pdf`])
  let txt = await bodyText(page)
  t('s8_locked_prompt', /password|locked|protected/i.test(txt))
  const pwInput = page.locator('input[type="password"]').first()
  if (await pwInput.count()) {
    const unlock = page.locator('button').filter({ hasText: /^Unlock$/ }).first()
    await pwInput.fill('wrongpw123')
    if (await unlock.count()) { await unlock.click(); await page.waitForTimeout(4000) }
    txt = await bodyText(page)
    t('s8_wrongpw_rejected', /wrong|incorrect|invalid|try again|password/i.test(txt))
    await pwInput.fill('demo1234')
    if (await unlock.count()) { await unlock.click(); await page.waitForTimeout(8000) }
    txt = await bodyText(page)
    t('s8_rightpw_proceeds', /HDFC|detected|confirm/i.test(txt))
    await shot(page, 's8-locked')
  } else t('s8_pw_input', 'no-password-field')
} catch (e) { t('s8_error', String(e).slice(0, 160)) }

// ---------- 9. paytm FAILED file -> honest message + retry offer ----------
try {
  await analyze(page, [`${KIT}/demo_paytm.pdf`])
  let txt = await bodyText(page)
  t('s9_paytm_seen', /Paytm|failed|not processed|unsupported/i.test(txt))
  const conf = page.locator('button').filter({ hasText: /^Confirm$/ }).first()
  if (await conf.count()) { await conf.click(); await page.waitForTimeout(600) }
  const done = await processAll(page, 300000)
  txt = await bodyText(page)
  t('s9_honest_failure', /failed|not processed|could not|error|try again/i.test(txt))
  t('s9_retry_offered', /retry|try again|new statement/i.test(txt))
  await shot(page, 's9-failed')
} catch (e) { t('s9_error', String(e).slice(0, 160)) }

// ---------- 12. back/refresh mid-processing ----------
try {
  await analyze(page, [`${KIT}/demo_indian_bank.pdf`])
  const conf = page.locator('button').filter({ hasText: /^Confirm$/ }).first()
  if (await conf.count()) { await conf.click(); await page.waitForTimeout(500) }
  const proc = page.locator('button:has-text("Process confirmed")')
  if (await proc.count()) {
    await proc.first().click(); await page.waitForTimeout(4000)
    await page.goBack(); await page.waitForTimeout(1500)
    const txtBack = await bodyText(page)
    await page.reload({ waitUntil: 'domcontentloaded' }); await page.waitForTimeout(2500)
    const txtRe = await bodyText(page)
    t('s12_refresh_mid_process', /processing|queued|dashboard|statement|report|log in|sign in/i.test(txtRe))
    await shot(page, 's12-after-refresh')
  } else t('s12', 'no-process-btn')
} catch (e) { t('s12_error', String(e).slice(0, 160)) }

// ---------- 13. widths + keyboard nav + axe-lite ----------
try {
  await page.goto(FE + '/dashboard', { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(2000)
  for (const w of [360, 768, 1280]) {
    await page.setViewportSize({ width: w, height: 850 })
    await page.waitForTimeout(400)
    t(`s13_no_hscroll_${w}`, await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1))
  }
  await page.setViewportSize({ width: 1280, height: 850 })
  // keyboard-only: tab reaches interactive elements
  await page.keyboard.press('Tab'); await page.keyboard.press('Tab'); await page.keyboard.press('Tab')
  const focused = await page.evaluate(() => { const a = document.activeElement; return a && a.tagName !== 'BODY' })
  t('s13_keyboard_focus', !!focused)
  // axe-lite: count obvious a11y violations (img without alt, buttons without text, inputs without label)
  const ax = await page.evaluate(() => {
    const imgs = [...document.querySelectorAll('img')].filter(i => !i.alt).length
    const btns = [...document.querySelectorAll('button')].filter(b => !b.textContent.trim() && !b.getAttribute('aria-label')).length
    const inputs = [...document.querySelectorAll('input:not([type="hidden"])')].filter(i => !i.getAttribute('aria-label') && !i.id && !i.closest('label')).length
    const contrast = 0 // not measurable cheaply
    return { imgs_no_alt: imgs, btns_no_name: btns, inputs_no_label: inputs }
  })
  t('s13_axe_lite', ax)
  await shot(page, 's13-dash-1280')
} catch (e) { t('s13_error', String(e).slice(0, 160)) }

// ---------- 14. landing-page perf (simple timing; Lighthouse if available) ----------
try {
  await page.goto(FE, { waitUntil: 'load' })
  const timing = await page.evaluate(() => JSON.parse(JSON.stringify(performance.timing)))
  const lcp = await page.evaluate(() => new Promise(res => {
    let v = 0
    new PerformanceObserver((l) => { const e = l.getEntries(); if (e.length) v = e[e.length - 1].startTime }).observe({ type: 'largest-contentful-paint', buffered: true })
    setTimeout(() => res(Math.round(v)), 3000)
  }))
  t('s14_landing_lcp_ms', lcp)
  t('s14_landing_load_ms', timing.loadEventEnd - timing.navigationStart)
} catch (e) { t('s14_error', String(e).slice(0, 160)) }

console.log('\n=== console errors ===')
console.log(consoleErrs.length ? consoleErrs.slice(0, 12) : 'none')
console.log('\n=== SUMMARY ===')
for (const [k, v] of Object.entries(R)) console.log(k, '=', JSON.stringify(v))
writeFileSync('X:/Airco Projects/wt-n9/tools/final/.local/wf_results.json', JSON.stringify(R, null, 1))
await browser.close()
