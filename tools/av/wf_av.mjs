// AV §3 UI leg on rc (:3600 frontend, :8601 backend). Synthetic PDFs only.
import { chromium } from 'playwright'
import { mkdirSync, writeFileSync } from 'fs'

const FE = 'http://localhost:3600'
const KC = 'http://localhost:8080'
const OUT = 'X:/Airco Projects/wt-av/tools/av/.local/shots'
const KIT = 'X:/Airco Projects/wt-av/tools/final/demo_pdfs'
mkdirSync(OUT, { recursive: true })

const USER = process.env.TEST_USER_EMAIL || 'test@airco.com'
const PW = process.env.TEST_USER_PASSWORD || 'Test123!'
const SECRET = process.env.KC_FE_SECRET || '' // fetched externally; fallback: script arg

const R = {}
const consoleErrs = []
const netHits = []
const t = (k, v) => { R[k] = v; console.log(' ', k, '=', JSON.stringify(v).slice(0, 170)) }
const bodyText = (p) => p.locator('body').innerText()
const shot = (p, n) => p.screenshot({ path: `${OUT}/${n}.png` }).catch(() => {})

async function token() {
  const body = new URLSearchParams({
    grant_type: 'password', client_id: 'frontend-app', client_secret: SECRET,
    username: USER, password: PW, scope: 'openid',
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
  await page.locator('input[type="file"]').setInputFiles(files)
  await page.waitForTimeout(500)
  await page.locator('button:has-text("Analyze")').first().click()
  await page.waitForFunction(
    () => /Confirm all detected|is not enabled yet|isn't fully supported|Why we think so|Use selected bank|could not identify|Password|password|scanned/i.test(document.body.textContent),
    null, { timeout: timeoutMs })
  await page.waitForTimeout(900)
}

const browser = await chromium.launch({ channel: 'chrome' })

// ---------- 1. real sign-in via Keycloak (confidential client path) ----------
{
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } })
  const page = await ctx.newPage()
  page.on('console', (m) => { if (m.type() === 'error') consoleErrs.push('signin: ' + m.text().slice(0, 140)) })
  try {
    await page.goto(FE, { waitUntil: 'domcontentloaded' })
    await page.locator('button,a').filter({ hasText: /sign in|log in|get started/i }).first().click()
    await page.waitForURL(/localhost:8080.*openid-connect\/auth/, { timeout: 20000 })
    await page.locator('#username').fill(USER)
    await page.locator('#password').fill(PW)
    await page.locator('#kc-login,button[type="submit"],input[type="submit"]').first().click()
    await page.waitForURL(/localhost:3600/, { timeout: 30000 })
    await page.waitForTimeout(2500)
    t('signin_ok', /dashboard|statement|upload/i.test(await bodyText(page)))
    await shot(page, 'signedin')
  } catch (e) { t('signin_error', String(e).slice(0, 200)) }
  await ctx.close()
}

// ---------- 2. expired-session honesty ----------
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
    t('expired_honest', /session has expired|sign in|log in|not authenticated|Request failed|try again|invalid authentication credentials/i.test(txt))
    t('expired_no_silent_data', !/VERIFIED|Confirm all detected/i.test(txt))
  } catch (e) { t('expired_error', String(e).slice(0, 160)) }
  await ctx.close()
}

