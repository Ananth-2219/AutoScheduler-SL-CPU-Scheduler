import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import test from 'node:test';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';

test('faculty pages expose only original v5 and keep cohorts separate',async()=>{
  const root=fileURLToPath(new URL('../../../',import.meta.url));
  const data=JSON.parse(execFileSync(`${root}.venv/bin/python`,['-c','import json; from dashboard.adapter import catalog; print(json.dumps(catalog()))'],{cwd:root,encoding:'utf8'}));
  const server=await createServer({root:fileURLToPath(new URL('../',import.meta.url)),server:{middlewareMode:true},appType:'custom'});
  try {
    const {Intelligence,Review}=await server.ssrLoadModule('/src/Research.jsx');
    const {Simulation}=await server.ssrLoadModule('/src/Simulation.jsx');
    const html=renderToStaticMarkup(React.createElement(Intelligence,{data}));
    assert.match(html,/49\.5% lower average waiting time/);
    assert.match(html,/Panel A · Original Dynamic ML v5/);
    assert.match(html,/Panel B · Azure-Retrained Dynamic ML v5/);
    assert.match(html,/33\.93% lower weighted score/);
    assert.match(html,/115 processes/);
    assert.match(html,/216 training \/ 72 validation \/ 72 test/);
    assert.match(html,/-9\.425/);
    assert.match(html,/dummy predictor performed better/i);
    assert.match(html,/Where Dynamic ML v5 Performs Better/);
    assert.match(html,/Where Tuned MLFQ Performs Better/);
    assert.match(html,/Not measured/);
    assert.doesNotMatch(html,/Azure-trained experimental|Guard candidate|quiet-period|v6|v4|v3/i);
    assert.doesNotMatch(html,/<select/);
    assert.match(html,/<details class="panel"><summary>Original v5 synthetic development/);
    assert.match(html,/<details class="panel"><summary>Historical offline classifier/);
    const simulation=renderToStaticMarkup(React.createElement(Simulation,{data,workload:'short_jobs',setWorkload:()=>{}}));
    assert.equal((simulation.match(/<option[^>]*>Dynamic ML \(v5\)<\/option>/g)||[]).length,1);
    assert.doesNotMatch(simulation,/v6|v4|v3|Azure tree|quiet-period/i);
    const review=renderToStaticMarkup(React.createElement(Review,{data}));
    assert.doesNotMatch(review,/Faculty questions|Expand an answer during the review/i);
    assert.doesNotMatch(review,/v6|quiet-period|Azure-trained experimental/i);
    assert.equal((html.match(/class="outcome-card /g)||[]).length,6);
    const css=readFileSync(new URL('./review.css',import.meta.url),'utf8');
    assert.match(css,/minmax\(min\(100%,240px\),1fr\)/);
    assert.match(css,/@media\(max-width:650px\)/);
    assert.match(html,/class="table-scroll"/);
  } finally {await server.close();}
});
