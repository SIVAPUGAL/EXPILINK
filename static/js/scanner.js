// scanner.js — thin wrapper around html5-qrcode to initialize camera and report detections
console.log('Scanner script loaded');

class ExpiScanner {
  constructor(targetElementId){
    this.target = document.getElementById(targetElementId);
    this.html5Qrcode = null;
    this.lastCode = null;
  }

  async startCamera(preferBack=true){
    if(!window.Html5Qrcode){ console.error('html5-qrcode not loaded'); return; }
    if(this.html5Qrcode) return;
    this.html5Qrcode = new Html5Qrcode(this.target.id, {formatsToSupport: [ Html5Qrcode.ScanType.SCAN_TYPE_FILE ]});
    const config = {fps:10, qrbox: {width: 250, height: 120}};
    try{
      console.log('Starting camera');
      await this.html5Qrcode.start({ facingMode: (preferBack? { exact: 'environment' } : 'user') }, config, (decodedText, decodedResult)=>{
        if(decodedText && decodedText !== this.lastCode){
          this.lastCode = decodedText;
          const ev = new CustomEvent('barcodeDetected',{detail:{code:decodedText}});
          window.dispatchEvent(ev);
          console.log('Barcode detected', decodedText);
        }
      });
      console.log('Camera started');
    }catch(err){ console.error('camera start error', err); }
  }

  async stopCamera(){
    if(!this.html5Qrcode) return;
    try{ await this.html5Qrcode.stop(); await this.html5Qrcode.clear(); this.html5Qrcode=null; console.log('Camera stopped'); }catch(e){console.warn('stop camera error', e)}
  }
}

window.ExpiScanner = ExpiScanner;
