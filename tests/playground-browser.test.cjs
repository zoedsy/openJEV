// Run with Playwright installed; all model responses are synthetic local fixtures.
// PLAYWRIGHT_MODULE=/path/to/playwright BROWSER_CHANNEL=msedge node --test tests/playground-browser.test.cjs
const {test,before,after}=require('node:test');
const assert=require('node:assert/strict');
const http=require('node:http');
const fs=require('node:fs');
const path=require('node:path');
let playwright;
try{playwright=require(process.env.PLAYWRIGHT_MODULE||'playwright');}catch{}
let server,browser,baseURL,requests,handler,currentStatus;
const errors=[];
const staticDir=path.resolve(__dirname,'../openjev/static');
const examples=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../openjev/examples.json'),'utf8'));
const json=(res,code,body)=>{res.writeHead(code,{'Content-Type':'application/json'});res.end(JSON.stringify(body));};
function fixture(body){
  const answers=Object.fromEntries(Object.entries(body.questions).map(([key,q])=>{
    if(q.type==='noul')return [key,{type:'noul',noul:.8}];
    if(q.type==='choice'){const keys=Object.keys(q.criteria);return [key,{type:'choice',choice:keys[0],confidence:1,probabilities:Object.fromEntries(keys.map((k,i)=>[k,i===0?1:0]))}];}
    return [key,{type:'score',score:1,confidence:1,probabilities:Object.fromEntries(q.criteria.map((_,i)=>[String(i),i===1?1:0])),legend:Object.fromEntries(q.criteria.map((x,i)=>[String(i),x]))}];
  }));
  return {model:'synthetic-test-fixture',answers,usage:{input_tokens:40,output_tokens:0},meta:{engine:'diffusiongemma-vllm',questions:Object.keys(answers).length,inference_ms:10,latency_ms:20,calibrated:false}};
}
if(playwright){
  before(async()=>{
    server=http.createServer((req,res)=>{
      const url=new URL(req.url,'http://localhost');
      if(url.pathname==='/api/status')return json(res,200,currentStatus);
      if(url.pathname==='/api/examples')return json(res,200,examples);
      if(url.pathname==='/v1/systemone'){let raw='';req.on('data',chunk=>raw+=chunk);req.on('end',()=>{const body=JSON.parse(raw);requests.push({body,authorization:req.headers.authorization});handler(req,res,body);});return;}
      const file=url.pathname==='/'?'index.html':url.pathname.startsWith('/static/')?url.pathname.slice(8):'';
      if(!['index.html','app.js','style.css','mark.svg'].includes(file)){res.writeHead(404);res.end();return;}
      res.writeHead(200,{'Content-Type':file.endsWith('.html')?'text/html':file.endsWith('.css')?'text/css':file.endsWith('.svg')?'image/svg+xml':'text/javascript','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"});
      res.end(fs.readFileSync(path.join(staticDir,file)));
    });
    await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));baseURL=`http://127.0.0.1:${server.address().port}`;
    browser=await playwright.chromium.launch({headless:true,...(process.env.BROWSER_CHANNEL?{channel:process.env.BROWSER_CHANNEL}:{})});
  });
  after(async()=>{await browser?.close();if(server)await new Promise(resolve=>server.close(resolve));assert.deepEqual(errors,[]);});
}
const opts={skip:!playwright,timeout:30000};
async function setup(t,options={}){
  requests=[];handler=(req,res,body)=>json(res,200,fixture(body));
  currentStatus={status:'ready',backend:'diffusiongemma',location:'remote',max_tokens:8192,model_id:'synthetic-test-fixture',revision:'fixture-1',auth_required:!!options.auth};
  const context=await browser.newContext({viewport:{width:1440,height:1050},acceptDownloads:true});t.after(()=>context.close());
  if(options.legacy)await context.addInitScript(()=>{localStorage.setItem('openjev.runs.v1',JSON.stringify([{id:1,request:{state:'legacy-content-to-remove',questions:{}},result:{answers:{}}}]));localStorage.setItem('unrelated-key','keep-me');});
  if(options.shortTimeout)await context.addInitScript(()=>{const original=window.setTimeout;window.setTimeout=(fn,ms,...args)=>original(fn,ms===120000?60:ms,...args);});
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  await page.goto(`${baseURL}/?example=${options.example||'support'}`);await page.waitForFunction(()=>document.querySelector('#presets').children.length===5&&document.querySelector('#status-label').textContent.includes('ready'));
  return {page,context};
}
async function run(page){await page.click('#run-button');await page.waitForSelector('.result-card');}

test('English defaults, old app history is cleared narrowly, and examples contain only current generic demos',opts,async t=>{
  const {page}=await setup(t,{legacy:true,example:'product_quality'});
  assert.equal(await page.getAttribute('html','lang'),'en');assert.equal(await page.inputValue('#language-select'),'en');
  assert.match(await page.inputValue('#state-input'),/Fictional product listing/);
  assert.equal(await page.getAttribute('.tickets-link','href'),'/tickets');assert.equal(await page.textContent('.tickets-link'),'Ticket triage');
  assert.equal(await page.evaluate(()=>localStorage.getItem('openjev.runs.v1')),null);
  assert.equal(await page.evaluate(()=>localStorage.getItem('unrelated-key')),'keep-me');
  assert.match(await page.textContent('#toast'),/Previous-version local demo history was cleared/);
  await page.click('[data-view="history"]');assert.match(await page.textContent('#history-list'),/No runs yet/);
  assert.doesNotMatch(await page.textContent('body'),/legacy-content-to-remove/);
  assert.ok(examples.every(e=>e.state&&e.questions&&e.state_zh&&e.questions_zh));
  assert.deepEqual(examples.map(e=>e.id),['support','chinese','review','facts','product_quality']);
});

