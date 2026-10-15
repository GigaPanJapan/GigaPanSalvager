"""Validate event data before passing it to the downloader. Never evaluate event text."""
import json
import os
import re
from pathlib import Path
import requests
from gigapan_salvager.model import parse_id, kml_metadata, Geometry


def parse_request(event,event_name,repo,check_permission=None):
    if event_name=='issues':
        issue=event['issue'];login=issue['user']['login']
        if not issue['title'].startswith('[Salvage] GigaPan '):raise ValueError('Not a salvage request')
        if login!=repo.split('/')[0] and not (check_permission and check_permission(login)):
            raise ValueError('救出を実行できるのはリポジトリ所有者・書き込み権限のある共同編集者です。')
        body=issue.get('body') or ''
        if len(body)>100_000 or '<!-- gigapan-salvager:v1 -->' not in body:raise ValueError('Invalid request marker or size')
        match=re.search(r'```json\s*\n([\s\S]+?)\n```',body)
        if not match:raise ValueError('Request JSON not found')
        value=json.loads(match[1])
    else:
        i=event.get('inputs',{})
        value={'id':i.get('gigapan_id'),'mode':i.get('mode','full')}
        for key in ('width','height'):
            if i.get(key):value[key]=int(i[key])
    if not isinstance(value,dict) or set(value)-{'id','mode','kml','width','height'}:raise ValueError('Unsupported request fields')
    gid=parse_id(value.get('id',''))
    if value.get('mode','full') not in ('full','probe'):raise ValueError('Invalid mode')
    value.update(id=gid,mode=value.get('mode','full'))
    if value.get('kml'):
        if not isinstance(value['kml'],str):raise ValueError('KML must be text')
        Geometry.from_metadata(kml_metadata(value['kml'].encode('utf-8'),gid))
    if value.get('width') or value.get('height'):
        Geometry.from_metadata({'width':value.get('width'),'height':value.get('height')})
    return value


def main():
    event=json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text());repo=os.environ['GITHUB_REPOSITORY']
    def permitted(login):
        response=requests.get(f'https://api.github.com/repos/{repo}/collaborators/{login}/permission',headers={'Authorization':'Bearer '+os.environ['GITHUB_TOKEN'],'Accept':'application/vnd.github+json'},timeout=20)
        response.raise_for_status()
        return response.json().get('permission') in ('admin','write','maintain')
    request=parse_request(event,os.environ['GITHUB_EVENT_NAME'],repo,permitted)
    Path('work').mkdir(exist_ok=True);Path('work/request.json').write_text(json.dumps(request))
    with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write(f'id={request["id"]}\nmode={request["mode"]}\n')


if __name__=='__main__':main()
