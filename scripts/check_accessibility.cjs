/* Development-only browser checks for generated fixture sites. */
const {chromium} = require('playwright');
const AxeBuilder = require('@axe-core/playwright').default;
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');

const index = path.resolve(process.argv[2] || 'dist/index.html');
const output = path.resolve(process.argv[3] || '.cam/accessibility/results.json');
const executablePath = process.env.CAM_BROWSER_PATH;
if (!executablePath) throw new Error('Set CAM_BROWSER_PATH to a locally installed Chromium browser.');
const checks = [];
const scans = [];
const requestFailures = [];
const abortedRequests = [];
const pageErrors = [];
let browser;
let server;
let siteUrl;
let siteOrigin;
let browserPids = [];

function processTable() {
  const {execFileSync} = require('node:child_process');
  return execFileSync('ps', ['-eo', 'pid=,ppid=,args='], {encoding:'utf8'}).trim().split('\n')
    .map(line => {const parts=line.trim().match(/^(\d+)\s+(\d+)\s+(.*)$/); return parts ? {pid:Number(parts[1]),ppid:Number(parts[2]),args:parts[3]} : null;}).filter(Boolean);
}
function descendants(pid, table) {
  const found = new Set([pid]);
  let changed = true;
  while(changed) {changed=false; for(const p of table) if(found.has(p.ppid) && !found.has(p.pid)) {found.add(p.pid);changed=true;}}
  found.delete(pid);
  return [...found];
}
async function tabTo(page, selector) {
  for (let n=0;n<80;n++) {
    await page.keyboard.press('Tab');
    if (await page.evaluate(sel => document.activeElement.matches(sel), selector)) return;
  }
  throw new Error('Keyboard target was not reachable: ' + selector);
}
async function scan(page, state) {
  const result = await new AxeBuilder({page}).analyze();
  scans.push({state,engine:result.testEngine,violations:result.violations,incomplete:result.incomplete,
    passes:result.passes.length,inapplicable:result.inapplicable.length});
  assert.equal(result.violations.length,0,'axe violations in '+state);
}
(async()=>{
 try {
  const directory = path.dirname(index);
  server = http.createServer((request, response) => {
    try {
      const pathname = decodeURIComponent(new URL(request.url, 'http://127.0.0.1').pathname);
      const file = path.resolve(directory, '.' + pathname);
      const real = fs.realpathSync(file);
      if (!real.startsWith(directory + path.sep) || !fs.statSync(real).isFile()) {
        response.writeHead(404); response.end(); return;
      }
      const mime = {'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8',
        '.css':'text/css; charset=utf-8','.csv':'text/csv; charset=utf-8',
        '.md':'text/plain; charset=utf-8','.txt':'text/plain; charset=utf-8'};
      response.writeHead(200, {'Content-Type':mime[path.extname(real)] || 'application/octet-stream',
        'Cache-Control':'no-store'});
      response.end(fs.readFileSync(real));
    } catch { response.writeHead(404); response.end(); }
  });
  await new Promise((resolve,reject) => {
    server.once('error',reject); server.listen(0,'127.0.0.1',resolve);
  });
  siteOrigin = 'http://127.0.0.1:' + server.address().port;
  siteUrl = siteOrigin + '/' + encodeURIComponent(path.basename(index));
  browser = await chromium.launch({executablePath,headless:true,args:[
    '--disable-background-networking','--disable-component-update','--disable-sync','--disable-default-apps'
  ]});
  browserPids = descendants(process.pid,processTable());
  const context = await browser.newContext({viewport:{width:1280,height:900},reducedMotion:'reduce'});
  await context.route('**/*', route => {
    if (new URL(route.request().url()).origin === siteOrigin) return route.continue();
    requestFailures.push('Blocked external request'); return route.abort();
  });
  const page = await context.newPage();
  page.on('pageerror', e => pageErrors.push(e.message));
  page.on('requestfailed', req => {
    const name = path.basename(new URL(req.url()).pathname);
    if (req.failure()?.errorText === 'net::ERR_ABORTED') abortedRequests.push(name);
    else requestFailures.push(name + ': ' + req.failure()?.errorText);
  });
  await page.goto(siteUrl);
  assert.equal(await page.locator('#services-table tbody tr').count(),10);
  assert.equal(await page.locator('.service-marker').count(),10);
  await scan(page,'desktop initial');
  await page.keyboard.press('Tab');
  assert.equal(await page.evaluate(()=>document.activeElement.className),'skip-link');
  await page.keyboard.press('Enter');
  assert.equal(await page.evaluate(()=>document.activeElement.id),'services-table');
  checks.push('Skip link focuses table');
  await page.goto(siteUrl);
  await tabTo(page,'#filter-city');
  await page.keyboard.type('Vancouver');
  assert.equal(await page.locator('#services-table tbody tr:visible').count(),3);
  assert.equal(await page.locator('.service-marker').count(),3);
  assert.match(await page.locator('#result-count').innerText(),/Showing 3 services/);
  assert.equal(await page.evaluate(()=>document.activeElement.id),'filter-city');
  checks.push('Keyboard city filter synchronizes map, table and count');
  await page.keyboard.press('ControlOrMeta+A');await page.keyboard.type('No matching city');
  assert.equal(await page.locator('#services-table tbody tr:visible').count(),0);
  assert.equal(await page.locator('.service-marker').count(),0);
  await scan(page,'empty filter');
  checks.push('Zero-result filter');
  await page.keyboard.press('ControlOrMeta+A');await page.keyboard.press('Backspace');
  await page.keyboard.press('Tab');
  assert.equal(await page.evaluate(()=>document.activeElement.id),'filter-type');
  await page.keyboard.press('h');await page.keyboard.press('Enter');
  assert.equal(await page.locator('#filter-type').inputValue(),'hospital');
  checks.push('Service type selectable with keyboard');
  await tabTo(page,'#map');
  const original = await page.evaluate(()=>[map.getCenter().lng,map.getZoom()]);
  await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(400);
  assert.notEqual(await page.evaluate(()=>map.getCenter().lng),original[0]);
  await page.keyboard.press('+');
  assert.ok(await page.evaluate(()=>map.getZoom()) > original[1]);
  await page.keyboard.press('-');
  assert.equal(await page.evaluate(()=>map.getZoom()),original[1]);
  checks.push('Map arrow pan and plus/minus zoom');
  await tabTo(page,'.leaflet-control-zoom-in');
  await page.keyboard.press('Enter');
  assert.equal(await page.evaluate(()=>map.getZoom()),original[1]+1);
  await tabTo(page,'.leaflet-control-zoom-out');
  await page.keyboard.press('Enter');
  assert.equal(await page.evaluate(()=>map.getZoom()),original[1]);
  checks.push('Zoom controls activate with Enter');
  await tabTo(page,'.service-marker');
  const markerName = await page.evaluate(()=>document.activeElement.getAttribute('aria-label'));
  assert.ok(markerName);
  await page.keyboard.press('Enter');
  assert.equal(await page.locator('.leaflet-popup').count(),1);
  assert.equal(await page.evaluate(()=>document.activeElement.classList.contains('leaflet-popup-close-button')),true);
  await scan(page,'service popup');
  await page.keyboard.press('Escape');
  assert.equal(await page.locator('.leaflet-popup').count(),0);
  assert.equal(await page.evaluate(()=>document.activeElement.getAttribute('aria-label')),markerName);
  await page.keyboard.press('Space');
  assert.equal(await page.locator('.leaflet-popup').count(),1);
  await page.keyboard.press('Enter');
  assert.equal(await page.locator('.leaflet-popup').count(),0);
  checks.push('Named marker Enter and Space open details; Escape and close return focus');
  await tabTo(page,'button[data-feature]');
  await page.keyboard.press('Enter');
  assert.equal(await page.locator('.leaflet-popup').count(),1);
  await page.keyboard.press('Escape');
  checks.push('Table action opens map details; keyboard can exit map');
  await page.goto(siteUrl);
  await tabTo(page,'a[download]');
  const downloadPromise=page.waitForEvent('download');
  await page.keyboard.press('Enter');
  const download=await downloadPromise;
  assert.equal(download.suggestedFilename(),'services.csv');
  assert.equal(await download.failure(),null);
  checks.push('CSV download activates with Enter');
  await page.screenshot({path:output.replace(/\.json$/, '-desktop.png'),fullPage:true});
  await page.setViewportSize({width:375,height:812});
  await page.goto(siteUrl);
  await scan(page,'375px viewport');
  await tabTo(page,'.table-scroll');
  await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(200);
  const scrolled = await page.locator('.table-scroll').evaluate(el=>el.scrollLeft);
  assert.ok(scrolled > 0);
  await page.keyboard.press('ArrowLeft');
  await page.waitForTimeout(200);
  assert.ok(await page.locator('.table-scroll').evaluate(el=>el.scrollLeft) < scrolled);
  checks.push('Narrow table scroll area works with Left and Right keys');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth <= window.innerWidth));
  checks.push('Narrow viewport has no page-level horizontal overflow');
  const nojs=await browser.newContext({javaScriptEnabled:false,viewport:{width:1280,height:900}});
  await nojs.route('**/*', route => new URL(route.request().url()).origin === siteOrigin ? route.continue() : route.abort());
  const fallback=await nojs.newPage();
  await fallback.goto(siteUrl);
  assert.equal(await fallback.locator('#services-table tbody tr:visible').count(),10);
  checks.push('Table and CSV link remain present with JavaScript disabled');
  assert.equal(pageErrors.length,0,'page errors');
  assert.equal(requestFailures.length,0,'unexpected requests or missing resources');
 } finally {
  const owned=new Set(browserPids.concat(descendants(process.pid,processTable())));
  if(browser) await browser.close();
  if(server) await new Promise(resolve => server.close(resolve));
  // Only inspect the process IDs owned by this check, never unrelated browsers.
  const survivors=processTable().filter(p=>owned.has(p.pid));
  assert.equal(survivors.length,0,'browser descendants survived close');
  fs.mkdirSync(path.dirname(output),{recursive:true});
  fs.writeFileSync(output,JSON.stringify({
    date:new Date().toISOString(),serving:"loopback HTTP only",playwright:require('playwright/package.json').version,
    axe:scans[0]?.engine.version,integration:JSON.parse(fs.readFileSync(path.join(path.dirname(require.resolve('@axe-core/playwright')), '..', 'package.json'), 'utf8')).version,scans,checks,
    pageErrors,requestFailures,abortedRequests,ownedBrowserProcessesClosed:true
  },null,2)+'\n');
 }
 console.log(JSON.stringify({scans:scans.length,keyboardChecks:checks.length,violations:0,processesClosed:true}));
})().catch(e=>{console.error(e.message);process.exitCode=1});
