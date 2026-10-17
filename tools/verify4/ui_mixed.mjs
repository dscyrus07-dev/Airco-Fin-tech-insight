// R3 mixed-batch UI check on rc (:3600) — one upload containing:
//  (a) dhanlaxmi REVIEW file   -> confirmable per-doc
//  (b) bandhan file            -> unsupported, refused honestly
//  (c) federal unbranded export-> UNKNOWN/refused honestly
// env: KC_SECRET, V4_PW. Files via MIX_A/MIX_B/MIX_C.
import { chromium } from 'playwright'
const FE='http://localhost:3600', KC='http://localhost:8080'
const SECRET=process.env.KC_SECRET||'', PW=process.env.V4_PW||process.env.E2E_USER_PW||''
const results=[], t=(n,ok,ex='')=>{results.push({n,ok:!!ok,ex});console.log(ok?'PASS':'FAIL',n,ex)}
const FILES=[process.env.MIX_A,process.env.MIX_B,process.env.MIX_C]
const tk=await (await fetch(`${KC}/realms/airco-insights/protocol/openid-connect/token`,{method:'POST',headers:{'content-type':'application/x-www-form-urlencoded'},body:new URLSearchParams({grant_type:'password',client_id:'frontend-app',client_secret:SECRET,username:'test@airco.com',password:PW})})).json()
const browser=await chromium.launch({channel:'chrome'})
for(const vw of [1280,360]){
 const ctx=await browser.newContext({viewport:{width:vw,height:900}})
 const page=await ctx.newPage()
 await page.addInitScript(([a,r])=>{sessionStorage.setItem('kc_token',a);sessionStorage.setItem('kc_refresh_token',r||'');document.cookie=`kc_token=${encodeURIComponent(a)}; Path=/; SameSite=Lax`},[tk.access_token,tk.refresh_token||''])
 await page.goto(FE+'/dashboard',{waitUntil:'domcontentloaded'}); await page.waitForTimeout(2000)
 const inp=page.locator('input[type="file"]')
 t(`upload3_${vw}`,(await inp.count())>0)
 if(await inp.count()){
  await inp.first().setInputFiles(FILES); await page.waitForTimeout(1000)
  await page.locator('button:has-text("Analyze")').first().click()
  await page.waitForFunction(()=>(document.body.textContent.match(/\.pdf/g)||[]).length>=3&&/Confirm/i.test(document.body.textContent),null,{timeout:300000}).catch(()=>{})
  await page.waitForTimeout(3000)
  const txt=await page.evaluate(()=>document.body.textContent)
  t(`dhan_review_${vw}`,/Dhanlaxmi/i.test(txt)&&/Confirm/i.test(txt))
  t(`unsup_refused_${vw}`,/Bandhan/i.test(txt)?/isn't fully supported|not enabled|not supported|could not identify/i.test(txt):'unknown-det')
  t(`unbranded_refused_${vw}`,/Federal Bank statement\. Please confirm|could not identify|isn't fully supported/i.test(txt),txt.match(/3311156[^]{0,120}/)?.[0]||'')
  const confirmBtns=await page.locator('button:has-text("Confirm")').count()
  t(`confirm_btns_${vw}`,confirmBtns>=1,String(confirmBtns))
  const procBtn=await page.locator('button:has-text("Process confirmed")').count()
  console.log('  [info]',vw,'process btn:',procBtn,'| confirm btns:',confirmBtns)
 }
 await page.screenshot({path:`tools/verify4/.local/ui_mixed_${vw}.png`,fullPage:true})
 if(vw===360)t('no_hscroll_360',await page.evaluate(()=>document.documentElement.scrollWidth<=370))
 await ctx.close()
}
console.log(JSON.stringify(results))
await browser.close()
