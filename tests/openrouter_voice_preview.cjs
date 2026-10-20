const fs=require('fs'),vm=require('vm'),assert=require('assert');
const root=require('path').resolve(__dirname,'..');
async function main(){
 const elements={};function element(id){return elements[id]||(elements[id]={hidden:false,textContent:'',disabled:false,value:'',options:[],appendChild(o){this.options.push(o)},replaceChildren(){this.options=[]},setAttribute(k,v){this[k]=v}})}
 let calls=[],plays=0,pauses=0,revoked=0,fail=false;
 const storage=new Map([['hermes-tts-engine','openrouter'],['hermes-tts-openrouter-model','google/test'],['hermes-tts-openrouter-voice','Kore']]);
 const context={document:{getElementById:element,createElement:()=>({}),baseURI:'http://localhost/nested/'},location:{href:'http://localhost/'},localStorage:{getItem:k=>storage.has(k)?storage.get(k):null,setItem:(k,v)=>storage.set(k,v)},URL,AbortController,setTimeout,clearTimeout,window:{},_markSpeechPreferenceChanged(){},_schedulePreferencesAutosave(){},fetch:async(url,opts)=>{if(!opts)return {ok:true,json:async()=>({models:[{id:'google/test',name:'Test',voices:['Kore']}],stale:false})};calls.push(JSON.parse(opts.body));return {ok:!fail,status:502,json:async()=>({error:'No provider available'}),blob:async()=>({type:'audio/mpeg'})}},Audio:function(){this.play=async()=>{plays++};this.pause=()=>pauses++;this.removeAttribute=()=>{};this.load=()=>{};}};
 context.URL=class extends URL{static createObjectURL(){return 'blob:test'}static revokeObjectURL(){revoked++}};
 vm.createContext(context);vm.runInContext(fs.readFileSync(root+'/static/openrouter-tts.js','utf8'),context);
 context.window._setupOpenRouterTts();await new Promise(r=>setTimeout(r,0));
 const button=element('settingsOpenRouterPreview');assert.equal(typeof button.onclick,'function','preview button must be wired');
 const before=JSON.stringify([...storage]);await button.onclick();assert.equal(plays,1);assert.equal(calls[0].model,'google/test');assert.equal(calls[0].voice,'Kore');assert.equal(calls[0].engine,'openrouter');assert.equal(before,JSON.stringify([...storage]),'preview must not change preferences');
 await button.onclick();assert.equal(pauses,1);assert.equal(revoked,1);assert.equal(calls.length,1,'stop must not generate speech');
 fail=true;await button.onclick();assert(element('settingsOpenRouterPreviewStatus').textContent.includes('No provider'));assert.equal(button.disabled,false);
 console.log('PASS: selected voice request, playback, stop, URL cleanup, error feedback, unchanged settings');
}
main().catch(e=>{console.error(e);process.exit(1)});
