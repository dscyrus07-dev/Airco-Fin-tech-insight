// P4 browser walk: login -> dashboard -> accordions -> responsive -> a11y -> reduced motion.
// Synthetic content only (no real statement data). Screenshots to tmp/r5b_screens/.
import { createRequire } from 'node:module';
const require = createRequire('X:/Airco Projects/wt-r5/frontend/package.json');
const { chromium } = require('playwright');

const BASE = 'http://localhost:3500';
const OUT = 'X:/Airco Projects/wt-r5/tmp/r5b_screens';
import fs from 'node:fs';
fs.mkdirSync(OUT, { recursive: true });

const b = await chromium.launch({ channel: 'chrome', headless: true });
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' });
const p = await ctx.newPage();
const errs = [];
p.on('console', m => { if (m.type() === 'error') errs.push(m.text().slice(0, 120)); });

await p.goto(`${BASE}/dashboard`, { waitUntil: 'domcontentloaded' });
for (let i = 0; i < 25; i++) {
  if (p.url().includes('realms/airco-insights')) break;
  const btn = p.locator('button:has-text("Sign In"),button:has-text("Continue")').first();
  if (await btn.count()) await btn.click().catch(() => {});
  await p.waitForTimeout(1000);
  if (await p.locator('input[type=file]').count()) break;
}
if (p.url().includes('realms')) {
  await p.fill('#username', 'devin-e2e');
  await p.fill('#password', 'DevinE2E!2024');
  await p.click('#kc-login');
  await p.waitForURL(/dashboard/, { timeout: 30000 });
}
await p.waitForTimeout(3000);
await p.screenshot({ path: `${OUT}/p4_dashboard_1440.png`, fullPage: true });

// accordions
const guide = p.locator('button:has-text("How to use")').first();
await guide.click(); await p.waitForTimeout(600);
await p.screenshot({ path: `${OUT}/p4_guide_open.png`, fullPage: true });
const limits = p.locator('button:has-text("Limits")').first();
await limits.click(); await p.waitForTimeout(600);
await p.screenshot({ path: `${OUT}/p4_limits_open.png`, fullPage: true });

// closed-accordion tabbability
const tab = await p.evaluate(() => {
  const btn = [...document.querySelectorAll('button')].find(b => /How to use/.test(b.textContent));
  const panel = document.getElementById(btn.getAttribute('aria-controls'));
  const f = panel ? [...panel.querySelectorAll('a,button,input,[tabindex]')].filter(el => el.getAttribute('tabindex') !== '-1' && el.offsetParent !== null) : [];
  return { expanded: btn.getAttribute('aria-expanded'), tabbables: f.length };
});
console.log('accordion closed-state:', JSON.stringify(tab));

// keyboard focus visibility
await p.keyboard.press('Tab'); await p.keyboard.press('Tab');
const focus = await p.evaluate(() => {
  const el = document.activeElement;
  const s = getComputedStyle(el);
  return { tag: el.tagName, outline: s.outlineStyle, shadow: s.boxShadow !== 'none', text: (el.textContent || '').trim().slice(0, 24) };
});
console.log('focus-visible:', JSON.stringify(focus));

// responsive 375/768/1280
for (const [w, h, name] of [[375, 812, '375'], [768, 1024, '768'], [1280, 900, '1280']]) {
  await p.setViewportSize({ width: w, height: h });
  await p.waitForTimeout(800);
  const hs = await p.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
  console.log(`${name}px hscroll:`, hs.sw > hs.cw, JSON.stringify(hs));
  await p.screenshot({ path: `${OUT}/p4_dashboard_${name}.png`, fullPage: true });
}

// reduced motion: no animations sampled (context created with reducedMotion=reduce)
const anims = await p.evaluate(() => {
  const els = [...document.querySelectorAll('*')].filter(e => {
    const s = getComputedStyle(e);
    return (s.animationName && s.animationName !== 'none' && s.animationDuration !== '0s');
  });
  return els.length;
});
console.log('reduced-motion animated elements:', anims);
console.log('console errors:', errs.length ? errs.slice(0, 4) : 'none');
await b.close();
