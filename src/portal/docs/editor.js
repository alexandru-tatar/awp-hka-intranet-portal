/* AWP Docs · Versionsverlauf (alle Lesenden) und Editor (Rollen aus docs.edit_roles).
   Läuft nach dem Hauptskript der Hülle und nutzt window.AWPDocs. Kein Framework, keine Fremdskripte. */
(function(){
  'use strict';
  var A=window.AWPDocs;if(!A)return;
  var D=document,B=A.boot||{},esc=A.esc;
  var T={
    editing:'Bearbeitungsmodus',saved:'Alle Änderungen veröffentlicht',dirty:'Nicht veröffentlichte Änderungen',
    draft:'Entwurf im Browser gespeichert',publish:'Veröffentlichen',publishing:'Wird veröffentlicht …',cancel:'Abbrechen',
    del:'Löschen …',group:'Bereich',level:'Stufe',note:'Was haben Sie geändert? (optional)',notePh:'z. B. Abschnitt Docker ergänzt',
    none:'—',beginner:'Einsteiger',advanced:'Fortgeschritten',noTitle:'Die Seite braucht eine Überschrift (Titel) ganz oben.',
    leave:'Sie haben Änderungen, die noch nicht veröffentlicht sind. Der Entwurf bleibt im Browser gespeichert.',
    published:'Veröffentlicht: {t}, Version {v}',created:'Seite „{t}“ angelegt',deleted:'Seite „{t}“ gelöscht',
    restored:'Version {n} wiederhergestellt (jetzt Version {v})',network:'Keine Verbindung zum Portal. Ihr Entwurf ist im Browser gespeichert.',
    uploading:'Wird hochgeladen … {n} %',uploadFail:'Hochladen fehlgeschlagen',tooBig:'Die Datei ist größer als {mb} MB.',
    badType:'Dieses Format ist nicht erlaubt. Möglich sind PNG, JPEG, GIF, WebP und PDF.',
    draftFound:'Es gibt einen nicht veröffentlichten Entwurf dieser Seite vom {d}.',useDraft:'Entwurf übernehmen',dropDraft:'Verwerfen',
    dropHere:'Bild hier ablegen',history:'Versionsverlauf',close:'Schließen',current:'aktuell',view:'Ansehen',restore:'Wiederherstellen',
    viewing:'Sie sehen Version {n} vom {d} von {a}.',backCurrent:'Zur aktuellen Version',
    a_create:'angelegt',a_update:'aktualisiert',a_restore:'wiederhergestellt',
    newPage:'Neue Seite',newTitle:'Neue Seite anlegen',newBody:'Die Seite erscheint in der Navigation im gewählten Bereich und öffnet sich gleich im Editor.',
    title:'Titel',create:'Anlegen',
    delTitle:'Seite löschen?',delBody:'„{t}“ verschwindet aus der Navigation. Der Versionsverlauf bleibt erhalten; Administratoren können die Seite wiederherstellen.',delBtn:'Löschen',
    restTitle:'Version {n} wiederherstellen?',restBody:'Der Inhalt von Version {n} wird als neue Version veröffentlicht. Die aktuelle Fassung bleibt im Verlauf.',
    confTitle:'Seite wurde inzwischen geändert',confBody:'{a} hat eine neuere Version (Version {v}) veröffentlicht, während Sie bearbeitet haben. Wenn Sie trotzdem veröffentlichen, ersetzt Ihre Fassung diese Änderungen; sie bleiben im Verlauf.',confBtn:'Trotzdem veröffentlichen',
    linkTitle:'Link einfügen',linkText:'Angezeigter Text',linkUrl:'Adresse',linkHint:'Seite der Docs (#kurzname) oder https://…',linkNew:'In neuem Tab öffnen',insert:'Einfügen',
    tblTitle:'Tabelle einfügen',rows:'Zeilen',cols:'Spalten',header:'Erste Zeile ist Kopfzeile',
    imgTitle:'Bild beschreiben',alt:'Alternativtext',altHint:'Was zeigt das Bild? Für Screenreader und falls das Bild nicht lädt.',caption:'Bildunterschrift (optional)',save:'Übernehmen',
    discardTitle:'Änderungen verwerfen?',discardBody:'Nicht veröffentlichte Änderungen gehen verloren, auch der Entwurf im Browser.',discard:'Verwerfen',
    colLabel:'Spalte',calloutTitle:{info:'Hinweis',tip:'Tipp',warn:'Achtung',wip:'In Arbeit'}
  };
  function f(s,o){return String(s).replace(/\{(\w+)\}/g,function(_,k){return o&&o[k]!==undefined?o[k]:''})}
  function el(tag,cls,html){var e=D.createElement(tag);if(cls)e.className=cls;if(html!==undefined)e.innerHTML=html;return e}

  // Icons (gleicher Strich wie das Sprite)
  var P={
    bold:'<path d="M7 4h6a4 4 0 0 1 0 8H7zM7 12h7a4 4 0 0 1 0 8H7z"/>',italic:'<path d="M14 4h-4M14 20h-4M14 4l-4 16"/>',
    under:'<path d="M7 4v7a5 5 0 0 0 10 0V4M5 21h14"/>',strike:'<path d="M4 12h16M16 6.5A4 3 0 0 0 12 5c-2.5 0-4 1.3-4 3 0 4 8 2.5 8 7 0 1.7-1.7 3-4 3a5 4 0 0 1-4.5-2"/>',
    code:'<path d="M8 7l-5 5 5 5M16 7l5 5-5 5"/>',link:'<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    ul:'<path d="M9 6h11M9 12h11M9 18h11"/><rect x="4" y="5" width="2" height="2"/><rect x="4" y="11" width="2" height="2"/><rect x="4" y="17" width="2" height="2"/>',
    ol:'<path d="M10 6h10M10 12h10M10 18h10M4 4h2v4M4 8h3M4 14h3l-3 4h3"/>',quote:'<path d="M5 18V12h4v6zM5 12c0-4 2-6 4-6M14 18V12h4v6zM14 12c0-4 2-6 4-6"/>',
    callout:'<rect x="3" y="4" width="18" height="16"/><path d="M3 4v16" style="stroke-width:3"/><path d="M8 10h8M8 14h5"/>',
    block:'<rect x="3" y="4" width="18" height="16"/><path d="M7 9l3 3-3 3M12 15h5"/>',table:'<rect x="3" y="4" width="18" height="16"/><path d="M3 10h18M3 15h18M10 4v16"/>',
    image:'<rect x="3" y="4" width="18" height="16"/><circle cx="8.5" cy="9.5" r="1.5"/><path d="M21 16l-5-5-9 9"/>',file:'<path d="M14 3H6v18h12V7z"/><path d="M14 3v4h4M9 13h6M9 17h6"/>',
    hr:'<path d="M3 12h18"/>',undo:'<path d="M9 14L4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/>',redo:'<path d="M15 14l5-5-5-5"/><path d="M20 9H10a6 6 0 0 0 0 12h3"/>',
    clear:'<path d="M6 4h12M12 4l-3 16M4 20l16-16" style="stroke-width:1.6"/>',source:'<path d="M8 7l-5 5 5 5M16 7l5 5-5 5M14 4l-4 16"/>',
    rowAdd:'<rect x="3" y="4" width="18" height="10"/><path d="M3 9h18M12 16v5M9.5 18.5h5"/>',colAdd:'<rect x="3" y="3" width="10" height="18"/><path d="M8 3v18M16 12h5M18.5 9.5v5"/>',
    rowDel:'<rect x="3" y="4" width="18" height="10"/><path d="M3 9h18M9.5 18.5h5"/>',colDel:'<rect x="3" y="3" width="10" height="18"/><path d="M8 3v18M16 12h5"/>',
    trash:'<path d="M4 7h16M10 7V4h4v3M6 7l1 14h10l1-14M10 11v6M14 11v6"/>',sizeS:'<rect x="8" y="8" width="8" height="8"/>',sizeM:'<rect x="5" y="6" width="14" height="12"/>',
    sizeL:'<rect x="2" y="5" width="20" height="14"/>',center:'<path d="M4 6h16M7 10h10M4 14h16M7 18h10"/>',alt:'<path d="M4 6h16M4 12h10M4 18h7"/><path d="M16 15l2 2 4-4"/>',
    x:'<path d="M6 6l12 12M18 6L6 18"/>',edit:'<path d="M15 4l5 5L9 20H4v-5z"/>',history:'<path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/><path d="M12 7v5l3.5 2"/>'
  };
  function ic(n){return '<svg class="i" viewBox="0 0 24 24" aria-hidden="true" focusable="false">'+P[n]+'</svg>'}

  // Schnittstelle
  function api(method,path,body){
    var o={method:method,headers:{'X-CSRF-Token':B.csrf||'','Accept':'application/json'},credentials:'same-origin'};
    if(body!==undefined){o.headers['Content-Type']='application/json';o.body=JSON.stringify(body)}
    return fetch(B.api+path,o).then(function(r){return r.text().then(function(t){var d={};try{d=t?JSON.parse(t):{}}catch(e){}return {ok:r.ok,status:r.status,data:d}})},
      function(){return {ok:false,status:0,data:{message:T.network}}})}

  // Meldung
  var toastEl=el('div','ed-toast'),toastT;toastEl.setAttribute('role','status');D.body.appendChild(toastEl);
  function toast(msg,err){clearTimeout(toastT);toastEl.className='ed-toast'+(err?' err':'');toastEl.innerHTML='<span>'+esc(msg)+'</span><button type="button" aria-label="'+T.close+'">×</button>';
    toastEl.querySelector('button').onclick=function(){toastEl.classList.remove('on')};requestAnimationFrame(function(){toastEl.classList.add('on')});
    toastT=setTimeout(function(){toastEl.classList.remove('on')},err?9000:4500)}
  function reload(){try{history.scrollRestoration='manual'}catch(e){}scrollTo(0,0);location.reload()}
  function flash(msg){try{sessionStorage.setItem('awp-docs-flash',msg)}catch(e){}}
  try{var fm=sessionStorage.getItem('awp-docs-flash');if(fm){sessionStorage.removeItem('awp-docs-flash');setTimeout(function(){toast(fm)},300)}}catch(e){}

  // Dialog mit genau zwei Buttons; liefert die Werte der Felder oder null
  function dialog(o){return new Promise(function(res){
    var d=el('dialog','ed-dlg');d.setAttribute('aria-labelledby','edDlgT');
    d.innerHTML='<form method="dialog"><h2 id="edDlgT">'+esc(o.title)+'</h2>'+(o.body?'<p>'+esc(o.body)+'</p>':'')+(o.fields||'')+
      '<p class="err" hidden></p><div class="dialog__actions"><button value="cancel" class="btn btn--secondary" formnovalidate>'+esc(o.cancel||T.cancel)+'</button>'+
      '<button value="confirm" class="btn btn--primary'+(o.danger?' btn--danger':'')+'">'+esc(o.confirm)+'</button></div></form>';
    D.body.appendChild(d);var fm=d.querySelector('form'),err=d.querySelector('.err');
    fm.addEventListener('submit',function(e){if(e.submitter&&e.submitter.value==='cancel')return;var v={};new FormData(fm).forEach(function(x,k){v[k]=x});
      fm.querySelectorAll('input[type=checkbox]').forEach(function(c){v[c.name]=c.checked});
      var bad=o.validate&&o.validate(v);if(bad){e.preventDefault();err.textContent=bad;err.hidden=false;return}d._v=v});
    d.addEventListener('close',function(){var v=d.returnValue==='confirm'?d._v||{}:null;d.remove();res(v)});
    d.showModal();var first=d.querySelector('input,select,textarea');if(first){first.focus();if(first.select)first.select()}})}

  /* ─────────────── Versionsverlauf (alle Lesenden) ─────────────── */
  var vh=el('div','vh');vh.innerHTML='<div class="vh-scrim"></div><aside class="vh-panel" role="dialog" aria-modal="true" aria-labelledby="vhT"><div class="vh-head"><div><h2 id="vhT">'+T.history+'</h2><p id="vhSub"></p></div><button type="button" class="dx-icon" id="vhX" aria-label="'+T.close+'">'+ic('x')+'</button></div><ol class="vh-list" id="vhL"></ol></aside>';
  D.body.appendChild(vh);var vhL=vh.querySelector('#vhL'),vhSub=vh.querySelector('#vhSub'),vhBack=null;
  function closeVh(){vh.classList.remove('on');if(vhBack&&vhBack.focus)vhBack.focus()}
  vh.querySelector('.vh-scrim').onclick=closeVh;vh.querySelector('#vhX').onclick=closeVh;
  D.addEventListener('keydown',function(e){if(e.key==='Escape'&&vh.classList.contains('on'))closeVh()});
  function openHistory(slug){vhBack=D.activeElement;var p=A.byId[slug];vhSub.textContent=p?p.dataset.title:slug;vhL.innerHTML='<li class="vh-empty">…</li>';vh.classList.add('on');vh.querySelector('#vhX').focus();
    api('GET','/pages/'+encodeURIComponent(slug)+'/history').then(function(r){
      if(!r.ok){vhL.innerHTML='<li class="vh-empty">'+esc(r.data.message||T.uploadFail)+'</li>';return}
      var vs=r.data.versions||[];vhL.innerHTML=vs.map(function(v,i){return '<li class="vh-it'+(i===0?' cur':'')+'"><span class="av" aria-hidden="true">'+esc(A.initials(v.actor))+'</span><div class="vh-body">'+
        '<b>Version '+v.version+'</b>'+(i===0?'<span class="vh-tag">'+T.current+'</span>':'')+'<span class="vh-meta">'+esc(v.actor)+' · '+esc(A.fmt(v.ts))+' · '+esc(T['a_'+v.action]||v.action)+'</span>'+
        (v.note?'<p class="vh-note">'+esc(v.note)+'</p>':'')+'<div class="vh-acts">'+(i>0?'<button type="button" class="by-btn" data-vh-view="'+v.version+'">'+T.view+'</button>':'')+
        (i>0&&B.canEdit?'<button type="button" class="by-btn" data-vh-restore="'+v.version+'">'+T.restore+'</button>':'')+'</div></div></li>'}).join('')||'<li class="vh-empty">—</li>';
      vhL.querySelectorAll('[data-vh-view]').forEach(function(b){b.onclick=function(){closeVh();viewVersion(slug,+b.dataset.vhView)}});
      vhL.querySelectorAll('[data-vh-restore]').forEach(function(b){b.onclick=function(){closeVh();restoreVersion(slug,+b.dataset.vhRestore)}});})}
  var preview=null;
  function closePreview(){if(!preview)return;var s=preview.dataset.of;preview.remove();preview=null;A.show(s)}
  function viewVersion(slug,n){if(editing)return;api('GET','/pages/'+encodeURIComponent(slug)+'/versions/'+n).then(function(r){
    if(!r.ok){toast(r.data.message||T.uploadFail,true);return}
    closePreview();var orig=A.byId[slug];if(!orig)return;if(A.current()!==orig)A.show(slug);
    var v=r.data;preview=el('article','page on ed-preview');preview.dataset.of=slug;
    preview.innerHTML='<div class="ed-banner" role="status"><p>'+esc(f(T.viewing,{n:v.version,d:A.fmt(v.ts),a:v.actor}))+(v.note?' „'+esc(v.note)+'“':'')+'</p>'+
      (B.canEdit?'<button type="button" class="by-btn by-edit" data-pv="restore">'+T.restore+'</button>':'')+'<button type="button" class="by-btn" data-pv="back">'+T.backCurrent+'</button></div>'+v.html;
    preview.querySelectorAll('.copy').forEach(function(b){b.remove()});
    orig.classList.remove('on');orig.after(preview);scrollTo(0,0);
    preview.querySelector('[data-pv="back"]').onclick=closePreview;var rb=preview.querySelector('[data-pv="restore"]');if(rb)rb.onclick=function(){restoreVersion(slug,v.version)}})}
  addEventListener('hashchange',function(){if(preview){preview.remove();preview=null}});
  function restoreVersion(slug,n){dialog({title:f(T.restTitle,{n:n}),body:f(T.restBody,{n:n}),confirm:T.restore}).then(function(v){if(!v)return;
    api('POST','/pages/'+encodeURIComponent(slug)+'/restore',{version:n}).then(function(r){if(!r.ok){toast(r.data.message,true);return}
      flash(f(T.restored,{n:n,v:r.data.version}));location.hash=slug;reload()})})}
  D.addEventListener('click',function(e){var h=e.target.closest('[data-docs-history]');if(h){e.preventDefault();openHistory(h.dataset.docsHistory)}});

  if(!B.canEdit)return;

  /* ─────────────── Editor (nur mit Bearbeitungsrolle) ─────────────── */
  var metaEl=null,editing=null,art=null,frag=null,base=0,dirty=false,srcMode=false,savedRange=null,bar=null,draftT=null,busy=false;
  var MAX=B.maxUpload||10485760,IMG=['image/png','image/jpeg','image/gif','image/webp'];
  function dkey(s){return 'awp-docs-draft:'+s}
  function sget(k){try{return JSON.parse(localStorage.getItem(k)||'null')}catch(e){return null}}
  function sset(k,v){try{v===null?localStorage.removeItem(k):localStorage.setItem(k,JSON.stringify(v))}catch(e){}}

  // Knopf „Neue Seite“ im Kopf
  var tools=D.querySelector('.dx-tools');
  if(tools){var nb=el('button','by-btn by-edit','<svg class="i" aria-hidden="true"><use href="#i-plus"/></svg><span>'+T.newPage+'</span>');nb.type='button';nb.id='newPageBtn';nb.onclick=newPage;tools.insertBefore(nb,tools.firstChild)}
  D.addEventListener('click',function(e){var b=e.target.closest('[data-docs-edit]');if(b){e.preventDefault();startEdit(b.dataset.docsEdit)}});
  // nach Neuladen direkt weiter bearbeiten (neue Seite)
  try{var ee=sessionStorage.getItem('awp-docs-edit');if(ee){sessionStorage.removeItem('awp-docs-edit');setTimeout(function(){if(A.byId[ee])startEdit(ee)},50)}}catch(e){}

  function groupsList(){return '<datalist id="edGroups">'+(B.groups||[]).map(function(g){return '<option value="'+esc(g)+'">'}).join('')+'</datalist>'}
  function newPage(){var cur=A.current(),g=cur&&!cur.dataset.landing&&!cur.dataset.system?cur.dataset.group:(B.groups||[])[0]||'';
    dialog({title:T.newTitle,body:T.newBody,confirm:T.create,
      fields:'<label>'+T.title+'<input name="title" type="text" maxlength="120" required autocomplete="off"></label><label>'+T.group+'<input name="group" type="text" list="edGroups" maxlength="60" required value="'+esc(g)+'" autocomplete="off"></label>'+groupsList()+
        '<label>'+T.level+'<select name="level"><option value="">'+T.none+'</option><option>'+T.beginner+'</option><option>'+T.advanced+'</option></select></label>',
      validate:function(v){return !v.title.trim()?T.noTitle:''}}).then(function(v){if(!v)return;
      var after=cur&&cur.dataset.group===v.group.trim()&&!cur.dataset.system?cur.dataset.page:'';
      api('POST','/pages',{title:v.title,group:v.group,level:v.level,after:after}).then(function(r){if(!r.ok){toast(r.data.message,true);return}
        flash(f(T.created,{t:r.data.title}));try{sessionStorage.setItem('awp-docs-edit',r.data.slug)}catch(e){}location.hash=r.data.slug;reload()})})}

  function btn(name,title,fn,cls){var b=el('button','ed-b'+(cls?' '+cls:''),P[name]?ic(name):name);b.type='button';b.title=title;b.setAttribute('aria-label',title);
    b.addEventListener('mousedown',function(e){e.preventDefault()});b.addEventListener('click',function(){if(srcMode&&name!=='source')return;fn()});return b}
  function sep(){return el('span','ed-sep')}
  function exec(cmd,val){art.focus();D.execCommand(cmd,false,val===undefined?null:val);changed()}

  function buildBar(p){
    bar=el('div','ed-bar');bar.setAttribute('role','region');bar.setAttribute('aria-label',T.editing);
    var top=el('div','ed-top','<span class="ed-title">'+ic('edit')+T.editing+'</span><span class="ed-status" id="edStatus" aria-live="polite"></span>'+
      '<div class="ed-acts">'+(p.dataset.page!=='start'?'<button type="button" class="btn btn--secondary btn--danger" id="edDel">'+T.del+'</button>':'')+
      '<button type="button" class="btn btn--secondary" id="edCancel">'+T.cancel+'</button><button type="button" class="btn btn--primary" id="edSave" disabled>'+T.publish+'</button></div>');
    var tl=el('div','ed-tools');tl.setAttribute('role','toolbar');tl.setAttribute('aria-label','Format');
    var blk=el('select','ed-sel');blk.id='edBlock';blk.title='Absatzformat';blk.setAttribute('aria-label','Absatzformat');
    [['p','Text'],['h2','Überschrift 2'],['h3','Überschrift 3'],['h4','Überschrift 4'],['blockquote','Zitat'],['pre','Code (vorformatiert)']].forEach(function(o){var op=el('option');op.value=o[0];op.textContent=o[1];blk.appendChild(op)});
    blk.onchange=function(){restoreSel();exec('formatBlock','<'+blk.value+'>')};blk.addEventListener('mousedown',saveSel);
    tl.append(btn('undo','Rückgängig (Strg+Z)',function(){exec('undo')}),btn('redo','Wiederholen (Strg+Umschalt+Z)',function(){exec('redo')}),sep(),blk,sep(),
      btn('bold','Fett (Strg+B)',function(){exec('bold')},'cmd-bold'),btn('italic','Kursiv (Strg+I)',function(){exec('italic')},'cmd-italic'),
      btn('under','Unterstrichen (Strg+U)',function(){exec('underline')},'cmd-underline'),btn('strike','Durchgestrichen',function(){exec('strikeThrough')},'cmd-strikeThrough'),
      btn('code','Code im Text',inlineCode),btn('link','Link (Strg+K)',linkDialog),sep(),
      btn('ul','Aufzählung',function(){exec('insertUnorderedList')},'cmd-insertUnorderedList'),btn('ol','Nummerierte Liste',function(){exec('insertOrderedList')},'cmd-insertOrderedList'),sep(),
      btn('callout','Hinweisbox',function(){calloutMenu(this)}),btn('block','Befehl / Codeblock',codeBlock),btn('table','Tabelle',tableDialog),
      btn('image','Bild hochladen',function(){pick(IMG.join(','))}),btn('file','PDF anhängen',function(){pick('application/pdf')}),btn('hr','Trennlinie',function(){exec('insertHorizontalRule')}),sep(),
      btn('clear','Formatierung entfernen',function(){exec('removeFormat');exec('unlink')}),btn('source','HTML bearbeiten',toggleSource,'cmd-source'));
    var tb=el('span','ed-tbl');tb.id='edTbl';
    tb.append(sep(),btn('rowAdd','Zeile darunter einfügen',function(){tableOp('rowAdd')}),btn('colAdd','Spalte rechts einfügen',function(){tableOp('colAdd')}),
      btn('rowDel','Zeile löschen',function(){tableOp('rowDel')}),btn('colDel','Spalte löschen',function(){tableOp('colDel')}),btn('trash','Tabelle löschen',function(){tableOp('del')}));
    tl.appendChild(tb);
    var meta=el('div','ed-meta');
    var lvl=p.dataset.level||'';
    meta.innerHTML='<label class="ed-f">'+T.group+'<input id="edGroup" type="text" list="edGroups" maxlength="60" value="'+esc(p.dataset.group)+'"'+(p.dataset.landing?' disabled':'')+'></label>'+groupsList()+
      '<label class="ed-f">'+T.level+'<select id="edLevel"><option value="">'+T.none+'</option><option'+(lvl===T.beginner?' selected':'')+'>'+T.beginner+'</option><option'+(lvl===T.advanced?' selected':'')+'>'+T.advanced+'</option></select></label>'+
      '<label class="ed-f grow">'+T.note+'<input id="edNote" type="text" maxlength="300" placeholder="'+esc(T.notePh)+'" autocomplete="off"></label>';
    bar.append(top,tl);metaEl=meta;
    meta.querySelector('#edGroup').oninput=changed;meta.querySelector('#edLevel').onchange=changed;
    top.querySelector('#edSave').onclick=function(){save(false)};top.querySelector('#edCancel').onclick=cancel;
    var db=top.querySelector('#edDel');if(db)db.onclick=delPage;
    return bar}

  function status(t,cls){var s=D.getElementById('edStatus');if(s){s.textContent=t;s.className='ed-status'+(cls?' '+cls:'')}}
  function changed(){if(!editing)return;dirty=true;var sb=D.getElementById('edSave');if(sb)sb.disabled=false;status(T.dirty,'dirty');
    clearTimeout(draftT);draftT=setTimeout(function(){sset(dkey(editing),{html:serialize(),base:base,ts:new Date().toISOString(),group:val('edGroup'),level:val('edLevel'),note:val('edNote')});status(T.draft+' · '+A.fmt(new Date().toISOString()).split(', ')[1],'dirty')},700)}
  function val(id){var e=D.getElementById(id);return e?e.value:''}

  function startEdit(slug){
    if(editing){if(editing===slug)return;toast(T.leave,true);return}
    if(preview)closePreview();
    var p=A.byId[slug];if(!p)return;if(A.current()!==p)A.show(slug);
    api('GET','/pages/'+encodeURIComponent(slug)).then(function(r){
      if(!r.ok){toast(r.data.message||T.network,true);return}
      editing=slug;art=p;base=r.data.version;dirty=false;srcMode=false;
      frag=D.createDocumentFragment();while(p.firstChild)frag.appendChild(p.firstChild);
      p.innerHTML=r.data.html;p.dataset.version=r.data.version;
      p.querySelectorAll('svg').forEach(function(s){if(!s.closest('[contenteditable="false"]'))s.setAttribute('contenteditable','false')});
      p.querySelectorAll('.copy').forEach(function(b){b.setAttribute('contenteditable','false')});
      rememberStyles();p.contentEditable='true';p.spellcheck=true;p.classList.add('ed-on');D.body.classList.add('ed-mode');
      var content=D.querySelector('.dx-content');content.insertBefore(buildBar(p),content.firstChild);p.parentNode.insertBefore(metaEl,p);
      status(T.saved,'ok');
      var dr=sget(dkey(slug));
      if(dr&&dr.base===base&&dr.html){var bn=el('div','ed-banner ed-draft','<p>'+esc(f(T.draftFound,{d:A.fmt(dr.ts)}))+'</p><button type="button" class="by-btn by-edit">'+T.useDraft+'</button><button type="button" class="by-btn">'+T.dropDraft+'</button>');
        bn.setAttribute('contenteditable','false');p.prepend(bn);var bs=bn.querySelectorAll('button');
        bs[0].onclick=function(){bn.remove();p.innerHTML=dr.html;rememberStyles();if(dr.group)D.getElementById('edGroup').value=dr.group;if(dr.level!==undefined)D.getElementById('edLevel').value=dr.level;if(dr.note)D.getElementById('edNote').value=dr.note;changed()};
        bs[1].onclick=function(){bn.remove();sset(dkey(slug),null)}}
      else if(dr)sset(dkey(slug),null);
      var h1=p.querySelector('h1');var target=h1||p;placeCaret(target);scrollTo(0,0)})}

  function placeCaret(node){art.focus();var r=D.createRange();r.selectNodeContents(node);r.collapse(false);var s=getSelection();s.removeAllRanges();s.addRange(r)}
  function saveSel(){var s=getSelection();if(s.rangeCount&&art&&art.contains(s.anchorNode))savedRange=s.getRangeAt(0).cloneRange()}
  function restoreSel(){if(!savedRange)return;art.focus();var s=getSelection();s.removeAllRanges();s.addRange(savedRange)}

  function stop(){if(!art)return;art.contentEditable='false';art.removeAttribute('contenteditable');art.classList.remove('ed-on');D.body.classList.remove('ed-mode');
    if(bar)bar.remove();bar=null;if(metaEl)metaEl.remove();metaEl=null;imgbar.classList.remove('on');editing=null;dirty=false;srcMode=false;clearTimeout(draftT)}
  function cancel(){var go=function(){var p=art;sset(dkey(editing),null);stop();p.innerHTML='';p.appendChild(frag);frag=null;A.refreshMeta(p);A.show(p.dataset.page)};
    if(!dirty)return go();dialog({title:T.discardTitle,body:T.discardBody,confirm:T.discard,danger:true}).then(function(v){if(v)go()})}

  // HTML zum Speichern: Laufzeit-Zusätze und Editor-Attribute entfernen, Kopier-Text der Codeblöcke neu bilden
  // Stilangaben, die der Browser beim Bearbeiten selbst einfügt (z. B. font-size), entfernen; eigene Stile bleiben
  var origStyle=new WeakMap(),JUNK=/^(font(-[a-z]+)?|color|background(-color)?|line-height|letter-spacing|word-spacing|text-(decoration[a-z-]*|transform|indent|align)|white-space|display|vertical-align|caret-color|outline|orphans|widows|-webkit-[a-z-]+)$/;
  function rememberStyles(){art.querySelectorAll('[style]').forEach(function(x){origStyle.set(x,x.getAttribute('style'))})}
  function cleanStyles(){art.querySelectorAll('[style]').forEach(function(x){var st=x.getAttribute('style');if(origStyle.get(x)===st||x.closest('svg'))return;
    if(/var\(/.test(st))return;var props=st.split(';').map(function(d){return d.split(':')[0].trim().toLowerCase()}).filter(Boolean);
    if(props.every(function(pr){return JUNK.test(pr)}))x.removeAttribute('style')})}
  function serialize(){if(srcMode){var ta=art.querySelector('.ed-src');return ta?ta.value:''}
    cleanStyles();var c=art.cloneNode(true);
    c.querySelectorAll('[data-runtime],.dx-pagemeta,.anc,.ed-banner,.ed-uploading').forEach(function(x){x.remove()});
    c.querySelectorAll('[contenteditable]').forEach(function(x){x.removeAttribute('contenteditable')});
    c.querySelectorAll('.ed-sel-img').forEach(function(x){x.classList.remove('ed-sel-img');if(!x.className)x.removeAttribute('class')});
    c.querySelectorAll('.reveal.run').forEach(function(x){x.classList.remove('run')});
    c.querySelectorAll('.code').forEach(function(cd){var b=cd.querySelector('.copy');if(!b)return;var k=cd.cloneNode(true);k.querySelectorAll('.copy,.p,.c').forEach(function(x){x.remove()});
      k.querySelectorAll('br').forEach(function(x){x.replaceWith('\n')});b.setAttribute('data-copy',k.textContent.replace(/ /g,' ').replace(/[ \t]+\n/g,'\n').trim());b.setAttribute('type','button');b.textContent='Kopieren'});
    c.querySelectorAll('h2[id]').forEach(function(h){if(h.id.indexOf(editing+'--')===0)h.removeAttribute('id')});
    c.querySelectorAll('span:not([class]):not([style]):not([id])').forEach(function(s){s.replaceWith.apply(s,[].slice.call(s.childNodes))});
    return c.innerHTML.replace(/^\s+|\s+$/g,'')}

  function save(force){if(busy)return;
    var html=serialize(),tmp=el('div','',html),h1=tmp.querySelector('h1');
    if(!A.byId[editing].dataset.landing&&(!h1||!h1.textContent.trim())){toast(T.noTitle,true);return}
    busy=true;var sb=D.getElementById('edSave');sb.disabled=true;sb.textContent=T.publishing;
    var body={base_version:base,html:html,level:val('edLevel'),note:val('edNote')};if(!A.byId[editing].dataset.landing)body.group=val('edGroup');
    api('PUT','/pages/'+encodeURIComponent(editing),body).then(function(r){busy=false;sb.textContent=T.publish;
      if(r.ok){sset(dkey(editing),null);dirty=false;flash(f(T.published,{t:r.data.title,v:r.data.version}));location.hash=r.data.slug;reload();return}
      sb.disabled=false;
      if(r.status===409){dialog({title:T.confTitle,body:f(T.confBody,{a:r.data.updated_by,v:r.data.current_version}),confirm:T.confBtn,danger:true}).then(function(v){if(v){base=r.data.current_version;save(true)}});return}
      toast(r.data.message||T.network,true)})}

  function delPage(){var p=A.byId[editing],t=p.dataset.title;dialog({title:T.delTitle,body:f(T.delBody,{t:t}),confirm:T.delBtn,danger:true}).then(function(v){if(!v)return;
    api('DELETE','/pages/'+encodeURIComponent(editing)).then(function(r){if(!r.ok){toast(r.data.message,true);return}sset(dkey(editing),null);dirty=false;flash(f(T.deleted,{t:t}));location.hash='aenderungen';reload()})})}

  // Formate
  function inlineCode(){var s=getSelection();if(!s.rangeCount)return;var n=s.anchorNode&&(s.anchorNode.nodeType===1?s.anchorNode:s.anchorNode.parentNode),c=n&&n.closest('code');
    if(c&&art.contains(c)&&!c.closest('pre')){c.replaceWith(D.createTextNode(c.textContent));changed();return}
    var t=s.toString()||'code';exec('insertHTML','<code>'+esc(t)+'</code>&#8203;')}
  function insertBlock(html){exec('insertHTML',html+'<p><br></p>')}
  function codeBlock(){var t=getSelection().toString();insertBlock('<div class="code"><button class="copy" type="button" contenteditable="false">Kopieren</button><span class="p">$ </span>'+(t?esc(t):'befehl')+'</div>')}
  function calloutMenu(anchor){saveSel();dialog({title:'Hinweisbox einfügen',confirm:T.insert,fields:'<label>Art<select name="k"><option value="info">Hinweis</option><option value="tip">Tipp</option><option value="warn">Achtung</option><option value="wip">In Arbeit</option></select></label><label>Überschrift<input name="h" type="text" maxlength="80" value="Hinweis"></label>'}).then(function(v){if(!v)return;restoreSel();
    var icn={info:'i-info',tip:'i-check',warn:'i-warn',wip:'i-wip'}[v.k]||'i-info';
    insertBlock('<div class="callout c-'+v.k+'"><div class="ic" contenteditable="false"><svg class="i" aria-hidden="true"><use href="#'+icn+'"/></svg></div><div><h5>'+esc(v.h||T.calloutTitle[v.k])+'</h5><p>Text</p></div></div>')})}
  function pageOptions(){return Object.keys(A.byId).map(function(k){return '<option value="#'+esc(k)+'">'+esc(A.byId[k].dataset.title)+'</option>'}).join('')}
  function linkDialog(){saveSel();var s=getSelection(),n=s.anchorNode&&(s.anchorNode.nodeType===1?s.anchorNode:s.anchorNode.parentNode),a=n&&n.closest('a');if(a&&!art.contains(a))a=null;
    var text=a?a.textContent:s.toString();
    dialog({title:T.linkTitle,confirm:T.insert,fields:'<label>'+T.linkText+'<input name="t" type="text" value="'+esc(text)+'"></label><label>'+T.linkUrl+' <small>'+T.linkHint+'</small><input name="u" type="text" list="edPages" value="'+esc(a?a.getAttribute('href'):'')+'" required autocomplete="off"></label><datalist id="edPages">'+pageOptions()+'</datalist><label class="chk"><input type="checkbox" name="n"'+(a&&a.target==='_blank'?' checked':'')+'>'+T.linkNew+'</label>',
      validate:function(v){var u=v.u.trim();return /^(#|\/|https?:\/\/|mailto:)/i.test(u)?'':T.linkHint}}).then(function(v){if(!v)return;restoreSel();
      var u=v.u.trim(),t=v.t.trim()||u,h='<a href="'+esc(u)+'"'+(v.n?' target="_blank" rel="noopener noreferrer"':'')+'>'+esc(t)+'</a>';
      if(a){a.outerHTML=h;changed()}else exec('insertHTML',h)})}
  function tableDialog(){saveSel();dialog({title:T.tblTitle,confirm:T.insert,fields:'<div class="row"><label>'+T.rows+'<input name="r" type="number" min="1" max="50" value="3"></label><label>'+T.cols+'<input name="c" type="number" min="1" max="10" value="3"></label></div><label class="chk"><input type="checkbox" name="h" checked>'+T.header+'</label>'}).then(function(v){if(!v)return;restoreSel();
    var r=Math.min(50,Math.max(1,+v.r||3)),c=Math.min(10,Math.max(1,+v.c||3)),h='<div class="tbl-wrap"><table>';
    if(v.h){h+='<thead><tr>';for(var j=0;j<c;j++)h+='<th>'+T.colLabel+' '+(j+1)+'</th>';h+='</tr></thead>'}
    h+='<tbody>';for(var i=0;i<r;i++){h+='<tr>';for(var k=0;k<c;k++)h+='<td><br></td>';h+='</tr>'}h+='</tbody></table></div>';insertBlock(h)})}
  function cell(){var s=getSelection();if(!s.rangeCount)return null;var n=s.anchorNode;n=n&&(n.nodeType===1?n:n.parentNode);var td=n&&n.closest('td,th');return td&&art.contains(td)?td:null}
  function tableOp(op){var td=cell();if(!td)return;var tr=td.parentNode,table=td.closest('table'),idx=[].indexOf.call(tr.children,td);
    if(op==='rowAdd'){var nr=tr.cloneNode(true);nr.querySelectorAll('td,th').forEach(function(x){var d=D.createElement(tr.parentNode.tagName==='THEAD'?'td':x.tagName);d.innerHTML='<br>';x.replaceWith(d)});
      if(tr.parentNode.tagName==='THEAD'){var tb=table.tBodies[0]||table.appendChild(D.createElement('tbody'));tb.insertBefore(nr,tb.firstChild)}else tr.after(nr)}
    else if(op==='colAdd'){table.querySelectorAll('tr').forEach(function(r){var x=r.children[idx];var d=D.createElement(x&&x.tagName==='TH'?'th':'td');d.innerHTML=x&&x.tagName==='TH'?T.colLabel:'<br>';if(x)x.after(d);else r.appendChild(d)})}
    else if(op==='rowDel'){if(table.querySelectorAll('tr').length>1)tr.remove()}
    else if(op==='colDel'){if(tr.children.length>1)table.querySelectorAll('tr').forEach(function(r){if(r.children[idx])r.children[idx].remove()})}
    else if(op==='del'){(table.closest('.tbl-wrap')||table).remove()}
    changed()}

  // HTML-Ansicht
  function toggleSource(){var b=bar.querySelector('.cmd-source');
    if(!srcMode){var h=serialize();srcMode=true;art.contentEditable='false';art.innerHTML='';var ta=el('textarea','ed-src');ta.value=pretty(h);ta.spellcheck=false;ta.setAttribute('aria-label','HTML der Seite');ta.oninput=changed;art.appendChild(ta);ta.focus();b.setAttribute('aria-pressed','true')}
    else{var v=art.querySelector('.ed-src').value;srcMode=false;art.innerHTML=v;rememberStyles();art.contentEditable='true';art.querySelectorAll('svg').forEach(function(s){s.setAttribute('contenteditable','false')});b.setAttribute('aria-pressed','false');placeCaret(art.querySelector('h1')||art)}
    bar.querySelectorAll('.ed-tools .ed-b,.ed-tools select').forEach(function(x){if(!x.classList.contains('cmd-source'))x.disabled=srcMode})}
  function pretty(h){return h.replace(/>\s*<(\/?(?:p|h[1-6]|div|ul|ol|li|table|thead|tbody|tr|figure|figcaption|blockquote|pre|details|summary|section|hr|dl|dt|dd)\b)/g,'>\n<$1')}

  // Dateien: Auswahl, Einfügen aus der Zwischenablage, Ziehen und Ablegen
  var picker=el('input');picker.type='file';picker.hidden=true;D.body.appendChild(picker);
  function pick(accept){saveSel();picker.accept=accept;picker.multiple=accept!=='application/pdf';picker.value='';picker.onchange=function(){restoreSel();[].slice.call(picker.files).forEach(upload)};picker.click()}
  function upload(file){
    if(IMG.indexOf(file.type)<0&&file.type!=='application/pdf'){toast(T.badType,true);return}
    if(file.size>MAX){toast(f(T.tooBig,{mb:Math.round(MAX/1048576)}),true);return}
    var id='up'+Math.random().toString(36).slice(2);
    exec('insertHTML','<div class="ed-uploading" id="'+id+'" contenteditable="false">'+esc(file.name)+' – '+f(T.uploading,{n:0})+'<span><i></i></span></div><p><br></p>');
    var ph=D.getElementById(id);if(!ph){ph=el('div','ed-uploading',esc(file.name)+'<span><i></i></span>');ph.id=id;art.appendChild(ph)}var x=new XMLHttpRequest();x.open('POST',B.api+'/assets');x.setRequestHeader('X-CSRF-Token',B.csrf||'');x.setRequestHeader('Content-Type',file.type);
    x.upload.onprogress=function(e){if(e.lengthComputable&&ph){var n=Math.round(e.loaded/e.total*100);ph.firstChild.nodeValue=file.name+' – '+f(T.uploading,{n:n});ph.querySelector('i').style.width=n+'%'}};
    x.onload=function(){var d={};try{d=JSON.parse(x.responseText)}catch(e){}if(x.status!==201||!d.url){if(ph)ph.remove();toast(d.message||T.uploadFail,true);return}
      var name=file.name.replace(/\.[^.]+$/,'').replace(/[-_]+/g,' ');
      if(file.type==='application/pdf'){var a=el('a','dx-file',ic('file')+esc(file.name));a.href=d.url;ph.replaceWith(a);changed();return}
      var fig=el('figure','dx-img img-l','<img src="'+esc(d.url)+'" alt="'+esc(name)+'" loading="lazy"><figcaption></figcaption>');ph.replaceWith(fig);changed();
      var img=fig.querySelector('img');img.onload=function(){if(img.naturalWidth<480){fig.classList.remove('img-l');fig.classList.add(img.naturalWidth<300?'img-s':'img-m')}};altDialog(img)};
    x.onerror=function(){if(ph)ph.remove();toast(T.network,true)};x.send(file)}
  function altDialog(img){var fig=img.closest('figure'),cap=fig&&fig.querySelector('figcaption');
    dialog({title:T.imgTitle,confirm:T.save,fields:'<label>'+T.alt+' <small>'+T.altHint+'</small><input name="a" type="text" maxlength="200" value="'+esc(img.alt)+'"></label>'+(cap?'<label>'+T.caption+'<input name="c" type="text" maxlength="300" value="'+esc(cap.textContent)+'"></label>':'')}).then(function(v){if(!v)return;
      img.alt=v.a.trim();if(cap){cap.textContent=(v.c||'').trim()}changed()})}

  // Werkzeugleiste am Bild
  var imgbar=el('div','ed-imgbar'),selImg=null;D.body.appendChild(imgbar);
  function setSize(c){var fg=selImg&&selImg.closest('figure');if(!fg)return;fg.classList.remove('img-s','img-m','img-l');fg.classList.add(c);changed();placeImgbar()}
  imgbar.append(btn('sizeS','Klein',function(){setSize('img-s')}),btn('sizeM','Mittel',function(){setSize('img-m')}),btn('sizeL','Volle Breite',function(){setSize('img-l')}),
    btn('center','Zentrieren',function(){var fg=selImg&&selImg.closest('figure');if(fg){fg.classList.toggle('img-c');changed()}}),
    btn('alt','Alternativtext und Bildunterschrift',function(){if(selImg)altDialog(selImg)}),btn('trash','Bild entfernen',function(){if(!selImg)return;(selImg.closest('figure')||selImg).remove();selImg=null;imgbar.classList.remove('on');changed()}));
  function placeImgbar(){if(!selImg)return;var r=selImg.getBoundingClientRect();imgbar.style.left=(r.left+scrollX+8)+'px';imgbar.style.top=(r.top+scrollY+8)+'px';imgbar.classList.add('on')}
  D.addEventListener('click',function(e){if(!editing||srcMode)return;var im=e.target.closest('img');
    D.querySelectorAll('.ed-sel-img').forEach(function(x){x.classList.remove('ed-sel-img')});
    if(im&&art.contains(im)){selImg=im;im.classList.add('ed-sel-img');placeImgbar()}else if(!e.target.closest('.ed-imgbar')){selImg=null;imgbar.classList.remove('on')}
    var a=e.target.closest('a');if(a&&art.contains(a))e.preventDefault()},true);
  addEventListener('resize',placeImgbar);addEventListener('scroll',function(){if(selImg)placeImgbar()},{passive:true});

  // Einfügen: Dateien hochladen, fremdes HTML vereinfachen
  var KEEP={P:1,H2:1,H3:1,H4:1,UL:1,OL:1,LI:1,A:1,B:1,STRONG:1,I:1,EM:1,U:1,S:1,CODE:1,PRE:1,BLOCKQUOTE:1,BR:1,TABLE:1,THEAD:1,TBODY:1,TR:1,TH:1,TD:1,HR:1,KBD:1};
  function simplify(html){var box=new DOMParser().parseFromString(html,'text/html').body;box.querySelectorAll('script,style,meta,link,title,img,svg,iframe,object').forEach(function(x){x.remove()});
    (function walk(n){[].slice.call(n.childNodes).forEach(function(c){if(c.nodeType===8){c.remove();return}if(c.nodeType!==1)return;walk(c);
      if(c.tagName==='H1'){var h=D.createElement('h2');h.innerHTML=c.innerHTML;c.replaceWith(h);return}
      if(!KEEP[c.tagName]){if(/^(DIV|SECTION|ARTICLE)$/.test(c.tagName)){var p=D.createElement('p');p.innerHTML=c.innerHTML;c.replaceWith(p)}else c.replaceWith.apply(c,[].slice.call(c.childNodes));return}
      [].slice.call(c.attributes).forEach(function(a){if(!(c.tagName==='A'&&a.name==='href'))c.removeAttribute(a.name)})})})(box);
    box.querySelectorAll('table').forEach(function(t){if(!t.parentNode.classList||!t.parentNode.classList.contains('tbl-wrap')){var w=el('div','tbl-wrap');t.replaceWith(w);w.appendChild(t)}});
    box.querySelectorAll('p,li,h2,h3,h4').forEach(function(x){if(!x.textContent.trim()&&!x.querySelector('br'))x.remove()});
    return box.innerHTML}
  function onPaste(e){if(!editing||srcMode)return;var cd=e.clipboardData;if(!cd)return;
    var files=[].slice.call(cd.files||[]).filter(function(x){return IMG.indexOf(x.type)>-1||x.type==='application/pdf'});
    if(files.length){e.preventDefault();files.forEach(upload);return}
    var h=cd.getData('text/html');if(h&&!e.target.closest('pre,.code')){e.preventDefault();exec('insertHTML',simplify(h));return}
    var t=cd.getData('text/plain');if(t){e.preventDefault();exec('insertText',t)}}
  var drop=el('div','ed-drop','<b>'+T.dropHere+'</b>'),dragN=0;D.body.appendChild(drop);
  D.addEventListener('dragenter',function(e){if(editing&&!srcMode&&e.dataTransfer&&[].indexOf.call(e.dataTransfer.types,'Files')>-1){dragN++;drop.classList.add('on')}});
  D.addEventListener('dragleave',function(){if(--dragN<=0){dragN=0;drop.classList.remove('on')}});
  D.addEventListener('dragover',function(e){if(editing&&e.dataTransfer&&[].indexOf.call(e.dataTransfer.types,'Files')>-1)e.preventDefault()});
  D.addEventListener('drop',function(e){dragN=0;drop.classList.remove('on');if(!editing||srcMode||!e.dataTransfer||!e.dataTransfer.files.length)return;e.preventDefault();
    var r=D.caretRangeFromPoint?D.caretRangeFromPoint(e.clientX,e.clientY):null;if(!r&&D.caretPositionFromPoint){var cp=D.caretPositionFromPoint(e.clientX,e.clientY);if(cp){r=D.createRange();r.setStart(cp.offsetNode,cp.offset)}}
    if(r&&art.contains(r.startContainer)){var s=getSelection();s.removeAllRanges();s.addRange(r)}else placeCaret(art);
    [].slice.call(e.dataTransfer.files).forEach(upload)});

  // Tastatur, Eingaben, Zustand der Werkzeugleiste
  D.addEventListener('paste',onPaste,true);
  D.addEventListener('input',function(e){if(editing&&art.contains(e.target))changed()});
  D.addEventListener('keydown',function(e){if(!editing)return;var k=e.key.toLowerCase(),mod=e.ctrlKey||e.metaKey;
    if(mod&&k==='s'){e.preventDefault();if(dirty)save(false);return}
    if(srcMode||!art.contains(e.target))return;
    if(mod&&k==='k'){e.preventDefault();e.stopPropagation();linkDialog();return}
    if(e.key==='Tab'&&e.target.closest&&getSelection().anchorNode&&(getSelection().anchorNode.parentNode.closest('pre'))){e.preventDefault();D.execCommand('insertText',false,'  ')}
  },true);
  D.addEventListener('selectionchange',function(){if(!editing||srcMode||!bar)return;var s=getSelection();if(!s.rangeCount||!art.contains(s.anchorNode))return;
    ['bold','italic','underline','strikeThrough','insertUnorderedList','insertOrderedList'].forEach(function(c){var b=bar.querySelector('.cmd-'+c);if(b)b.setAttribute('aria-pressed',String(D.queryCommandState(c)))});
    var n=s.anchorNode.nodeType===1?s.anchorNode:s.anchorNode.parentNode,blk=n.closest('h2,h3,h4,blockquote,pre,p'),sel=D.getElementById('edBlock');
    if(sel)sel.value=blk&&art.contains(blk)?blk.tagName.toLowerCase():'p';
    D.getElementById('edTbl').classList.toggle('on',!!cell())});
  addEventListener('beforeunload',function(e){if(editing&&dirty){e.preventDefault();e.returnValue=''}});
  // Navigation während der Bearbeitung: Entwurf bleibt gespeichert, Editor schließt
  addEventListener('hashchange',function(){if(!editing)return;setTimeout(function(){if(A.current()!==art){if(dirty){sset(dkey(editing),{html:serialize(),base:base,ts:new Date().toISOString(),group:val('edGroup'),level:val('edLevel'),note:val('edNote')});toast(T.leave)}
    var p=art;stop();p.innerHTML='';p.appendChild(frag);frag=null;A.refreshMeta(p)}},0)});
})();
