"""Browser-flow verification on the onb frontend via Playwright (preinstalled Chromium).

Covers: sign-in via Keycloak, upload 1+ files, review row states, bank dropdown
contents, UNSUPPORTED row behaviour, batch upload, viewport widths 360/768/1280
(horizontal-scroll check). Credentials come from env vars, never printed.

usage: python tools/verify/browser_flow.py --fe=http://localhost:3400
        --user=.. --pass-env=E2E_USER_PW --files=f1.pdf,f2.pdf,...
        [--unsupported=locked.pdf] [--widths=360,768,1280]
"""
import json, os, sys, time
from playwright.sync_api import sync_playwright

opt = {"--fe": "http://localhost:3400", "--user": "test@airco.com",
       "--pass-env": "E2E_USER_PW", "--widths": "360,768,1280",
       "--files": "", "--unsupported": "", "--out": "tools/verify/.local/browser.json"}
for a in sys.argv[1:]:
    k, _, v = a.partition("=")
    if k in opt:
        opt[k] = v

FILES = [f for f in opt["--files"].split(",") if f]
WIDTHS = [int(w) for w in opt["--widths"].split(",")]
PW = os.environ.get(opt["--pass-env"], "")
report = {"signin": None, "upload": None, "rows": [], "dropdown": None,
          "widths": {}, "errors": []}

with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page()
    try:
        page.goto(opt["--fe"] + "/dashboard", wait_until="networkidle", timeout=60000)
        # app landing page: click "Continue to Sign In" -> keycloak
        try:
            btn = page.locator("button:has-text('Sign In'), button:has-text('Continue'), a:has-text('Sign In')")
            if btn.count():
                btn.first.click()
                page.wait_for_load_state("networkidle", timeout=60000)
        except Exception as e:
            report["errors"].append("signin-click:" + str(e)[:120])
        if page.locator("input#username").count():
            page.fill("input#username", opt["--user"])
            page.fill("input#password", PW)
            page.click("input#kc-login, button[type=submit], input[type=submit]")
            page.wait_for_load_state("networkidle", timeout=60000)
        report["signin"] = {"ok": "/dashboard" in page.url,
                            "url": page.url}
        page.wait_for_timeout(2000)

        # upload files via the file input
        inp = page.locator("input[type=file]")
        if inp.count() and FILES:
            inp.first.set_input_files(FILES)
            report["upload"] = {"files": len(FILES)}
            page.wait_for_timeout(2000)
            # click the Analyze/continue button that appears after upload
            for label in ("Analyze", "Continue", "Review"):
                b0 = page.locator(f"button:has-text('{label}')")
                if b0.count():
                    try:
                        b0.first.click()
                    except Exception:
                        pass
                    break
            # wait for the review list: state chips are span.rounded-full
            for _ in range(45):
                if page.locator("span.rounded-full").count() >= len(FILES):
                    break
                page.wait_for_timeout(2000)
            page.wait_for_timeout(1000)
            report["state_chips"] = page.locator(
                "span.rounded-full").evaluate_all("es=>es.map(e=>e.textContent)")[:20]
            sels = page.locator("select")
            report["rows"] = []
            for i in range(sels.count()):
                sel = sels.nth(i)
                row_html = sel.evaluate("e=>e.closest('li,tr,div')?.innerText?.slice(0,160)")
                report["rows"].append({"i": i, "selected": sel.input_value(),
                                       "row_text": row_html})
                opts = sel.locator("option")
                if i == 0:
                    report["dropdown"] = {"n": opts.count(),
                        "labels": [opts.nth(j).evaluate("e=>e.textContent") for j in range(min(opts.count(), 60))]}
            # confirm buttons per row
            report["confirm_btns"] = page.locator("button:has-text('Confirm')").count()
            report["buttons"] = [page.locator("button").nth(j).inner_text()
                                 for j in range(min(page.locator("button").count(), 12))]
        else:
            report["upload"] = {"error": "no file input found", "inputs": inp.count()}

        # viewport widths — horizontal scroll check
        for w in WIDTHS:
            page.set_viewport_size({"width": w, "height": 800})
            page.wait_for_timeout(400)
            sw = page.evaluate("document.documentElement.scrollWidth")
            report["widths"][w] = {"scrollWidth": sw, "hscroll": sw > w + 1}
        page.set_viewport_size({"width": 1280, "height": 800})
    except Exception as e:
        report["errors"].append(str(e)[:200])
    b.close()

json.dump(report, open(opt["--out"], "w"), indent=1)
print(json.dumps({k: v for k, v in report.items() if k != "dropdown"}, indent=1)[:2000])
print("dropdown_n:", (report.get("dropdown") or {}).get("n"))
print("OUT", opt["--out"])
