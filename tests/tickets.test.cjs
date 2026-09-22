// node --test tests/tickets.test.cjs; no model or additional dependencies required.
const {test,beforeEach}=require('node:test');
const assert=require('node:assert/strict');
const U=require('../openjev/static/ticket-utils.js');
beforeEach(()=>U.setLocale('en'));
test('CSV preserves quoted commas, doubled quotes, line breaks, BOM and message spacing',()=>{
 const rows=U.parseSource('\uFEFFtitle,message,channel,url\r\n"A, B","First line\r\nSecond ""quoted"" line",Web form,https://example.org/ticket\r\n','csv');
 assert.equal(rows.length,1);assert.equal(rows[0].title,'A, B');assert.equal(rows[0].message,'First line\r\nSecond "quoted" line');assert.equal(rows[0].status,'pending');
 assert.equal(U.parseSource('[{"title":"T","message":"  original spacing  "}]')[0].message,'  original spacing  ');
 assert.equal(U.parseSource('[{"title":"T","message":"   "}]')[0].status,'incomplete');
});
test('Chinese headings and JSON wrappers work; absent messages never become negative results',()=>{
 const row=U.parseSource('标题,内容,渠道,链接\n只有标题,,网页表单,')[0];assert.equal(row.status,'incomplete');assert.equal(row.response,null);assert.throws(()=>U.makeRequest(row,'Shop support'),/valid title and message/);
 assert.equal(U.parseSource('{"tickets":[{"title":"T","message":"A","channel":"Web form"}]}')[0].channel,'Web form');
});
test('malformed CSV, wrong field types and oversized imports fail explicitly',()=>{
 for(const[input,pattern]of[['title,message\nT,"unfinished',/not closed/],['title,message\nT,A,B',/columns/],['title,title,message\nA,B,C',/duplicated/],['title,message\n"T"oops,A',/closing CSV quote/],['title,notes\nT,A',/requires title and message/],['{}',/ticket array/]])assert.throws(()=>U.parseSource(input),pattern);
 assert.throws(()=>U.parseSource(JSON.stringify(Array(101).fill({title:'T',message:'A'}))),/100 tickets/);
 assert.throws(()=>U.parseSource('x'.repeat(U.LIMITS.sourceBytes+1)),/2 MiB/);
 assert.equal(U.parseSource('[{"title":"T","message":42}]')[0].status,'invalid');
 assert.equal(U.parseSource('[{"title":"T","message":"A","channel":["Web"]}]')[0].status,'invalid');
 assert.equal(U.parseSource('[null]')[0].status,'invalid');
 assert.equal(U.parseSource(JSON.stringify([{title:'T',message:'x'.repeat(16001)}]))[0].status,'invalid');
});
test('unsafe links remain inert; duplicates are retained with a warning',()=>{
 const input={title:'<img onerror=alert(1)>',message:'A',url:'javascript:alert(1)'};const rows=U.parseSource(JSON.stringify([input,input]));
 assert.equal(rows[0].title,input.title);assert.equal(U.safeURL(rows[0].url),null);assert.equal(U.safeURL('data:text/html,evil'),null);assert.equal(U.safeURL('https://user:secret@example.org'),null);assert.ok(U.safeURL('https://example.org/ticket'));assert.ok(rows[1].warnings.some(w=>w.key==='duplicateRow'));
});
test('CSV exports escape spreadsheet formula prefixes, whitespace and controls',()=>{
 for(const value of['=1+1','+SUM(A1:A3)','-10+20','@cmd',' \t=1+1','\u0000=1+1','\ttext','\ntext'])assert.ok(U.csvCell(value).startsWith('"\''),value);
 assert.equal(U.csvCell('Ticket, "A"'),'"Ticket, ""A"""');
 const csv=U.toCSV(U.parseSource('[{"title":"=cmd()","message":"A"}]'),null);assert.ok(csv.startsWith('\uFEFF'));assert.ok(csv.includes('"\'=cmd()"'));
});
test('fictional shop examples build only the supported request fields and frozen rubric',()=>{
 const demo=U.demo(),rows=U.parseSource(JSON.stringify(demo.tickets));assert.equal(rows.length,5);assert.equal(rows.filter(r=>r.status==='pending').length,4);assert.ok(rows.every(r=>r.fictional&&r.title.includes('fictional demo')));
 const rubric=U.questions(),request=U.makeRequest(rows[0],demo.scope,rubric);assert.deepEqual(Object.keys(request.state),['service_scope','ticket']);assert.deepEqual(Object.keys(request.state.ticket),['title','message','channel']);assert.deepEqual(Object.keys(request.questions),['in_scope','category','priority']);assert.deepEqual(Object.keys(request.questions.category.criteria),U.CATEGORIES);assert.equal(request.questions.priority.criteria.length,4);
 rubric.category.criteria.other='changed';assert.notEqual(request.questions.category.criteria.other,'changed');assert.throws(()=>U.makeRequest(rows[0],''),/Service scope/);
});
function result(){return{answers:{in_scope:{type:'noul',noul:.7},category:{type:'choice',choice:'payment',confidence:.5,probabilities:Object.fromEntries(U.CATEGORIES.map(key=>[key,key==='payment'?1:0]))},priority:{type:'score',score:2,confidence:.5,probabilities:{0:0,1:0,2:1,3:0}}}};}
test('malformed responses never become placeholder decisions',()=>{
 assert.equal(U.validateResponse(result()).answers.priority.score,2);
 for(const mutate of[r=>r.answers.in_scope.noul=null,r=>r.answers.category.choice='invented',r=>r.answers.priority.score=4,r=>r.answers.priority.probabilities['3']=1,r=>r.answers.category.confidence=NaN,r=>delete r.answers.priority]){const r=result();mutate(r);assert.throws(()=>U.validateResponse(r));}
});
test('JSON exports preserve messages, exact request, original rules and raw responses without authentication',()=>{
 const demo=U.demo(),rows=U.parseSource(JSON.stringify(demo.tickets));const run={id:'run-1',service_scope:demo.scope,language:'en',questions:U.questions(),model:{model_id:'fixture-model',revision:'r1'}};
 rows[0].request=U.makeRequest(rows[0],run.service_scope,run.questions);rows[0].response=result();rows[0].status='done';const exported=U.exportJSON(rows,run,'fixture');
 assert.equal(exported.tickets[0].message,rows[0].message);assert.deepEqual(exported.tickets[0].response,result());assert.deepEqual(exported.run.questions,run.questions);assert.equal(exported.tickets[4].response,null);assert.equal(JSON.stringify(exported).includes('Authorization'),false);assert.equal(exported.format,'openjev-tickets-v1');
});
test('English is the default and Chinese changes validation, examples and rule text, with stable category keys',()=>{
 assert.equal(U.getLocale(),'en');assert.match(U.t('start'),/Start triage/);const english=U.questions();
 U.setLocale('zh');assert.equal(U.t('start'),'开始分流 →');assert.throws(()=>U.parseSource(''),/请先粘贴/);assert.match(U.demo().tickets[0].title,/虚构演示/);assert.match(U.questions().priority.criteria[3],/一小时/);assert.deepEqual(Object.keys(U.questions().category.criteria),Object.keys(english.category.criteria));assert.match(english.priority.criteria[3],/one hour/);
 const issue={key:'missingTitle',params:{}};assert.equal(U.describe(issue),'缺少标题。');U.setLocale('en');assert.equal(U.describe(issue),'Missing title.');
});
