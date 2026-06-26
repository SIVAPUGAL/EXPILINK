// barcode_scan.js — wires UI, listens for barcodeDetected, calls /api/lookup and /api/scan
console.log('barcode_scan.js loaded');

document.addEventListener('DOMContentLoaded', ()=>{
  const scannerTarget = document.createElement('div'); scannerTarget.id='html5qr-scanner'; scannerTarget.style.width='100%'; scannerTarget.style.height='100%';
  const scanBox = document.getElementById('scanBox');
  scanBox.appendChild(scannerTarget);
  const overlay = document.createElement('div'); overlay.className='scan-overlay'; scanBox.appendChild(overlay);

  const scanner = new ExpiScanner('html5qr-scanner');
  const cameraBtn = document.getElementById('cameraBtn');
  const scanInput = document.getElementById('barcodeInput');
  const historyList = document.getElementById('historyList');
  const modeInventory = document.getElementById('modeInventory');
  const modeSales = document.getElementById('modeSales');
  let currentMode = 'inventory';

  modeInventory.addEventListener('click', ()=>{ currentMode='inventory'; modeInventory.classList.add('active'); modeSales.classList.remove('active'); });
  modeSales.addEventListener('click', ()=>{ currentMode='sales'; modeSales.classList.add('active'); modeInventory.classList.remove('active'); });

  cameraBtn.addEventListener('click', async ()=>{
    if(cameraBtn.dataset.running==='1'){
      await scanner.stopCamera(); cameraBtn.dataset.running='0'; cameraBtn.innerText='Enable Camera';
    } else {
      await scanner.startCamera(true); cameraBtn.dataset.running='1'; cameraBtn.innerText='Stop Camera';
    }
  });

  window.addEventListener('barcodeDetected', async (e)=>{
    const code = (e.detail && e.detail.code) || e.detail;
    if(!code) return;
    console.log('Detected code event', code);
    await handleDetected(code, currentMode);
  });

  async function handleDetected(code, mode){
    // lookup
    try{
      const lookup = await fetch('/api/lookup/?barcode=' + encodeURIComponent(code));
      if(lookup.ok){
        const j = await lookup.json();
        if(j && j.success && j.product){
          await recordScan(code, mode);
          addHistoryItem(code, j.product.product_name || j.product_name || code);
          updateResultPanel(j.product);
          return;
        }
      }
    }catch(err){ console.warn('lookup failed', err); }
    // not found
    showNotFound(code);
    addHistoryItem(code, 'Not Found');
  }

  async function recordScan(code, mode){
    try{
      const resp = await fetch('/api/scan/', {method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken': window.csrftoken}, body: JSON.stringify({barcode: code, mode: mode, qty:1})});
      const j = await resp.json().catch(()=>null);
      if(resp.ok && j && j.success){
        console.log('Inventory updated', j);
        // dispatch global event
        window.dispatchEvent(new CustomEvent('inventoryUpdated',{detail:{barcode:code,id:j.id,quantity:j.quantity,stats:j.stats}}));
      } else {
        console.warn('scan record failed', j);
      }
    }catch(err){ console.error('recordScan error', err); }
  }

  function addHistoryItem(code, label){
    const el = document.createElement('div'); el.className='history-item'; el.innerText = `${new Date().toLocaleTimeString()} — ${label} (${code})`; historyList.prepend(el);
  }

  function updateResultPanel(prod){
    try{
      document.getElementById('scanResult').style.display='block';
      document.getElementById('resName').innerText = prod.product_name || prod.productName || '';
      document.getElementById('resBarcode').innerText = prod.barcode || '';
      document.getElementById('resCategory').innerText = prod.category || '';
      document.getElementById('resQty').innerText = prod.quantity || 0;
      document.getElementById('resExp').innerText = prod.expiry_date || '—';
    }catch(e){console.warn('updateResult error', e)}
  }

  function showNotFound(code){
    document.getElementById('scanResult').style.display='block';
    document.getElementById('resName').innerText = 'Product Not Found';
    document.getElementById('resBarcode').innerText = code;
    document.getElementById('resCategory').innerText = '—';
    document.getElementById('resQty').innerText = '—';
    document.getElementById('resExp').innerText = '—';
  }

  // manual scan via input
  document.getElementById('scanBtn').addEventListener('click', ()=>{ const v = scanInput.value.trim(); if(v) window.dispatchEvent(new CustomEvent('barcodeDetected',{detail:{code:v}})); });

});