test('English and Chinese switch static UI, built-in input, states, and editor; custom input is preserved',opts,async t=>{
  const {page,context}=await setup(t,{example:'product_quality'});
  await page.selectOption('#language-select','zh');
  assert.equal(await page.getAttribute('html','lang'),'zh-CN');assert.equal(await page.textContent('.tickets-link'),'工单分流');
  assert.match(await page.textContent('#status-label'),/GPU 模型已就绪/);assert.match(await page.inputValue('#state-input'),/纯虚构商品页面/);
  assert.match(await page.textContent('#questions'),/商品容量是否一致/);
  await page.click('#add-question');assert.equal(await page.textContent('#dialog-title'),'添加一个问题');assert.match(await page.inputValue('#edit-criteria'),/描述选项/);
  await page.selectOption('#edit-type','noul');await page.fill('#edit-id','custom');await page.fill('#edit-instructions','A user-written statement.');await page.click('#question-form button[type="submit"]');
  const original=await page.inputValue('#state-input');
  await page.selectOption('#language-select','en');assert.equal(await page.inputValue('#state-input'),original);assert.match(await page.textContent('#questions'),/A user-written statement/);
  assert.equal(await page.textContent('#run-label'),'Run evaluation');assert.match(await page.textContent('#status-label'),/GPU model ready/);
  await page.selectOption('#language-select','zh');
  const another=await context.newPage();await another.goto(baseURL);await another.waitForFunction(()=>document.documentElement.lang==='zh-CN');
  assert.equal(await another.inputValue('#language-select'),'zh');
});

test('inference, authentication, localized results, exact export, and v2 history remain functional',opts,async t=>{
  const {page}=await setup(t,{auth:true});
  assert.match(await page.textContent('#model-notice'),/requires an API key/);
  await page.fill('#local-key','test-key');await page.click('#set-key');await run(page);
  assert.equal(requests.length,1);assert.equal(requests[0].authorization,'Bearer test-key');
  assert.equal(await page.locator('.result-card').count(),3);assert.match(await page.textContent('.result-summary'),/Model service/);
  assert.equal(await page.evaluate(()=>JSON.parse(localStorage.getItem('openjev.runs.v2')).length),1);
  const downloadPromise=page.waitForEvent('download');await page.click('#download-result');const download=await downloadPromise;
  const exported=JSON.parse(fs.readFileSync(await download.path(),'utf8'));assert.deepEqual(exported.request,requests[0].body);
  assert.match(await page.textContent('#toast'),/Result JSON downloaded/);
  await page.selectOption('#language-select','zh');assert.match(await page.textContent('.stale-banner'),/输入已修改/);assert.match(await page.textContent('.result-summary'),/模型服务/);
  await page.click('[data-view="history"]');assert.equal(await page.locator('.history-row').count(),1);await page.click('.history-row');assert.equal(await page.inputValue('#state-input'),requests[0].body.state);
  page.once('dialog',dialog=>dialog.accept());await page.click('[data-view="history"]');await page.click('#clear-history');assert.equal(await page.evaluate(()=>localStorage.getItem('openjev.runs.v2')),null);assert.match(await page.textContent('#toast'),/运行记录已清空/);
});

test('validation and editor errors follow locale without sending invalid requests',opts,async t=>{
  const {page}=await setup(t);
  await page.fill('#state-input','');await page.click('#run-button');assert.match(await page.textContent('#error-message'),/Enter some context/);
  await page.selectOption('#language-select','zh');assert.match(await page.textContent('#error-message'),/请先输入/);
  await page.click('[data-preset="support"]');await page.click('#add-question');await page.fill('#edit-id','extra');await page.fill('#edit-instructions','demo');await page.fill('#edit-criteria','{');await page.click('#question-form button[type="submit"]');assert.match(await page.textContent('#form-error'),/不是有效的 JSON/);
  await page.selectOption('#language-select','en');assert.match(await page.textContent('#form-error'),/not valid JSON/);assert.equal(await page.textContent('#dialog-title'),'Add a question');
  assert.equal(requests.length,0);
});

test('bounded timeout does not retry and keeps server-processing caveat in both locales',opts,async t=>{
  const {page}=await setup(t,{shortTimeout:true});handler=()=>{};
  await page.click('#run-button');await page.waitForFunction(()=>!document.querySelector('#error-message').hidden);
  assert.match(await page.textContent('#error-message'),/server may still be processing/);assert.equal(requests.length,1);assert.equal(await page.isEnabled('#run-button'),true);
  // Editing marks this as a custom input, so switching UI language preserves its error.
  await page.fill('#state-input','custom input');await page.selectOption('#language-select','zh');assert.match(await page.textContent('#error-message'),/服务器可能仍在处理/);assert.equal(requests.length,1);
});

test('desktop and mobile layouts fit both languages',opts,async t=>{
  const {page}=await setup(t,{example:'product_quality'});await run(page);
  for(const language of ['en','zh']){
    await page.selectOption('#language-select',language);
    for(const width of [1440,390]){await page.setViewportSize({width,height:1000});const size=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth}));assert.ok(size.scroll<=size.width,JSON.stringify({language,...size}));if(process.env.PLAYGROUND_SCREENSHOTS){const dir=path.resolve(__dirname,'../artifacts');fs.mkdirSync(dir,{recursive:true});await page.screenshot({path:path.join(dir,`playground-mock-${language}-${width}.png`),fullPage:true});}}
  }
});
