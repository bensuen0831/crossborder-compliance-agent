import hashlib,json,pathlib,re
from html.parser import HTMLParser
R=pathlib.Path('/workspace/kb01-security-final-733a748')
class Tables(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.tables=[];self.table=None;self.row=None;self.cell=None
 def handle_starttag(self,t,a):
  if t=='table':self.table=[]
  elif self.table is not None and t=='tr':self.row=[]
  elif self.row is not None and t in ('td','th'):self.cell={'text':'','rowspan':int(dict(a).get('rowspan','1')),'colspan':int(dict(a).get('colspan','1'))}
 def handle_data(self,d):
  if self.cell is not None:self.cell['text']+=d+' '
 def handle_endtag(self,t):
  if t in ('td','th') and self.cell is not None:self.cell['text']=' '.join(self.cell['text'].split());self.row.append(self.cell);self.cell=None
  elif t=='tr' and self.row is not None:self.table.append(self.row);self.row=None
  elif t=='table' and self.table is not None:self.tables.append(self.table);self.table=None

def expand(rows):
 out=[];carry={}
 for row in rows:
  values=[];col=0;new={}
  for cell in row:
   while col in carry:
    v,n=carry[col];values.append(v)
    if n>1:new[col]=(v,n-1)
    col+=1
   for _ in range(cell['colspan']):
    values.append(cell['text'])
    if cell['rowspan']>1:new[col]=(cell['text'],cell['rowspan']-1)
    col+=1
  while col in carry:
   v,n=carry[col];values.append(v)
   if n>1:new[col]=(v,n-1)
   col+=1
  out.append(values);carry=new
 return out
out={}
for f in sorted((R/'advisories').glob('*.html')):
 p=Tables();p.feed(f.read_text());tables=[expand(t) for t in p.tables];out[f.stem]={'url':'https://security-tracker.debian.org/tracker/'+f.stem,'raw_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'tables':tables,'release_rows':[]}
 for table in tables:
  if table and table[0][:4]==['Source Package','Release','Version','Status']:
   out[f.stem]['release_rows']=[dict(zip(['source_package','release','version','status'],row[:4])) for row in table[1:] if len(row)>=4]
for entry in out.values():
 last=None
 for row in entry['release_rows']:
  if row['source_package']:last=row['source_package']
  elif last:row['source_package']=last
(R/'official-advisory-data.json').write_text(json.dumps(out,indent=2)+'\n');print('Parsed',len(out),'officialCVEpages;',sum(bool(v['release_rows']) for v in out.values()),'have release status tables');print(json.dumps(out['CVE-2026-6653']['release_rows'],indent=2))
