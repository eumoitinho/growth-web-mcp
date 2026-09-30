"""Local reference application with deterministic failure injection. No external API calls."""
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread
from urllib.parse import urlparse

PAGE = '''<!doctype html><html><body>
<button data-qa="consent-accept" onclick="consent=true">Accept</button>
<button data-qa="consent-deny" onclick="consent=false">Deny</button>
<a data-qa="direct-return">Return direct</a><a data-qa="subdomain-form">Subdomain</a>
<form><input name="email" type="email" required><button type="submit">Submit</button></form>
<div data-qa="success" hidden>Success</div><div data-qa="error" hidden>Error</div>
<script>
window.dataLayer=window.dataLayer||[];
let consent=false, sent=false;
const q=new URLSearchParams(location.search);
const remembered=JSON.parse(sessionStorage.getItem('attribution')||'{}');
for(const key of ['utm_source','utm_medium','utm_campaign']) if(q.has(key)) remembered[key]=q.get(key);
sessionStorage.setItem('attribution',JSON.stringify(remembered));
const direct=new URL(location.href);direct.pathname='/return';
for(const key of ['utm_source','utm_medium','utm_campaign','gclid']) direct.searchParams.delete(key);
document.querySelector('[data-qa="direct-return"]').href=direct.href;
const cross=new URL(location.href);cross.hostname='localhost';
document.querySelector('[data-qa="subdomain-form"]').href=cross.href;
if(location.pathname==='/return' || location.hostname==='localhost') consent=true;

document.querySelector('form').onsubmit=async e=>{
 e.preventDefault();
 const fields={test_run_id:q.get('test_run_id'),submission_id:'sub-'+q.get('test_run_id'),
  utm_source:remembered.utm_source||'google',utm_medium:remembered.utm_medium||'organic',first_touch_source:remembered.utm_source||'google',
  utm_campaign:remembered.utm_campaign||'',lifecyclestage:'lead'};
 if(sent && q.get('fault')!=='duplicate') return;
 const response=await fetch('/submit',{method:'POST',body:JSON.stringify({fields,email:document.querySelector('[name="email"]').value,scenario:q.get('scenario'),fault:q.get('fault'),consent})});
 if(!response.ok){document.querySelector('[data-qa="error"]').hidden=false;return;}
 sent=true;
 if(consent){
  dataLayer.push({event:'generate_lead',...fields});
  const payload=new URLSearchParams({en:'generate_lead'});
  for(const [key,value] of Object.entries(fields)) payload.set('ep.'+key,value);
  await fetch('/g/collect',{method:'POST',body:payload.toString()});
 }
 document.querySelector('[data-qa="success"]').hidden=false;
};
</script></body></html>'''


class Fixture:
    def __enter__(self):
        self.rows = []
        self.contacts = {"existing@example.invalid":"existing-contact-id"}
        contacts = self.contacts
        rows = self.rows
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Type','text/html')
                self.end_headers()
                self.wfile.write(PAGE.encode())
            def do_POST(self):
                data = self.rfile.read(int(self.headers.get('Content-Length','0')))
                if urlparse(self.path).path == '/submit':
                    payload = json.loads(data)
                    if payload.get('scenario') == 'form-error':
                        self.send_response(422); self.end_headers(); return
                    fields = payload['fields']
                    contact_id = contacts.setdefault(payload['email'], f'contact-{len(contacts)}')
                    if payload.get('fault') == 'campaign-loss': fields.pop('utm_campaign',None)
                    for source,event in [('hubspot','submission'),('hubspot','contact')] + ([('ga4','generate_lead')] if payload['consent'] else []):
                        rows.append({'run_id':fields['test_run_id'],'source':source,'event':event,'record_id':contact_id if event=='contact' else f'{event}-{len(rows)}','occurred_at':datetime.now(timezone.utc).isoformat(),'fields':dict(fields)})
                self.send_response(204); self.end_headers()
        self.http = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread = Thread(target=self.http.serve_forever,daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.http.server_port}'
        return self
    def __exit__(self,*args):
        self.http.shutdown();self.http.server_close();self.thread.join()
