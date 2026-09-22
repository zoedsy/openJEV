// Optional browser tests. Install Playwright and a browser, then run:
// BROWSER_CHANNEL=msedge node --test tests/tickets-browser.test.cjs
// PLAYWRIGHT_MODULE can point at an existing Playwright installation.
// All inference responses below are explicitly synthetic test fixtures.
const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const U = require('../openjev/static/ticket-utils.js');
let playwright;
try { playwright = require(process.env.PLAYWRIGHT_MODULE || 'playwright'); } catch {}
let server, browser, baseURL, requests, handler, authRequired;
const pageErrors = [];
const staticDir = path.resolve(__dirname, '../openjev/static');
function fixture(score = 2) {
  const categories = U.CATEGORIES, low = Math.floor(score), high = Math.ceil(score);
  const probabilities = Object.fromEntries([0,1,2,3].map(i => [String(i), low===high ? Number(i===low) : i===low ? high-score : i===high ? score-low : 0]));
  return {model:'synthetic-browser-test-fixture',answers:{in_scope:{type:'noul',noul:.8},category:{type:'choice',choice:categories[0],confidence:1,probabilities:Object.fromEntries(categories.map((key,i)=>[key,i===0?1:0]))},priority:{type:'score',score,confidence:.5,probabilities}},meta:{model_id:'synthetic-browser-test-fixture',revision:'fixture-1',calibrated:false}};
}
function json(response, status, body, headers={}) { response.writeHead(status, {'Content-Type':'application/json', ...headers}); response.end(JSON.stringify(body)); }
if (playwright) {
  before(async () => {
    server = http.createServer((request, response) => {
      const url = new URL(request.url, 'http://localhost');
      if (url.pathname === '/api/status') return json(response,200,{status:'ready',backend:'diffusiongemma',location:'remote',model_id:'synthetic-browser-test-fixture',revision:'fixture-1',max_tokens:8192,calibrated:false,auth_required:authRequired});
      if (url.pathname === '/v1/systemone') { let text=''; request.on('data',data=>text+=data); request.on('end',()=>{ const body=JSON.parse(text); requests.push({body,authorization:request.headers.authorization}); handler(request,response,body,requests.length); }); return; }
      const file = url.pathname === '/tickets' ? 'tickets.html' : url.pathname.startsWith('/static/') ? url.pathname.slice(8) : '';
      if (!['tickets.html','tickets.js','tickets.css','ticket-utils.js','mark.svg'].includes(file)) { response.writeHead(404); response.end(); return; }
      const type = file.endsWith('.html') ? 'text/html' : file.endsWith('.css') ? 'text/css' : file.endsWith('.svg') ? 'image/svg+xml' : 'text/javascript';
      response.writeHead(200, {'Content-Type': type, 'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"}); response.end(fs.readFileSync(path.join(staticDir,file)));
    });
    await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
    baseURL = `http://127.0.0.1:${server.address().port}`;
    browser = await playwright.chromium.launch({headless:true,...(process.env.BROWSER_CHANNEL ? {channel:process.env.BROWSER_CHANNEL} : {})});
  });
  after(async () => { await browser?.close(); if (server) await new Promise(resolve=>server.close(resolve)); assert.deepEqual(pageErrors,[]); });
}
async function setup(t, options={}) {
  requests=[]; authRequired=false; handler=(req,res)=>json(res,200,fixture());
  const context = await browser.newContext({ viewport:{width:1440,height:1050}, acceptDownloads:true });
  t.after(()=>context.close()); const page = await context.newPage(); page.on('pageerror',error=>pageErrors.push(error.message));
  if (options.legacy) await page.addInitScript(()=>{localStorage.setItem('openjev.runs.v1','[]');localStorage.setItem('unrelated-setting','keep');});
  if (options.shortTimeout) await page.addInitScript(()=>{ const original=window.setTimeout; window.setTimeout=(fn,ms,...args)=>original(fn,ms===180000?60:ms,...args); });
  await page.goto(`${baseURL}/static/tickets.html`); await page.waitForFunction(()=>document.querySelector('#status-label').textContent.includes('ready'));
  return {page,context};
}
async function demo(page) { await page.click('#load-demo'); assert.equal(await page.locator('#ticket-rows tr').count(),5); }
async function complete(page, count=4) { await page.waitForFunction(count=>document.querySelector('#done-count').textContent===String(count),count); }
async function exported(page, type='json') { const promise=page.waitForEvent('download'); await page.click(`#export-${type}`); const download=await promise; return fs.readFileSync(await download.path(),'utf8'); }
const opts = {skip:!playwright, timeout:30000};
test('ticket workflow imports, evaluates only messages, filters, sorts, and exports exact inputs',opts,async t=>{
  const {page}=await setup(t); await demo(page);
  assert.equal(await page.textContent('#missing-count'),'1');
  await page.locator('[data-ticket-id="ticket-5"] .ticket-title').click();
  assert.match(await page.textContent('#dialog-content'),/not sent to the model/); await page.click('#close-dialog');
  handler=(req,res,body,index)=>json(res,200,fixture([.5,3,2,1][index-1]));
  await page.click('#start'); await complete(page); assert.equal(requests.length,4);
  assert.ok(requests.every(item=>item.body.state.ticket.message && Object.keys(item.body.questions).join(',')==='in_scope,category,priority'));
  await page.selectOption('#sort','priority'); assert.match(await page.locator('#ticket-rows tr').first().textContent(),/Delivery update/);
  await page.selectOption('#filter','priority'); assert.equal(await page.locator('#ticket-rows tr').count(),1);
  const output=JSON.parse(await exported(page)); assert.equal(output.tickets.length,5); assert.equal(output.tickets[4].response,null); assert.ok(output.run.questions.priority);
  assert.deepEqual(output.tickets[0].request,requests[0].body);
  assert.equal(await page.evaluate(()=>localStorage.length),0);
});
test('pause waits for the in-flight ticket; resume does not replay completed records',opts,async t=>{
  const {page}=await setup(t); await demo(page); let release;
  handler=(req,res,body,index)=>{ if(index===1) release=()=>json(res,200,fixture()); else json(res,200,fixture()); };
  await page.click('#start'); await page.waitForFunction(()=>document.querySelector('#ticket-rows .running'));
  await page.click('#pause'); assert.equal(await page.isDisabled('#pause'),true); release();
  await complete(page,1); await page.waitForFunction(()=>!document.querySelector('#start').disabled);
  assert.equal(requests.length,1); assert.equal(await page.textContent('#pending-count'),'3');
  await page.click('#start'); await complete(page); assert.equal(requests.length,4);
  assert.equal(new Set(requests.map(request=>request.body.state.ticket.title)).size,4);
});
test('429 honors a bounded retry and never advances before the accepted response',opts,async t=>{
  const {page}=await setup(t); await demo(page);
  handler=(req,res,body,index)=>index===1?json(res,429,{detail:'fixture busy'},{'Retry-After':'0'}):json(res,200,fixture());
  await page.click('#start'); await complete(page); assert.equal(requests.length,5);
  assert.equal(requests[0].body.state.ticket.title,requests[1].body.state.ticket.title);
  const output=JSON.parse(await exported(page)); assert.equal(output.tickets[0].attempts,2);
});
test('repeated 429 stops the batch, and manual retry recovers without replaying finished rows',opts,async t=>{
  const {page}=await setup(t); await demo(page);
  handler=(req,res)=>json(res,429,{detail:'fixture busy'},{'Retry-After':'0'});
  await page.click('#start'); await page.waitForFunction(()=>document.querySelector('#error-count').textContent==='1');
  assert.equal(requests.length,3); assert.equal(await page.textContent('#pending-count'),'3');
  handler=(req,res)=>json(res,200,fixture()); await page.click('#retry'); await complete(page); assert.equal(requests.length,7);
});
test('timeout pauses subsequent work and requires an explicit retry',opts,async t=>{
  const {page}=await setup(t,{shortTimeout:true}); await demo(page);
  handler=(req,res)=>setTimeout(()=>{if(!res.destroyed)json(res,200,fixture());},200);
  await page.click('#start'); await page.waitForFunction(()=>document.querySelector('#error-count').textContent==='1');
  assert.equal(requests.length,1); assert.equal(await page.textContent('#pending-count'),'3');
  assert.match(await page.textContent('#run-error'),/may still be processing/);
  await page.selectOption('#language-select','zh'); assert.match(await page.textContent('#run-error'),/可能仍在处理/);
  await page.selectOption('#language-select','en');
  handler=(req,res)=>json(res,200,fixture()); await page.click('#retry'); await complete(page); assert.equal(requests.length,5);
});
test('malformed responses are failures, not placeholder model results',opts,async t=>{
  const {page}=await setup(t); await demo(page); handler=(req,res)=>json(res,200,{answers:{}});
  await page.click('#start'); await page.waitForFunction(()=>document.querySelector('#error-count').textContent==='1');
  assert.equal(requests.length,1); assert.equal(await page.textContent('#done-count'),'0');
  const output=JSON.parse(await exported(page)); assert.equal(output.tickets[0].response,null); assert.equal(output.tickets[0].status,'error');
});
test('API keys stay in request headers and page memory; 401 stops later tickets',opts,async t=>{
  const {page}=await setup(t); authRequired=true; await page.reload(); await page.waitForSelector('#auth-box:not([hidden])'); await demo(page);
  assert.equal(await page.isDisabled('#start'),true);
  await page.fill('#api-key','bad-fixture-key'); await page.click('#save-key'); handler=(req,res)=>json(res,401,{detail:'fixture unauthorized'});
  await page.click('#start'); await page.waitForFunction(()=>document.querySelector('#error-count').textContent==='1'); assert.equal(requests.length,1);
  await page.fill('#api-key','valid-fixture-secret'); await page.click('#save-key'); handler=(req,res)=>json(res,200,fixture()); await page.click('#retry'); await complete(page);
  assert.ok(requests.slice(1).every(request=>request.authorization==='Bearer valid-fixture-secret'));
  const output=await exported(page); assert.equal(output.includes('fixture-secret'),false); assert.equal(output.includes('bad-fixture-key'),false);
  assert.equal(await page.evaluate(()=>localStorage.length+sessionStorage.length),0);
});
test('HTML stays plain text, unsafe links stay inert, and spreadsheet formulas are escaped',opts,async t=>{
  const {page}=await setup(t);
  await page.fill('#scope','A fictional shop'); await page.fill('#source',JSON.stringify([{title:'<img src=x onerror="window.ticketXSS=1">',message:'<script>window.ticketXSS=1</script>',url:'javascript:alert(1)'},{title:'=1+1',message:'A'}]));
  await page.click('#preview'); assert.equal(await page.locator('#ticket-rows img').count(),0);
  await page.locator('#ticket-rows .ticket-title').first().click(); assert.equal(await page.locator('#dialog-content script').count(),0); assert.equal(await page.locator('#dialog-content a').count(),0); assert.equal(await page.evaluate(()=>window.ticketXSS),undefined);
  await page.click('#close-dialog'); const csv=await exported(page,'csv'); assert.ok(csv.includes('"\'=1+1"'));
});
test('desktop and mobile layouts have no viewport overflow',opts,async t=>{
  const {page}=await setup(t); await demo(page);
  const artifactDir=process.env.TICKETS_SCREENSHOT_DIR;
  if(artifactDir) { fs.mkdirSync(artifactDir,{recursive:true}); await page.screenshot({path:path.join(artifactDir,'tickets-desktop.png'),fullPage:true}); }
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  if(artifactDir)await page.screenshot({path:path.join(artifactDir,'tickets-mobile.png'),fullPage:true});
  await page.selectOption('#language-select','zh'); assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  if(artifactDir)await page.screenshot({path:path.join(artifactDir,'tickets-mobile-zh.png'),fullPage:true});
  await page.locator('#ticket-rows .ticket-title').first().click(); assert.ok(await page.evaluate(()=>document.querySelector('dialog').getBoundingClientRect().right<=innerWidth));
});

test('file upload previews multiline CSV and double-start clicks create only one queue',opts,async t=>{
  const {page}=await setup(t);
  await page.fill('#scope','Shop service scope');
  await page.setInputFiles('#file-input',{name:'tickets-fixture.csv',mimeType:'text/csv',buffer:Buffer.from('title,message,channel,url\r\n"A","line 1\r\nline 2",,\r\n"B","second message",,')});
  await page.waitForFunction(()=>document.querySelector('#source').value.includes('line 2'));
  await page.click('#preview'); assert.equal(await page.locator('#ticket-rows tr').count(),2);
  await page.evaluate(()=>{const button=document.querySelector('#start');button.dispatchEvent(new MouseEvent('click'));button.dispatchEvent(new MouseEvent('click'));});
  await complete(page,2); assert.equal(requests.length,2); assert.equal(requests[0].body.state.ticket.message,'line 1\nline 2');
});
test('individual input rejection continues, while a dropped connection pauses later tickets',opts,async t=>{
  const {page}=await setup(t); await demo(page);
  handler=(req,res,body,index)=>{ if(index===1)json(res,422,{detail:'fixture input too long'}); else if(index===2){res.writeHead(200,{'Content-Type':'application/json','Content-Length':'1000'});res.write('{\"answers\":');setImmediate(()=>res.destroy());} else json(res,200,fixture()); };
  await page.click('#start'); await page.waitForFunction(()=>document.querySelector('#error-count').textContent==='2');
  assert.equal(requests.length,2); assert.equal(await page.textContent('#pending-count'),'2');
  assert.match(await page.textContent('#run-error'),/connection ended/);
});

test('English defaults, Chinese switching and validation are localized',opts,async t=>{
 const {page}=await setup(t);
 assert.equal(await page.getAttribute('html','lang'),'en');
 assert.equal(await page.inputValue('#language-select'),'en');
 assert.equal(/[\u4e00-\u9fff]/u.test(await page.locator('main').innerText()),false);
 await page.click('#preview');assert.match(await page.textContent('#import-error'),/Paste content/);
 await page.selectOption('#language-select','zh');assert.match(await page.textContent('#import-error'),/请先粘贴/);
 await demo(page);assert.match(await page.locator('#ticket-rows tr').first().textContent(),/整个商城/);
 await page.click('#show-rubric');assert.match(await page.textContent('#dialog-content'),/一小时/);await page.click('#close-dialog');
 await page.click('#start');await complete(page);const output=JSON.parse(await exported(page));
 assert.equal(output.run.language,'zh');assert.match(output.run.questions.priority.criteria[3],/一小时/);
 assert.deepEqual(await page.evaluate(()=>Object.keys(localStorage)),['openjev.locale']);
});
test('switching language mid-batch keeps the original scope and rules frozen',opts,async t=>{
 const {page}=await setup(t);await demo(page);let release;
 handler=(req,res,body,index)=>{if(index===1)release=()=>json(res,200,fixture());else json(res,200,fixture());};
 await page.click('#start');await page.waitForFunction(()=>document.querySelector('#ticket-rows .running'));
 await page.selectOption('#language-select','zh');release();await complete(page);
 assert.ok(requests.every(r=>r.body.questions.priority.criteria[3].includes('one hour')));
 assert.ok(requests.every(r=>r.body.state.service_scope.includes('fictional online shop')));
 assert.match(await page.textContent('#progress-label'),/已处理/);const output=JSON.parse(await exported(page));assert.equal(output.run.language,'en');
 await page.locator('#ticket-rows .ticket-title').first().click();assert.match(await page.textContent('#dialog-content'),/仍使用英文/);
});
test('only old demo history is removed; unrelated storage is preserved',opts,async t=>{
 const {page}=await setup(t,{legacy:true});
 assert.equal(await page.evaluate(()=>localStorage.getItem('openjev.runs.v1')),null);
 assert.equal(await page.evaluate(()=>localStorage.getItem('unrelated-setting')),'keep');
 assert.match(await page.textContent('#history-note'),/Old demo history/);
});
