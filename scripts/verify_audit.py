"""Verify hash links in a session export. This does not prove external authenticity."""
import hashlib,json,sys
s=json.load(open(sys.argv[1]));previous='0'*64
for event in s['log']:
 body={k:v for k,v in event.items() if k not in ('previous','hash')}
 digest=hashlib.sha256((previous+json.dumps(body,sort_keys=True,separators=(',',':'))).encode()).hexdigest()
 if event['previous']!=previous or event['hash']!=digest: raise SystemExit('Audit chain mismatch')
 previous=digest
print(f'Validated {len(s["log"])} linked events. Final hash: {previous}')
