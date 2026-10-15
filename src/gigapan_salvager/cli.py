import argparse
import hashlib
import json
import sys
import tarfile
from pathlib import Path
from .archive import Salvager, write, write_json, now
from .model import parse_id


def main(argv=None):
    p=argparse.ArgumentParser(description='Public GigaPan panorama preservation')
    p.add_argument('id',type=parse_id,help='GigaPan ID or URL')
    p.add_argument('--output',type=Path,default=Path('archives'))
    p.add_argument('--kml',type=Path)
    p.add_argument('--width',type=int);p.add_argument('--height',type=int)
    p.add_argument('--workers',type=int,default=6,choices=range(1,13))
    p.add_argument('--max-tiles',type=int,default=250000)
    p.add_argument('--max-bytes',type=int,default=8*1024**3)
    p.add_argument('--offline',action='store_true',help='Verify and package already-saved files without network access')
    p.add_argument('--probe',action='store_true',help='Metadata and one tile only; not a full archive')
    args=p.parse_args(argv)
    if bool(args.width)!=bool(args.height):p.error('--width and --height must be supplied together')
    job=Salvager(args.id,args.output,workers=args.workers,offline=args.offline,max_tiles=args.max_tiles,max_bytes=args.max_bytes)
    try:
        job.bootstrap(args.kml,args.width,args.height)
        job.extras()
        report=job.download(args.probe)
        archive=job.finalize()
        code=0 if report['status']=='complete' or (args.probe and report['verified_tiles']==1) else 2
    except Exception as exc:
        report={'id':args.id,'status':'unavailable','finished_at':now(),'error':str(exc),'warnings':job.warnings,'errors':job.errors}
        write_json(job.root/'audit.json',report)
        archive=job.root.with_suffix('.tar.gz')
        with tarfile.open(archive,'w:gz',dereference=False) as tar:tar.add(job.root,arcname=job.root.name)
        digest=hashlib.sha256()
        with archive.open('rb') as f:
            for chunk in iter(lambda:f.read(1024*1024),b''):digest.update(chunk)
        write(archive.with_name(archive.name+'.sha256'),digest.hexdigest()+'  '+archive.name+'\n')
        print(str(exc),file=sys.stderr);code=1
    write_json(args.output/'job-result.json',{'archive':str(archive),'exit_code':code,**report})
    print(json.dumps({'archive':str(archive),'status':report['status'],'exit_code':code},ensure_ascii=False),flush=True)
    return code


if __name__=='__main__':sys.exit(main())
