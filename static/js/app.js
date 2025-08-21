
document.getElementById('analyzeBtn').addEventListener('click', async function(){
  const btn = this;
  btn.disabled = true;
  btn.textContent = 'In Progress...';
  document.getElementById('status').textContent = 'Training & predicting — please wait';
  document.getElementById('results').innerHTML = '';
  try{
    const res = await fetch('/analyze', {method:'POST'});
    const data = await res.json();
    if(data.status !== 'ok'){
      document.getElementById('status').textContent = 'Error: ' + (data.error || 'unknown');
      return;
    }
    document.getElementById('status').textContent = 'Done';
    const results = data.results || {};
    Object.keys(results).forEach(pair => {
      const r = results[pair];
      const box = document.createElement('div');
      box.className = 'box';
      const pred = (r.prediction || 'N/A').toUpperCase();
      const conf = r.confidence!==undefined ? (r.confidence + '%') : '';
      const mode = r.mode || '';
      const reason = r.reason || '';
      const last = r.last_candle ? `O:${r.last_candle.o} H:${r.last_candle.h} L:${r.last_candle.l} C:${r.last_candle.c}` : 'N/A';
      const prob = r.prob_call!==undefined && r.prob_call!==null ? r.prob_call : '';
      box.innerHTML = `<h3>${pair}</h3>
                       <div class="pred ${pred.toLowerCase()}">${pred} ${conf}</div>
                       <div class="mode">Mode: ${mode}</div>
                       <div class="prob">Prob CALL: ${prob}</div>
                       <div class="last">Last candle: ${last}</div>
                       <div class="reason">${reason}</div>`;
      document.getElementById('results').appendChild(box);
    });
  }catch(err){
    document.getElementById('status').textContent = 'Request failed: ' + err;
  }finally{
    btn.disabled = false;
    btn.textContent = 'Analyze';
  }
});
