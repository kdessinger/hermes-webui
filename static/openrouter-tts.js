/* OpenRouter speech catalog. Server settings own the selected model and voice;
 * per-model voice history is a browser convenience, never a provider fallback. */
(function(){
  const defaultModel='heygen/heygen-voice-1-turbo';
  const modelKey='hermes-tts-openrouter-model',voiceKey='hermes-tts-openrouter-voice';
  let models=[],pending=null,loaded=false;
  const el=id=>document.getElementById(id);
  const model=()=>localStorage.getItem(modelKey)||defaultModel;
  function option(select,value,label){
    const opt=document.createElement('option');opt.value=value;opt.textContent=label;select.appendChild(opt);
  }
  function history(){try{return JSON.parse(localStorage.getItem('hermes-tts-openrouter-voices')||'{}');}catch(_){return {};}}
  function rememberVoice(value){
    stopPreview();
    const saved=history();saved[model()]=value;
    localStorage.setItem('hermes-tts-openrouter-voices',JSON.stringify(saved));
    localStorage.setItem(voiceKey,value);
    _markSpeechPreferenceChanged('tts_openrouter_voice');_schedulePreferencesAutosave();
  }
  let previewAudio=null,previewUrl=null,previewRequest=null,previewTimer=null;
  function stopPreview(){
    if(previewRequest)previewRequest.abort();
    previewRequest=null;
    clearTimeout(previewTimer);previewTimer=null;
    if(previewAudio){previewAudio.pause();previewAudio.removeAttribute('src');previewAudio.load();}
    previewAudio=null;
    if(previewUrl)URL.revokeObjectURL(previewUrl);
    previewUrl=null;
    const button=el('settingsOpenRouterPreview');
    button.disabled=false;button.textContent='▶ Preview';button.setAttribute('aria-label','Preview selected voice');
  }
  async function previewVoice(){
    const status=el('settingsOpenRouterPreviewStatus'),button=el('settingsOpenRouterPreview');
    if(previewAudio||previewRequest){stopPreview();status.textContent='Preview stopped.';return;}
    const selection=window._openRouterTtsSelection();
    // Read the visible field as well: a click can precede its change event.
    selection.voice=el('settingsOpenRouterVoice').hidden?el('settingsOpenRouterCustomVoice').value.trim():el('settingsOpenRouterVoice').value;
    const controller=new AbortController();previewRequest=controller;
    previewTimer=setTimeout(()=>controller.abort(),45000);
    button.textContent='■ Stop';button.setAttribute('aria-label','Stop voice preview');
    status.textContent='Generating a short sample…';
    try{
      const response=await fetch(new URL('api/tts',document.baseURI||location.href),{
        method:'POST',headers:{'Content-Type':'application/json'},signal:controller.signal,
        body:JSON.stringify({engine:'openrouter',model:selection.model,voice:selection.voice,text:'Hello Kenn. This is a preview of my voice. How do I sound?'})
      });
      if(!response.ok){
        const error=await response.json().catch(()=>({}));
        throw new Error(error.error||('Voice preview failed: '+response.status));
      }
      const blob=await response.blob();
      if(controller.signal.aborted||previewRequest!==controller)return;
      clearTimeout(previewTimer);previewTimer=null;
      previewRequest=null;previewUrl=URL.createObjectURL(blob);
      const audio=new Audio(previewUrl);previewAudio=audio;
      audio.onended=()=>{if(previewAudio===audio){stopPreview();status.textContent='Preview finished.';}};
      audio.onerror=()=>{if(previewAudio===audio){stopPreview();status.textContent='Unable to play the voice sample. Please try again.';}};
      await audio.play();status.textContent='Playing voice sample…';
    }catch(error){
      if(previewRequest!==controller&&previewAudio===null)return;
      stopPreview();status.textContent=error.name==='AbortError'?'Preview timed out. Please try again.':error.message;
    }
  }
  function renderVoices(){
    stopPreview();
    const select=el('settingsOpenRouterVoice'),custom=el('settingsOpenRouterCustomVoice');
    const metadata=models.find(row=>row.id===model());
    const voices=metadata?metadata.voices:[];
    const saved=localStorage.getItem(voiceKey)||'';
    select.replaceChildren();option(select,'','Provider default');
    voices.forEach(v=>option(select,v,v));
    // A removed voice remains visible rather than being silently overwritten.
    if(saved&&voices.length&&!voices.includes(saved)) option(select,saved,saved+' (not in current catalog)');
    select.value=saved;
    select.hidden=voices.length===0;
    custom.hidden=voices.length>0;el('settingsOpenRouterCustomLabel').hidden=voices.length>0;
    custom.value=saved;
    select.onchange=()=>rememberVoice(select.value);
    custom.onchange=()=>rememberVoice(custom.value.trim());
  }
  function render(){
    const select=el('settingsOpenRouterModel'),saved=model();
    select.replaceChildren();
    models.forEach(row=>option(select,row.id,row.name+' — '+row.id));
    if(!models.some(row=>row.id===saved)) option(select,saved,saved+' (not in current catalog)');
    select.value=saved;
    select.onchange=function(){
      const previous=model(),h=history();h[previous]=localStorage.getItem(voiceKey)||'';
      localStorage.setItem('hermes-tts-openrouter-voices',JSON.stringify(h));
      localStorage.setItem(modelKey,this.value);localStorage.setItem(voiceKey,h[this.value]||'');
      _markSpeechPreferenceChanged('tts_openrouter_model');_markSpeechPreferenceChanged('tts_openrouter_voice');
      renderVoices();_schedulePreferencesAutosave();
    };
    renderVoices();
  }
  async function load(refresh){
    if(pending)return pending;
    const status=el('settingsOpenRouterStatus'),button=el('settingsOpenRouterRefresh');
    button.disabled=true;status.textContent='Loading OpenRouter speech catalog…';
    pending=(async()=>{
      try{
        const response=await fetch(new URL('api/tts/openrouter/models'+(refresh?'?refresh=1':''),document.baseURI||location.href));
        if(!response.ok)throw new Error('Catalog request failed: '+response.status);
        const data=await response.json();
        if(!Array.isArray(data.models)||!data.models.length)throw new Error('Speech catalog is empty');
        models=data.models;loaded=true;render();
        status.textContent=models.length+' speech models'+(data.stale?' · offline/stale '+data.source:' · catalog loaded')+'.';
      }catch(e){status.textContent=e.message+'; your selection has been kept.';}
      finally{button.disabled=false;pending=null;}
    })();
    return pending;
  }
  window._setupOpenRouterTts=function(){
    const enabled=localStorage.getItem('hermes-tts-engine')==='openrouter';
    el('settingsOpenRouterField').hidden=!enabled;
    if(!enabled){stopPreview();return;}
    el('settingsOpenRouterPreview').onclick=previewVoice;
    // Existing generic HeyGen voice preference migrates only in this browser;
    // opening settings never creates an owned server preference.
    if(localStorage.getItem(voiceKey)===null&&model()===defaultModel){
      const legacy=localStorage.getItem('hermes-tts-voice')||'';
      if(['nadine','tabitha','bram','gareth','noelle','meredith','sabrina','lucian','weston','vincent'].includes(legacy)) localStorage.setItem(voiceKey,legacy);
    }
    el('settingsOpenRouterRefresh').onclick=()=>load(true);
    if(loaded)render();else load(false);
  };
  // Bind immediately when the deferred script loads, not only when the
  // preferences panel decides to repopulate its voice list.
  const previewButton=el('settingsOpenRouterPreview');
  if(previewButton)previewButton.onclick=previewVoice;
  window._openRouterTtsSelection=function(){
    let voice=localStorage.getItem(voiceKey);
    if(voice===null&&model()===defaultModel){
      const old=localStorage.getItem('hermes-tts-voice')||'';
      voice=['nadine','tabitha','bram','gareth','noelle','meredith','sabrina','lucian','weston','vincent'].includes(old)?old:'';
    }
    return {model:model(),voice:voice||''};
  };
})();
