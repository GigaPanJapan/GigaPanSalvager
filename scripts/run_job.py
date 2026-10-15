import json
import sys
from pathlib import Path
from gigapan_salvager.cli import main

request=json.loads(Path('work/request.json').read_text())
args=[str(request['id']),'--output','archives']
if request['mode']=='probe':args+=['--probe']
if request.get('kml'):
    Path('work/request.kml').write_text(request['kml'],encoding='utf-8');args+=['--kml','work/request.kml']
for key in ('width','height'):
    if request.get(key):args+=['--'+key,str(request[key])]
sys.exit(main(args))
