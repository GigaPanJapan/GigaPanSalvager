import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from PIL import Image
from gigapan_salvager.archive import Salvager, inspect_jpeg
from gigapan_salvager.model import Geometry, tile_path, parse_id, kml_metadata, offline_kml, safe_xml
from gigapan_salvager.network import allowed_url
from scripts.prepare_request import parse_request

KML='''<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><PhotoOverlay id="gigapan_42"><name>日本語 &amp; 海</name><description><![CDATA[<p>原本の説明</p>]]></description><Icon><href>http://gigapan.com/get_ge_tile/42/$[level]/$[y]/$[x]</href></Icon><ImagePyramid><tileSize>256</tileSize><maxWidth>513</maxWidth><maxHeight>257</maxHeight></ImagePyramid></PhotoOverlay></Document></kml>'''.encode()

def jpeg(color='blue'):
    f=io.BytesIO();Image.new('RGB',(256,256),color).save(f,'JPEG');return f.getvalue()

class FakeClient:
    def __init__(self):self.calls=[];self.failed=set();self.unavailable=False
    def get(self,url,**kwargs):
        self.calls.append(url);u=urlparse(url);path=u.path
        if self.unavailable or any(path.endswith(x) for x in self.failed):raise RuntimeError('simulated outage')
        if path.endswith('/42.json'):data=json.dumps({'gigapan':{'id':42,'name':'日本語','width':513,'height':257,'levels':3}}).encode()
        elif path.endswith('.kml'):data=KML
        elif '/tiles/' in path or path.endswith('.jpg'):data=jpeg()
        elif path.endswith('snapshots.json'):
            p=int(parse_qs(u.query)['page'][0]);data=json.dumps([{'snapshot':{'id':100+p,'gigapan_id':42}}] if p<=2 else []).encode()
        elif path=='/gigapans/42':data=b'<html>var gigapan = {"tile_server_path":"http://tile00.gigapan.com/gigapans0/42/tiles/"};\n</html>'
        else:raise RuntimeError('not found')
        return data,{'url':url}

class ModelTests(unittest.TestCase):
    def test_geometry_and_paths(self):
        g=Geometry.from_metadata({'width':39488,'height':14732,'levels':9})
        self.assertEqual(g.count,12053)
        self.assertEqual(g.grid(8),(155,58))
        self.assertEqual(tile_path(8,0,0),'r00/000/r00000000.jpg')
        self.assertEqual(tile_path(1,1,1),'r3.jpg')
        self.assertEqual(tile_path(6,63,63),'r33/333/r333333.jpg')
        self.assertEqual(Geometry.from_metadata({'width':513,'height':257}).count,9)
        with self.assertRaises(ValueError):Geometry.from_metadata({'width':513,'height':257,'levels':2})
    def test_id_and_hosts(self):
        self.assertEqual(parse_id('https://gigapan.com/gigapans/76564'),76564)
        for bad in ('0','-1','76564; echo no','https://evil.com/gigapans/42'):
            with self.assertRaises(ValueError):parse_id(bad)
        for bad in ('https://gigapan.com.evil.test/x','https://user@gigapan.com/x','http://localhost/x','file:///x'):
            self.assertFalse(allowed_url(bad))
    def test_kml_preserves_bytes(self):
        m=kml_metadata(KML,42);out=offline_kml(KML,m)
        expected=KML.replace(b'http://gigapan.com/get_ge_tile/42/$[level]/$[y]/$[x]',b'ge_tiles/$[level]/$[y]/$[x].jpg')
        self.assertEqual(out,expected);self.assertIn('原本の説明'.encode(),out)
        with self.assertRaises(ValueError):kml_metadata(KML,43)
        with self.assertRaises(ValueError):safe_xml(b'<!DOCTYPE x><x/>')
    def test_truncated_jpeg(self):
        with self.assertRaises(ValueError):inspect_jpeg(jpeg()[:-20])
    def test_permission_and_injection(self):
        body='<!-- gigapan-salvager:v1 -->\n```json\n{"id":42,"mode":"full"}\n```'
        event={'issue':{'title':'[Salvage] GigaPan 42','body':body,'user':{'login':'owner'}}}
        self.assertEqual(parse_request(event,'issues','owner/repo')['id'],42)
        event['issue']['user']['login']='stranger'
        with self.assertRaises(ValueError):parse_request(event,'issues','owner/repo',lambda _:False)
        with self.assertRaises(ValueError):parse_request({'inputs':{'gigapan_id':'42; rm -rf x'}},'workflow_dispatch','owner/repo')

class PipelineTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.client=FakeClient()
    def tearDown(self):self.tmp.cleanup()
    def run_job(self,offline=False):
        j=Salvager(42,self.tmp.name,client=self.client,offline=offline,workers=2)
        j.bootstrap();j.extras();j.download();j.finalize();return j
    def test_complete_archive_and_offline_resume(self):
        j=self.run_job();self.assertEqual(j.report['status'],'complete');self.assertEqual(j.report['verified_tiles'],9)
        self.assertEqual(j.report['snapshot_count'],2)
        self.assertTrue((j.root/'preview.jpg').exists())
        with tarfile.open(j.root.with_suffix('.tar.gz')) as t:
            names=t.getnames();self.assertIn('gigapan_42/gigapan_42_offline.kml',names)
            self.assertEqual(sum('/tiles/' in n and n.endswith('.jpg') for n in names),9)
        self.client.calls.clear();j=self.run_job(True)
        self.assertEqual(j.report['status'],'complete');self.assertEqual(self.client.calls,[])
        self.assertEqual(len(json.loads((j.meta/'retrieval_log.json').read_text())['history']),2)
    def test_partial_then_repair(self):
        self.client.failed.add('r03.jpg');j=self.run_job()
        self.assertEqual(j.report['status'],'partial');self.assertEqual(j.report['missing_tiles'],1)
        self.client.failed.clear();j=self.run_job();self.assertEqual(j.report['status'],'complete')
        self.assertEqual(sum(r['status']=='downloaded' for r in j.rows),1)
    def test_checksum_detects_valid_but_changed_tile(self):
        j=self.run_job();(j.root/'tiles/r0.jpg').write_bytes(jpeg('red'))
        j=self.run_job(True);self.assertEqual(j.report['status'],'partial')
        self.assertFalse((j.root/'tiles/r0.jpg').exists());self.assertFalse((j.root/'ge_tiles/1/0/0.jpg').exists())
    def test_outage_does_not_request_every_tile(self):
        j=self.run_job();self.client.calls.clear();self.client.unavailable=True
        j=self.run_job();self.assertEqual(j.report['status'],'complete')
        tile_calls=[x for x in self.client.calls if '/tiles/' in x]
        self.assertEqual(len(tile_calls),4)
    def test_probe_never_claims_complete(self):
        j=Salvager(42,self.tmp.name,client=self.client);j.bootstrap();j.download(probe=True)
        self.assertEqual(j.report['status'],'probe');self.assertEqual(j.report['verified_tiles'],1)

if __name__=='__main__':unittest.main()
