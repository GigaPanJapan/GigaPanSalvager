import test from 'node:test';
import assert from 'node:assert/strict';
import {parseId,issueUrl,statusLabel} from '../web/core.mjs';
test('ID or public panorama URL',()=>{assert.equal(parseId(' 76564 '),76564);assert.equal(parseId('https://gigapan.com/gigapans/76564'),76564);for(const bad of ['0','42;echo bad','https://evil.test/gigapans/42'])assert.throws(()=>parseId(bad));});
test('issue request roundtrip without shell interpolation',()=>{const u=new URL(issueUrl('owner/repo',{id:42,mode:'full',width:513,height:257}));assert.equal(u.origin,'https://github.com');const body=u.searchParams.get('body');assert.match(body,/gigapan-salvager:v1/);assert.deepEqual(JSON.parse(body.match(/```json\n([\s\S]+?)\n```/)[1]),{id:42,mode:'full',width:513,height:257});});
test('failed run is visibly incomplete',()=>{assert.equal(statusLabel({status:'completed',conclusion:'failure'}),'未完了・ログを確認');});
