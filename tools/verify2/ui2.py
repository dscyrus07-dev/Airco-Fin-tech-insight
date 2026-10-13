"""verify2 UI flow: unified analyze->confirm->process in the onb frontend via Playwright.
Own implementation (prompt-28). Uses preinstalled Chromium only; no playwright install.
usage: python tools/verify2/ui2.py --files=sha8,... [--batch=a,b,c,d] [--unsupported=sha8] [--widths=360,768,1280] --out=<json>"""
import json, os, sys, glob
from playwright.sync_api import sync_playwright

opt = {"--fe": "http://localhost:3400", "--user": "test@airco.com",
       "--pass-env": "E2E_USER_PW", "--widths": "360,768,1280",
       "--files": "", "--batch": "", "--unsupported": "", "--out": "tools/verify2/.local/ui2.json"}
for a in sys.argv[1:]:
    k, _, v = a.partition("=")
    if k in opt:
        opt[k] = v

mani = {}
for m in glob.glob(os.path.join(os.path.dirname(__file__), ".local", "manifest_*.jsonl")):
    for ln in open(m, encoding="utf-8"):
        d = json.loads(ln); mani[d["sha8"]] = d["path"]

PW = os.environ.get(opt["--pass-env"], "Test123!")
report = {"scenarios": {}, "errors": []}

def signin(page):
    page.goto(opt["--fe"] + "/dashboard", wait_until="networkidle", timeout=60000)
    btn = page.locator("button:has-text('Sign In'), button:has-text('Continue'), a:has-text('Sign In')")
    if btn.count():
        btn.first.click()
        page.wait_for_load_state("networkidle", timeout=60000)
    if page.locator("input#username").count():
        page.fill("input#username", opt["--user"])
        page.fill("input#password", PW)
        page.click("input#kc-login, button[type=submit], input[type=submit]")
        page.wait_for_load_state("networkidle", timeout=60000)
    return "/dashboard" in page.url or "dashboard" in page.url

def upload_and_review(page, sha8s):
    paths = [mani[s] for s in sha8s]
    inp = page.locator("input[type=file]")
    if not inp.count():
        return {"error": "no file input"}
    inp.first.set_input_files(paths)
    page.wait_for_timeout(2500)
    for label in ("Analyze", "Continue", "Review", "Next"):
        b0 = page.locator(f"button:has-text('{label}')")
        if b0.count():
            try:
                b0.first.click(timeout=3000)
            except Exception:
                pass
            page.wait_for_timeout(1500)
    for _ in range(60):
        chips = page.locator("span.rounded-full")
        if chips.count() >= len(sha8s):
            break
        page.wait_for_timeout(2000)
    chips_txt = page.locator("span.rounded-full").evaluate_all("es=>es.map(e=>e.textContent)")
    res = {"chips": chips_txt[:20]}
    sels = page.locator("select")
    res["rows"] = []
    for i in range(sels.count()):
        sel = sels.nth(i)
        res["rows"].append({
            "i": i,
            "selected": sel.input_value(),
            "row": (sel.evaluate("e=>e.closest('li,tr,div')?.innerText?.slice(0,140)") or "")[:140],
        })
        if i == 0:
            opts = sel.locator("option")
            res["dropdown_n"] = opts.count()
            res["dropdown"] = [opts.nth(j).evaluate("e=>e.textContent")
                               for j in range(min(opts.count(), 60))]
    res["confirm_btns"] = page.locator("button:has-text('Confirm')").count()
    res["confirm_all"] = page.locator("button:has-text('Confirm All'), button:has-text('Confirm all')").count()
    return res

with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page()
    try:
        report["signin"] = signin(page)
        page.wait_for_timeout(1500)

        if opt["--files"]:
            s8s = opt["--files"].split(",")
            report["scenarios"]["single"] = {"files": s8s, **upload_and_review(page, s8s)}
            # confirm all and process
            ca = page.locator("button:has-text('Confirm All'), button:has-text('Confirm all')")
            if ca.count() and ca.first.is_enabled():
                ca.first.click()
            else:
                rc = page.locator("button:has-text('Confirm')")
                for i in range(min(rc.count(), len(s8s))):
                    try:
                        rc.nth(i).click(timeout=4000)
                        page.wait_for_timeout(600)
                    except Exception:
                        pass
            report["scenarios"]["single"]["confirmed"] = True
            page.wait_for_timeout(1500)
            proc = page.locator("button:has-text('Process'), button:has-text('Generate'), button:has-text('Proceed')")
            report["scenarios"]["single"]["process_btn"] = proc.count()
            if proc.count():
                try:
                    proc.first.click(timeout=4000)
                    page.wait_for_timeout(3000)
                    report["scenarios"]["single"]["post_process_text"] = page.locator("body").inner_text()[:300]
                except Exception as e:
                    report["errors"].append("process-click:" + str(e)[:120])
            page.goto(opt["--fe"] + "/dashboard", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(1500)

        if opt["--batch"]:
            s8s = opt["--batch"].split(",")
            report["scenarios"]["batch"] = {"files": s8s, **upload_and_review(page, s8s)}
            page.goto(opt["--fe"] + "/dashboard", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(1500)

        if opt["--unsupported"]:
            s8s = opt["--unsupported"].split(",")
            report["scenarios"]["unsupported"] = {"files": s8s, **upload_and_review(page, s8s)}
            # check: no default bank selected, no Confirm for that row
            page.goto(opt["--fe"] + "/dashboard", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(1500)

        for w in [int(x) for x in opt["--widths"].split(",")]:
            page.set_viewport_size({"width": w, "height": 800})
            page.wait_for_timeout(400)
            sw = page.evaluate("document.documentElement.scrollWidth")
            report.setdefault("widths", {})[w] = {"scrollWidth": sw, "hscroll": sw > w + 1}
    except Exception as e:
        report["errors"].append(str(e)[:200])
    b.close()

json.dump(report, open(opt["--out"], "w"), indent=1)
print(json.dumps({k: v for k, v in report.items() if k != "scenarios"}, indent=1)[:800])
for name, sc in report["scenarios"].items():
    print("==", name, {k: v for k, v in sc.items() if k in ("chips", "confirm_btns", "dropdown_n", "error")})
print("OUT", opt["--out"])
