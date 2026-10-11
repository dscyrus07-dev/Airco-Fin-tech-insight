# Wave11 E3 UI acceptance: real-browser flow on the w11 stack
# (frontend dev server :3001 -> backend :8005, shared Keycloak :8080).
# For each bank: login -> upload -> detect/confirm -> process -> download
# -> capture engine badge/review wording shown in the UI.
import asyncio, json, os, re, sys, urllib.request, urllib.parse
from playwright.async_api import async_playwright

BASE = "http://localhost:3001"
KC = "http://localhost:8080"
OUT = r"X:\Airco Projects\Airco Insights fintech\wt-w11\comparison\wave11"
PICKS = json.load(open(os.path.join(OUT, "e3_picks.json")))
BANKS = sys.argv[1:] or ["hdfc", "sbi", "citibank", "city_union", "axis"]
ENV = {}
for line in open(r"X:\Airco Projects\Airco Insights fintech\wt-demo\local.env", encoding="utf-8"):
    m = re.match(r"^([A-Z_0-9]+)=(.*)$", line.strip())
    if m:
        ENV[m.group(1)] = m.group(2).strip().strip('"')
USER = ENV.get("TEST_USER_EMAIL", "test@airco.com")
PW = ENV.get("TEST_USER_PASSWORD") or "Test123!"


def get_tokens():
    body = urllib.parse.urlencode({
        "grant_type": "password", "client_id": "frontend-app",
        "client_secret": ENV.get("KEYCLOAK_CLIENT_SECRET", ""),
        "username": USER, "password": PW, "scope": "openid"}).encode()
    req = urllib.request.Request(
        f"{KC}/realms/airco-insights/protocol/openid-connect/token",
        data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    return json.load(urllib.request.urlopen(req))


async def main():
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(accept_downloads=True, viewport={"width": 1366, "height": 900})
        page = await ctx.new_page()
        console_errs = []
        page.on("console", lambda m: console_errs.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: console_errs.append(str(e)))

        # Browser login is unavailable on :3001 (Keycloak redirect_uri allowlist is
        # demo-owned). Inject a direct-grant session token instead — same storage
        # the app's own callback writes (sessionToken.ts).
        tk = get_tokens()
        await page.goto(BASE, wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)
        await page.evaluate("""([at, rt]) => {
            sessionStorage.setItem('kc_token', at);
            sessionStorage.setItem('kc_refresh_token', rt || '');
            document.cookie = `kc_token=${encodeURIComponent(at)}; Path=/; SameSite=Lax`;
            if (rt) document.cookie = `kc_refresh_token=${encodeURIComponent(rt)}; Path=/; SameSite=Lax`;
        }""", [tk["access_token"], tk.get("refresh_token") or ""])
        await page.screenshot(path=os.path.join(OUT, "ui_login.png"))

        for spec in BANKS:
            rec = next(r for r in PICKS[spec] if r.get("path"))
            res = {"spec": spec, "sha": rec["sha"], "corpus_verdict": rec["verdict"]}
            try:
                await page.goto(BASE + "/analyze", wait_until="domcontentloaded")
                await page.wait_for_timeout(1500)
                fi = page.locator("input[type='file']").first
                await fi.set_input_files(rec["path"])
                await page.wait_for_timeout(1200)
                b = page.locator("button:has-text('Analyze')")
                if await b.count() and await b.first.is_enabled():
                    await b.first.click()
                # wait for analysis result card (state chip or doc filename)
                for _ in range(30):
                    await page.wait_for_timeout(2000)
                    txt = await page.locator("body").inner_text()
                    if any(w in txt for w in ("DETECTED", "REVIEW", "UNKNOWN", "UNSUPPORTED",
                                              "Confirm all detected", "Why we think so")):
                        break
                await page.screenshot(path=os.path.join(OUT, f"ui_{spec}_analyzed.png"))
                res["analyzed_text"] = (await page.locator("body").inner_text())[:1500]
                res["state_chip"] = [w for w in ("DETECTED", "REVIEW", "UNKNOWN", "UNSUPPORTED")
                                     if w in res["analyzed_text"]]
                # confirm docs: bulk for DETECTED, per-doc Confirm for REVIEW
                clicked = False
                b = page.locator("button:has-text('Confirm all detected')")
                if await b.count() and await b.first.is_enabled():
                    await b.first.click()
                    await page.wait_for_timeout(1500)
                    clicked = True
                if not clicked:
                    for _ in range(15):
                        b = page.locator("button:text-is('Confirm')")
                        if await b.count() and await b.first.is_enabled():
                            await b.first.click()
                            await page.wait_for_timeout(1500)
                            break
                        await page.wait_for_timeout(1000)
                # process (button disabled while confirm is busy — wait for enable)
                for _ in range(15):
                    b = page.locator("button:has-text('Process confirmed')")
                    if await b.count() and await b.first.is_enabled():
                        await b.first.click()
                        break
                    await page.wait_for_timeout(1000)
                # wait for job terminal state
                for _ in range(90):
                    await page.wait_for_timeout(4000)
                    txt = await page.locator("body").inner_text()
                    low = txt.lower()
                    if "status: completed" in low or "status: failed" in low or "download excel" in low:
                        break
                final = (await page.locator("body").inner_text())
                res["final_text"] = final[:2000]
                low = final.lower()
                res["job_done"] = "status: completed" in low
                res["job_failed"] = "status: failed" in low
                res["badge_verified"] = "verif" in low
                res["badge_review"] = "review" in low or "needs attention" in low
                await page.screenshot(path=os.path.join(OUT, f"ui_{spec}_final.png"))
                try:
                    async with page.expect_download(timeout=20000) as di:
                        b = page.locator("button:has-text('Download Excel')")
                        if await b.count():
                            await b.first.click()
                    dl = await di.value
                    res["download"] = dl.suggested_filename
                except Exception:
                    res["download"] = None
                res["ok"] = True
            except Exception as e:
                res["ok"] = False
                res["error"] = f"{type(e).__name__}: {e}"[:200]
                res["url_at_error"] = page.url
                try:
                    await page.screenshot(path=os.path.join(OUT, f"ui_{spec}_error.png"))
                except Exception:
                    pass
            results.append(res)
            print(json.dumps({k: v for k, v in res.items() if k not in ("analyzed_text", "final_text")}, default=str), flush=True)
        res_all = {"results": results, "console_errors": console_errs[:20]}
        json.dump(res_all, open(os.path.join(OUT, "e3_ui_results.json"), "w"), indent=1)
        print("console_errors:", console_errs[:10])
        await browser.close()

asyncio.run(main())