// ---------- 3. full flow + downloads (1280) ----------
const tk = await token()
{
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, acceptDownloads: true })
  const page = await ctx.newPage()
  page.on('console', (m) => { if (m.type() === 'error') consoleErrs.push(m.text().slice(0, 140)) })
  page.on('request', (r) => { if (/\/api\/jobs\/|\/api\/download\//.test(r.url())) netHits.push(r.url()) })
  await injectSession(page, tk)
  try {
    await analyze(page, [`${KIT}/demo_hdfc.pdf`])
    const conf = page.locator('button').filter({ hasText: /^Confirm$/ }).first()
    if (await conf.count()) { await conf.click(); await page.waitForTimeout(600) }
    const bulk = page.locator('button:has-text("Confirm all detected")')
    if (await bulk.count() && await bulk.first().isEnabled()) await bulk.first().click()
    const proc = page.locator('button:has-text("Process confirmed")')
    if (await proc.count()) {
      await proc.first().click()
      await page.waitForFunction(
        () => /Download Excel|Download Report|download|VERIFIED|Needs review|failed/i.test(document.body.textContent),
        null, { timeout: 300000 }).catch(() => {})
    }
    await page.waitForTimeout(1500)
    t('report_reached', /Report|Download|Transactions|VERIFIED|review/i.test(await bodyText(page)))
    await shot(page, 'report')
    // excel_url on the wire should carry ?t=
    const jobsHits = netHits.filter(u => /\/api\/jobs\/[^/]+$/.test(u))
    t('job_poll_hits', jobsHits.length)
    // download button click -> expect download event
    const dlBtn = page.locator('button,a').filter({ hasText: /Download Excel|Download Report|\.xlsx|Download/i }).first()
    if (await dlBtn.count()) {
      const href = await dlBtn.getAttribute('href').catch(() => null)
      const [dl] = await Promise.all([
        page.waitForEvent('download', { timeout: 20000 }).catch(() => null),
        dlBtn.click(),
      ])
      t('download_fired', !!dl)
      if (dl) t('download_name', dl.suggestedFilename())
      if (href) t('download_href_has_t', /\?t=/.test(href))
      // if no href, it's a button->fetch path; check network for the download call
      t('dl_net_hits', netHits.filter(u => /download/.test(u)).slice(-3))
    } else t('download_btn', 'missing')
    // Dashboard history download (bearer fetch -> filename)
    await page.goto(FE + '/dashboard', { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(2500)
    const histBtn = page.locator('button[aria-label="Download report"]').first()
    t('history_dl_btn', await histBtn.count() > 0)
    if (await histBtn.count()) {
      const [dl2] = await Promise.all([
        page.waitForEvent('download', { timeout: 20000 }).catch(() => null),
        histBtn.click(),
      ])
      t('history_download_fired', !!dl2)
      if (dl2) t('history_download_name', dl2.suggestedFilename())
    }
  } catch (e) { t('flow_error', String(e).slice(0, 200)) }
  await ctx.close()
}

// ---------- 4. batch of 2 + download-all links carry ?t= ----------
{
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, acceptDownloads: true })
  const page = await ctx.newPage()
  page.on('request', (r) => { if (/download\?t=/.test(r.url())) netHits.push('signed:' + r.url().replace(/t=[^&]+/, 't=<redacted>')) })
  await injectSession(page, await token())
  try {
    await analyze(page, [`${KIT}/demo_canara.pdf`, `${KIT}/demo_axis.pdf`], 300000)
    const bulk = page.locator('button:has-text("Confirm all detected")')
    if (await bulk.count() && await bulk.first().isEnabled()) await bulk.first().click()
    const proc = page.locator('button:has-text("Process confirmed")')
    if (await proc.count()) {
      await proc.first().click()
      await page.waitForFunction(
        () => /Download All|Download all|download all/i.test(document.body.textContent),
        null, { timeout: 300000 }).catch(() => {})
    }
    await page.waitForTimeout(1200)
    const allBtn = page.locator('button').filter({ hasText: /download all/i }).first()
    t('download_all_btn', await allBtn.count() > 0)
    if (await allBtn.count()) {
      const downloads = []
      page.on('download', (d) => downloads.push(d.suggestedFilename()))
      await allBtn.click()
      await page.waitForTimeout(8000)
      t('download_all_files', downloads)
    }
    t('signed_download_requests', netHits.filter(u => u.startsWith('signed:')).length)
    await shot(page, 'batch-done')
  } catch (e) { t('batch_error', String(e).slice(0, 200)) }
  await ctx.close()
}

// ---------- 5. width 360 sanity ----------
{
  const ctx = await browser.newContext({ viewport: { width: 360, height: 800 } })
  const page = await ctx.newPage()
  await injectSession(page, await token())
  await page.goto(FE + '/dashboard', { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(1500)
  const txt = await bodyText(page)
  t('w360_renders', /upload|statement|dashboard|analyze/i.test(txt))
  t('w360_no_hscroll', await page.evaluate(() => document.documentElement.scrollWidth <= 400))
  await shot(page, 'w360')
  await ctx.close()
}

t('console_errors', consoleErrs)
writeFileSync('X:/Airco Projects/wt-av/tools/av/.local/wf_results.json', JSON.stringify({ R, netHits }, null, 2))
console.log('\nDONE', Object.keys(R).length, 'checks')
await browser.close()
