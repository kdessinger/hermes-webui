"""Exercise real app bundles against the real Configure lifecycle runtime."""
from pathlib import Path
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('slot,prefix', [('external-app-tab','hwx-extapp'), ('external-app-tab-2','hwx-extapp2')])
def test_configure_close_settles_and_can_reopen(slot, prefix):
    bundle = ROOT / 'site-customizations/external-apps/extensions' / slot / 'assets' / (slot + '.js')
    script = r'''
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const [runtime,bundle,slot,prefix]=process.argv.slice(1);
const elements=new Map();
class Element {
 constructor(){this.handlers={};this.children=new Map();this.dataset={};this.classList={add(){},remove(){}};this.style={};this.value='';}
 setAttribute(){} focus(){} addEventListener(type,fn){this.handlers[type]=fn;}
 querySelector(s){if(!this.children.has(s))this.children.set(s,new Element());return this.children.get(s);}
 appendChild(el){if(el.id)elements.set(el.id,el);}
 remove(){elements.delete(this.id);}
}
const rail=new Element();rail.querySelector=()=>null;
global.document={readyState:'complete',body:new Element(),createElement:()=>new Element(),getElementById:id=>elements.get(id)||null,querySelector:s=>s==='.rail'?rail:null,querySelectorAll:()=>[],addEventListener(){},removeEventListener(){}};
global.window=global;window.location={href:'https://example.test/',origin:'https://example.test'};
window.__HERMES_EXTENSION_CONFIG__={extensions:[{id:slot,name:slot,storage_owned:true,settings_schema:[],effective_enabled:true}]};
window.localStorage={getItem:()=>null,setItem(){},removeItem(){}};
global.fetch=async()=>({ok:true,json:async()=>({[slot]:{url:'/apps/nas-recovery/',label:'NAS Recovery'}})});
vm.runInThisContext(fs.readFileSync(runtime,'utf8'));
vm.runInThisContext(fs.readFileSync(bundle,'utf8'));
(async()=>{
 await new Promise(r=>setTimeout(r,0));
 const rt=window.HermesExtensionSettings;
 for(const action of ['cancel','backdrop','escape','save']){
  assert.equal(rt._invokeConfigure(slot,{}),true);
  assert.equal(rt._configureStateForExtension(slot).pending,true);
  const dlg=[...elements.values()].find(el=>el.id?.endsWith('Config'));
  assert.ok(dlg);
  if(action==='cancel')dlg.querySelector('.'+prefix+'-cancel').handlers.click();
  if(action==='backdrop')dlg.handlers.click({target:dlg});
  if(action==='escape')dlg.handlers.keydown({key:'Escape',preventDefault(){},stopPropagation(){}});
  if(action==='save')await dlg.querySelector('.'+prefix+'-save').handlers.click();
  assert.equal(rt._configureStateForExtension(slot).pending,false,action+' must settle Configure');
  assert.equal(elements.has(dlg.id),false,action+' removes dialog');
 }
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = subprocess.run(['node','-e',script,str(ROOT/'static/extension_settings.js'),str(bundle),slot,prefix],capture_output=True,text=True,timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr

@pytest.mark.parametrize('slot,prefix', [('external-app-tab','hwx-extapp'), ('external-app-tab-2','hwx-extapp2')])
def test_configure_dialog_is_above_core_dialog_layer(slot, prefix):
    import re
    css = (ROOT / 'site-customizations/external-apps/extensions' / slot / 'assets' / (slot+'.css')).read_text()
    block = re.search(r'\.'+prefix+r'-config-dlg\s*\{([^}]+)',css).group(1)
    assert int(re.search(r'z-index:\s*(\d+)',block).group(1)) > 1100
