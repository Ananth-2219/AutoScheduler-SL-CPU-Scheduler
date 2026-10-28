// Dependency-free browser proof with an isolated Chromium profile (Node 22+).
const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const {mkdtemp, readFile, writeFile} = require('node:fs/promises');
const {tmpdir} = require('node:os');
const {join} = require('node:path');

const base = process.env.DEMO_URL || 'http://127.0.0.1:8000';
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
async function until(check, message) {
  for (let i = 0; i < 150; i++) {
    const result = await check();
    if (result) return result;
    await delay(100);
  }
  throw new Error(message);
}

(async () => {
  assert(process.env.CHROME, 'Set CHROME to the existing Chromium executable');
  const profile = await mkdtemp(join(tmpdir(), 'autoscheduler-overhead-browser-'));
  const chrome = spawn(process.env.CHROME, ['--headless', '--no-sandbox', '--disable-gpu',
    '--no-first-run', '--no-default-browser-check', '--remote-debugging-port=0',
    `--user-data-dir=${profile}`, 'about:blank'], {stdio:['ignore','ignore','pipe']});
  let launchError = '';
  chrome.stderr.on('data', data => {launchError += data.toString();});
  let socket;
  try {
    const port = await until(async () => {
      try {return Number((await readFile(join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0]);}
      catch {return null;}
    }, 'Chromium did not start').catch(error => {throw new Error(`${error.message}: ${launchError}`);});
    const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
    socket = new WebSocket(targets.find(t => t.type === 'page').webSocketDebuggerUrl);
    await new Promise((resolve, reject) => {socket.onopen = resolve; socket.onerror = reject;});
    let nextId = 0;
    const pending = new Map(), errors = [], external = [];
    socket.onmessage = event => {
      const data = JSON.parse(event.data);
      if (data.id) {
        const request = pending.get(data.id);
        pending.delete(data.id);
        data.error ? request.reject(new Error(data.error.message)) : request.resolve(data.result);
      } else if (data.method === 'Runtime.exceptionThrown') errors.push(data.params.exceptionDetails.text);
      else if (data.method === 'Runtime.consoleAPICalled' && ['error','warning'].includes(data.params.type))
        errors.push(JSON.stringify(data.params.args));
      else if (data.method === 'Network.requestWillBeSent' && !data.params.request.url.startsWith(base)
        && !data.params.request.url.startsWith('data:')) external.push(data.params.request.url);
    };
    const send = (method, params = {}) => new Promise((resolve, reject) => {
      const id = ++nextId; pending.set(id, {resolve,reject});
      socket.send(JSON.stringify({id,method,params}));
    });
    // Runtime evaluation only inspects the page. User actions use native input events.
    const inspect = async expression => {
      const result = await send('Runtime.evaluate', {expression,returnByValue:true});
      if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
      return result.result.value;
    };
    const text = () => inspect('document.body.innerText');
    const click = async selector => {
      const document = await send('DOM.getDocument', {depth:0});
      const node = await send('DOM.querySelector', {nodeId:document.root.nodeId,selector});
      await send('DOM.scrollIntoViewIfNeeded', {nodeId:node.nodeId});
      const box = await inspect(`(() => { const r = document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2}; })()`);
      await send('Input.dispatchMouseEvent', {type:'mousePressed',...box,button:'left',clickCount:1});
      await send('Input.dispatchMouseEvent', {type:'mouseReleased',...box,button:'left',clickCount:1});
    };
    const key = async key => {
      const windowsVirtualKeyCode = {End:35,Home:36,ArrowDown:40,Enter:13}[key];
      await send('Input.dispatchKeyEvent', {type:'keyDown',key,windowsVirtualKeyCode});
      await send('Input.dispatchKeyEvent', {type:'keyUp',key,windowsVirtualKeyCode});
    };
    await send('Page.enable'); await send('Runtime.enable'); await send('Network.enable');
    await send('Emulation.setDeviceMetricsOverride', {width:1440,height:1000,deviceScaleFactor:1,mobile:false});
    const noOverhead = async () => {
      assert.doesNotMatch(await inspect('document.body.textContent'), /overhead/i);
      assert.equal(await inspect('document.querySelectorAll(".controller-overhead").length'), 0);
    };
    await send('Page.navigate', {url:`${base}/#intelligence`});
    await until(async () => (await text()).includes('Panel B · Azure-Retrained'), 'Missing model evaluation');
    await noOverhead();
    const image = await send('Page.captureScreenshot', {captureBeyondViewport:true});
    await writeFile('/tmp/autoscheduler-dashboard-evaluation.png', Buffer.from(image.data,'base64'));
    const ax = await send('Accessibility.getFullAXTree');
    assert(!ax.nodes.some(node => /overhead/i.test(node.name?.value || '')));
    await click('details.panel > summary');
    assert((await text()).includes('240 synthetic development workloads'));
    await noOverhead();
    // A direct page navigation resets state and uses the same documented local page route.
    await send('Page.navigate', {url:`${base}/#simulation`});
    await until(async () => (await text()).includes('Workload Performance Metrics'), 'Missing simulation metrics');
    await noOverhead();
    await click('.selectors label:nth-child(2) select');
    await key('Home');
    for (let i = 0; i < 5; i++) await key('ArrowDown');
    await key('Enter');
    await until(async () => (await text()).includes('Quantum 2 · aging 8'), 'Missing Priority RR simulation');
    await noOverhead();
    await click('.selectors label:nth-child(2) select');
    await key('End'); await key('Enter');
    await until(async () => (await text()).includes('Policy Transition History'), 'Missing dynamic simulation');
    await noOverhead();
    for (const width of [1440,1024,768,320]) {
      await send('Emulation.setDeviceMetricsOverride', {width,height:1000,deviceScaleFactor:1,mobile:false});
      for (const page of ['overview','simulation','intelligence','review']) {
        await send('Page.navigate', {url:`${base}/#${page}`});
        const heading = {overview:'Scheduling & Evaluation Pipeline',simulation:'Workload Performance Metrics',intelligence:'Panel B · Azure-Retrained',review:'Offline-Replay Model Comparison'}[page];
        await until(async () => (await text()).includes(heading), 'Page did not load');
        await delay(100);
        await noOverhead();
        assert.equal(await inspect('document.documentElement.scrollWidth > innerWidth'), false, `${page} overflows at ${width}`);
      }
    }
    await until(async () => (await text()).includes('Offline-Replay Model Comparison'), 'Missing model comparison');
    assert((await text()).includes('Data-sufficiency gate'));
    assert((await text()).includes('cannot authorize a scheduler deployment'));
    assert.deepEqual(errors, []); assert.deepEqual(external, []);
    console.log(JSON.stringify({status:'PASS',viewports:[1440,1024,768,320],
      checks:['no overhead text or panels on any page','static and dynamic simulations',
        'no overhead accessibility labels','research limitations retained','no overflow','no console errors','no external requests'],
      screenshot:'/tmp/autoscheduler-dashboard-evaluation.png'},null,2));
  } finally {socket?.close(); chrome.kill();}
})().catch(error => {console.error(error);process.exitCode=1;});
