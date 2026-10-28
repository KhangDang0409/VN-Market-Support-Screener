'use strict';
// Optional: paste your public repository URL here.
const GITHUB_REPOSITORY_URL = '';
const $=id=>document.getElementById(id);
let running=false, revision=0;
function changed(){revision++;$('results').hidden=true;$('status').textContent='Settings changed. Click Run Screener to apply.';}
$('form').addEventListener('input',changed);
for(const [id,delta] of [['less',-5],['more',5]]) $(id).onclick=()=>{$('liquidity').value=Math.max(1,Number($('liquidity').value)+delta);changed();};
function source(url){if(/^https:\/\/github\.com\/[\w.-]+\/[\w.-]+\/?$/.test(url))$('source').href=url;}
if(GITHUB_REPOSITORY_URL)source(GITHUB_REPOSITORY_URL);else fetch('/api/project').then(r=>r.json()).then(d=>source(d.github_url)).catch(()=>{});
$('form').onsubmit=async e=>{
 e.preventDefault();if(running)return;running=true;const version=revision;$('run').disabled=true;$('results').hidden=true;$('status').classList.remove('error');$('status').textContent='Scanning the market… This can take a few minutes.';
 try{
  const r=await fetch('/api/screen',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({tickers:$('tickers').value,liquidity:Number($('liquidity').value)})});
  let data;try{data=await r.json();}catch{throw Error(`Server error (HTTP ${r.status}). Check Vercel runtime logs.`);}
  if(!r.ok)throw Error(data.error||'Scan failed.');if(version!==revision)return;
  $('status').textContent=data.rows.length?`Found ${data.rows.length} matching stocks. ${data.cached?'Cached results':'New scan'} · ${new Date(data.scanned_at*1000).toLocaleString()}`:'No tickers meet the criteria in the returned data. Yahoo Finance may also return missing or insufficient data; this is not confirmation that every ticker was evaluated.';
  if(!data.rows.length)return;
  const keys=['Ticker','Price','Setup','Support Level','Distance','Liquidity','Chart'];$('head').replaceChildren();$('body').replaceChildren();const hr=document.createElement('tr');
  keys.forEach(k=>{const th=document.createElement('th');th.textContent=k==='Liquidity'?'Liquidity (Bil VND)':k;hr.append(th);});$('head').append(hr);
  data.rows.forEach(row=>{const tr=document.createElement('tr');keys.forEach(k=>{const td=document.createElement('td');if(k==='Chart'){const a=document.createElement('a');a.href=row[k];a.textContent='Fireant ↗';a.target='_blank';a.rel='noopener noreferrer';td.append(a);}else td.textContent=row[k];tr.append(td);});$('body').append(tr);});
  $('results').hidden=false;Plotly.purge('chart');$('chart').replaceChildren();if(data.chart)await Plotly.newPlot('chart',data.chart.data,data.chart.layout,{responsive:true,displaylogo:false});else $('chart').textContent=data.chart_error;
 }catch(err){if(version===revision){$('status').textContent=err.message;$('status').classList.add('error');}}
 finally{running=false;$('run').disabled=false;}
};
