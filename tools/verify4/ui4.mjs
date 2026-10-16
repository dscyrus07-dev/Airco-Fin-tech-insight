// V4 UI check on rc (:3600) — unified AnalyzeFlow + BankSupportPanel + ReviewTable.
// env: KC_SECRET, V4_PW, V4_F_DBS, V4_F_FED, V4_F_DHAN
import { chromium } from 'playwright'
import fs from 'fs'
const FE='http://localhost:3600', KC='http://localhost:8080'
const SECRET=process.env.KC_SECRET||'', PW=process.env.V4_PW||process.env.E2E_USER_PW||''
const USER='test@airco.com'
const results=[], consoleErrs=[]
const t=(n,ok,extra='')=>{results.push({n,ok:!!ok,extra});console.log((ok?'PASS':'FAIL'),n,extra)}
async function token(){const r=await fetch(`${KC}/realms/airco-insights/protocol/openid-connect/token`,{method:'POST',headers:{'content-type':'application/x-www-form-urlencoded'},body:new URLSearchParams({grant_type:'password',client_id:'frontend-app',client_secret:SECRET,username:USER,password:PW})});return r.json()}
async function inject(page,tk){await page.addInitScript(([a,r])=>{sessionStorage.setItem('kc_token',a);sessionStorage.setItem('kc_refresh_token',r||'');document.cookie=`kc_token=${encodeURIComponent(a)}; Path=/; SameSite=Lax`;if(r)document.cookie=`kc_refresh_token=${encodeURIComponent(r)}; Path=/; SameSite=Lax`},[tk.access_token,tk.refresh_token||''])}
const browser=await chromium.launch({channel:'chrome'})
const tk=await token()
// ---- leg A: support panel structure + counts at 1280 then 360 ----
{
 const ctx=await browser.newContext({viewport:{width:1280,height:900}})
 const page=await ctx.newPage(); page.on('console',m=>{if(m.type()==='error')consoleErrs.push(m.text().slice(0,120))})
 await inject(page,tk)
 await page.goto(FE+'/dashboard',{waitUntil:'domcontentloaded'}); await page.waitForTimeout(2000)
 const body=await page.evaluate(()=>document.body.textContent)
 const m=body.match(/(\d+)\s+banks supported/)
 t('support_panel_count',!!m,m?m[0]:'absent')
 // expand "See the full bank list"
 const det=page.locator('summary:has-text("Details")')
 if(await det.count()){await det.first().click();await page.waitForTimeout(600)}
 const selA=page.locator('select[aria-label="Bank hint"]')
 if(await selA.count()){
   const opts=await selA.evaluateAll(os=>os.flatMap(s=>[...s.querySelectorAll('option')].map(o=>({v:o.value,t:o.textContent.trim(),dis:o.disabled,grp:o.parentElement?.tagName==='OPTGROUP'?o.parentElement.label:''}))))
   fs.writeFileSync('tools/verify4/.local/ui_options.json',JSON.stringify(opts,null,1))
   for(const c of['dbs','federal','dhanlaxmi']){const o=opts.find(x=>x.v===c);t(`ui_${c}_selectable`,o&&!o.dis,o?`${o.t}|${o.grp}`:'absent')}
   const ii=opts.find(x=>x.v==='indusind');t('ui_indusind_greyed',!ii||ii.dis,ii?`${ii.t}`:'absent-from-hint')
   t('optgroups',opts.length>0,JSON.stringify([...new Set(opts.map(o=>o.grp))]))
 }
 const fl=page.locator('summary:has-text("full bank list"), summary:has-text("bank list")')
 if(await fl.count()){await fl.first().click();await page.waitForTimeout(600)}
 const listTxt=await page.evaluate(()=>document.body.textContent)
 for(const[cand,label]of[['dbs','DBS Bank'],['federal','Federal Bank'],['dhanlaxmi','Dhanlaxmi Bank']])
   t(`ui_${cand}_in_panel`,listTxt.includes(label))
 t('ui_indusind_greyed_or_absent',!listTxt.includes('IndusInd Bank')||/IndusInd Bank[^·]*—/.test(listTxt))
 t('groups_labeled',/Verified \(\d+\)/.test(listTxt),listTxt.match(/(Verified|Review required|Legacy parser|Coming soon|Not supported) \(\d+\)/g)?.join('|'))
 t('reasons_shown',/— .{10,}/.test(listTxt))
 await page.screenshot({path:'tools/verify4/.local/ui_1280.png',fullPage:true})
 await page.setViewportSize({width:360,height:800}); await page.waitForTimeout(500)
 t('no_hscroll_360',await page.evaluate(()=>document.documentElement.scrollWidth<=370),await page.evaluate(()=>document.documentElement.scrollWidth))
 await page.screenshot({path:'tools/verify4/.local/ui_360.png',fullPage:true})
 await ctx.close()
}
// ---- leg B: full unified flow per candidate ----
const FILES={dbs:process.env.V4_F_DBS,federal:process.env.V4_F_FED,dhanlaxmi:process.env.V4_F_DHAN}
for(const[cand,fp]of Object.entries(FILES)){
 const ctx=await browser.newContext({viewport:{width:1280,height:900}})
 const page=await ctx.newPage(); await inject(page,tk)
 await page.goto(FE+'/dashboard',{waitUntil:'domcontentloaded'}); await page.waitForTimeout(2000)
 if(!await page.locator('input[type="file"]').count()){t(`flow_${cand}_upload`,false,'no file input');await ctx.close();continue}
 await page.locator('input[type="file"]').setInputFiles(fp); await page.waitForTimeout(800)
 await page.locator('button:has-text("Analyze")').first().click()
 await page.waitForFunction(()=>/Confirm all detected|VERIFIED|REVIEW|could not identify|not enabled yet|isn't fully supported|Password required/i.test(document.body.textContent),null,{timeout:120000}).catch(()=>{})
 await page.waitForTimeout(1200)
 const txt=await page.evaluate(()=>document.body.textContent)
 t(`flow_${cand}_analyze`,/VERIFIED|REVIEW|Confirm all detected|Confirm/i.test(txt))
 // per-doc bank select shows candidates selectable
 const sel=page.locator('select').first()
 if(await sel.count()){
   const opts=await sel.evaluateAll(os=>os.flatMap(s=>[...s.querySelectorAll('option')].map(o=>({v:o.value,t:o.textContent.trim(),dis:o.disabled}))))
   const c=opts.find(o=>o.v===cand); t(`flow_${cand}_opt_enabled`,c&&!c.dis,c?`${c.t} dis=${c.dis}`:'opt absent')
   fs.writeFileSync(`tools/verify4/.local/ui_sel_${cand}.json`,JSON.stringify(opts))
 }
 const cf=page.locator('button:has-text("Confirm all detected")')
 if(await cf.count()&&await cf.first().isEnabled().catch(()=>false)){await cf.first().click();await page.waitForTimeout(2500)}
 else{const one=page.locator('button:has-text("Confirm")').first(); if(await one.count()){await one.click();await page.waitForTimeout(2000)}}
 const pb=page.locator('button:has-text("Process confirmed")')
 await page.waitForFunction(()=>{const b=[...document.querySelectorAll('button')].find(x=>x.textContent.includes('Process confirmed'));return b&&!b.disabled},null,{timeout:90000}).catch(()=>{})
 if(await pb.count()){
   await pb.first().click()
   let ok='timeout'; const t0=Date.now()
   while(Date.now()-t0<420000){const bt=await page.evaluate(()=>document.body.textContent)
     if(/Download Excel|Report/i.test(bt)&&await page.locator('button:has-text("Download Excel"),button:has-text("Download"),a:has-text("Download")').count()){ok='report';break}
     if(/not processed|failed/i.test(bt)&&/Ready to process|processing/i.test(bt)===false){ok='failed-seen';break}
     await page.waitForTimeout(3000)}
   t(`flow_${cand}_report`,ok==='report',ok)
   t(`flow_${cand}_download_btn`,await page.locator('button:has-text("Download Excel"),button:has-text("Download"),a:has-text("Download")').count()>0)
 } else t(`flow_${cand}_process_btn`,false,'disabled/absent')
 await page.screenshot({path:`tools/verify4/.local/ui_flow_${cand}.png`,fullPage:true})
 await ctx.close()
}
fs.writeFileSync('tools/verify4/.local/ui4_results.json',JSON.stringify({results,consoleErrs},null,1))
console.log('console errors:',consoleErrs.length)
await browser.close()
