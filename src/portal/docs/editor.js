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
  function viewVersion(slug,n){if(E&&E.slug)return;api('GET','/pages/'+encodeURIComponent(slug)+'/versions/'+n).then(function(r){
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

  /* ═════════════════ Editor (nur mit Bearbeitungsrolle) ═════════════════
     Fokus-Modus mit Kopfleiste, Formatleiste, „/“-Befehlen, Blase über markiertem Text, Link-Karte,
     Tabellen- und Bildleiste, Markdown-Kürzeln, Entwurf im Browser und Veröffentlichen-Dialog. */
  var E={slug:null,art:null,frag:null,base:0,dirty:false,src:false,group:'',level:'',busy:false,draftT:null,range:null,origStyle:new WeakMap()};
  var MAX=B.maxUpload||10485760,IMG=['image/png','image/jpeg','image/gif','image/webp'];
  var bar=null,metaTitle=null;
  var U={ // weitere Texte des Editors
    edit:'Bearbeiten',close:'Schließen',more:'Weitere Aktionen',insert:'Einfügen',style:'Absatzformat',noHits:'Kein Treffer',
    clean:'Keine Änderungen',unsaved:'Nicht veröffentlicht',draftAt:'Entwurf gespeichert · {t}',words:'{n} Wörter',
    settings:'Seiteneinstellungen …',html:'HTML bearbeiten',htmlBack:'Zurück zum Editor',keys:'Tastenkürzel',delete:'Seite löschen …',
    settingsTitle:'Seiteneinstellungen',apply:'Übernehmen',
    pubTitle:'Änderungen veröffentlichen',pubBody:'Alle mit Zugriff auf die Dokumentation sehen danach die neue Fassung. Die bisherige bleibt im Versionsverlauf.',
    pubNote:'Was haben Sie geändert?',pubNoteHint:'Optional, erscheint im Verlauf und unter „Letzte Änderungen“.',pubVersion:'Wird Version {v}',
    ph:'Text eingeben oder „/“ für Befehle',phH:'Überschrift',open:'Öffnen',editLink:'Bearbeiten',unlink:'Entfernen',
    keysTitle:'Tastenkürzel',ctrl:/Mac|iPhone|iPad/.test(navigator.platform)?'⌘':'Strg'
  };
  function sget(k){try{return JSON.parse(localStorage.getItem(k)||'null')}catch(e){return null}}
  function sset(k,v){try{v===null?localStorage.removeItem(k):localStorage.setItem(k,JSON.stringify(v))}catch(e){}}
  function dkey(s){return 'awp-docs-draft:'+s}
  function norm(s){return String(s).toLowerCase().replace(/ä/g,'ae').replace(/ö/g,'oe').replace(/ü/g,'ue').replace(/ß/g,'ss')}
  Object.assign(P,{
    plus:'<path d="M12 5v14M5 12h14"/>',more:'<circle cx="5" cy="12" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="19" cy="12" r="1.2"/>',
    gear:'<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1"/>',
    keys:'<rect x="2" y="6" width="20" height="12"/><path d="M6 10h1M10 10h1M14 10h1M18 10h1M7 14h10"/>',ext:'<path d="M14 4h6v6M20 4l-9 9M18 14v6H4V6h6"/>',
    unlink:'<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1M4 4l16 16"/>',
    h2:'<path d="M4 6v12M12 6v12M4 12h8"/><path d="M15 10a2.5 2.5 0 1 1 4.5 1.5L15 18h5"/>',h3:'<path d="M4 6v12M12 6v12M4 12h8"/><path d="M15 8h5l-3 4a3 3 0 1 1-2.6 4.5"/>',
    h4:'<path d="M4 6v12M12 6v12M4 12h8"/><path d="M19 18V8l-5 7h6"/>',text:'<path d="M5 6h14M12 6v13"/>',chev:'<path d="M7 10l5 5 5-5"/>',pre:'<path d="M8 7l-5 5 5 5M16 7l5 5-5 5"/>'
  });
  function sp(id){return '<svg class="i" aria-hidden="true" focusable="false"><use href="#'+id+'"/></svg>'}

  // Knopf „Neue Seite“ im Kopf und Einstieg „Bearbeiten“
  var tools=D.querySelector('.dx-tools');
  if(tools){var nb=el('button','by-btn by-edit','<svg class="i" aria-hidden="true"><use href="#i-plus"/></svg><span>'+T.newPage+'</span>');nb.type='button';nb.id='newPageBtn';nb.onclick=newPage;tools.insertBefore(nb,tools.firstChild)}
  D.addEventListener('click',function(e){var b=e.target.closest('[data-docs-edit]');if(b){e.preventDefault();startEdit(b.dataset.docsEdit)}});
  try{var ee=sessionStorage.getItem('awp-docs-edit');if(ee){sessionStorage.removeItem('awp-docs-edit');setTimeout(function(){if(A.byId[ee])startEdit(ee)},50)}}catch(e){}
  addEventListener('keydown',function(e){if(!E.slug&&e.key==='e'&&!e.ctrlKey&&!e.metaKey&&!e.altKey&&!/INPUT|TEXTAREA|SELECT/.test(D.activeElement.tagName)&&!D.activeElement.isContentEditable){var c=A.current();if(c&&!c.dataset.system&&D.querySelector('[data-docs-edit="'+c.dataset.page+'"]')){e.preventDefault();startEdit(c.dataset.page)}}});

  function groupsList(){return '<datalist id="edGroups">'+(B.groups||[]).map(function(g){return '<option value="'+esc(g)+'">'}).join('')+'</datalist>'}
  function levelSelect(name,v){return '<select name="'+name+'"><option value="">'+T.none+'</option><option'+(v===T.beginner?' selected':'')+'>'+T.beginner+'</option><option'+(v===T.advanced?' selected':'')+'>'+T.advanced+'</option></select>'}
  function newPage(){var cur=A.current(),g=cur&&!cur.dataset.landing&&!cur.dataset.system?cur.dataset.group:(B.groups||[])[0]||'';
    dialog({title:T.newTitle,body:T.newBody,confirm:T.create,
      fields:'<label>'+T.title+'<input name="title" type="text" maxlength="120" required autocomplete="off"></label><label>'+T.group+'<input name="group" type="text" list="edGroups" maxlength="60" required value="'+esc(g)+'" autocomplete="off"></label>'+groupsList()+'<label>'+T.level+levelSelect('level','')+'</label>',
      validate:function(v){return !v.title.trim()?T.noTitle:''}}).then(function(v){if(!v)return;
      var after=cur&&cur.dataset.group===v.group.trim()&&!cur.dataset.system?cur.dataset.page:'';
      api('POST','/pages',{title:v.title,group:v.group,level:v.level,after:after}).then(function(r){if(!r.ok){toast(r.data.message,true);return}
        flash(f(T.created,{t:r.data.title}));try{sessionStorage.setItem('awp-docs-edit',r.data.slug)}catch(e){}location.hash=r.data.slug;reload()})})}

  /* ── Befehle ── */
  function sel(){return getSelection()}
  function inArt(n){return !!(E.art&&n&&E.art.contains(n.nodeType===1?n:n.parentNode))}
  function exec(cmd,val){E.art.focus();D.execCommand(cmd,false,val===undefined?null:val);changed()}
  function block(tag){var cur=curBlock();if(cur&&cur.tagName.toLowerCase()===tag&&tag!=='p')tag='p';exec('formatBlock','<'+tag+'>')}
  function insertBlock(html){exec('insertHTML',html+'<p><br></p>')}
  function curBlock(){var s=sel();if(!s.rangeCount||!inArt(s.anchorNode))return null;var n=s.anchorNode.nodeType===1?s.anchorNode:s.anchorNode.parentNode;var b=n.closest('p,h1,h2,h3,h4,h5,li,blockquote,pre,td,th,figcaption,div');return b&&E.art.contains(b)?b:null}
  var CI={info:'i-info',tip:'i-check',warn:'i-warn',wip:'i-wip'};
  function callout(k){insertBlock('<div class="callout c-'+k+'"><div class="ic" contenteditable="false">'+sp(CI[k])+'</div><div><h5>'+T.calloutTitle[k]+'</h5><p>Text</p></div></div>')}
  function table(){var h='<div class="tbl-wrap"><table><thead><tr>';for(var j=0;j<3;j++)h+='<th>'+T.colLabel+' '+(j+1)+'</th>';h+='</tr></thead><tbody>';for(var i=0;i<3;i++)h+='<tr><td><br></td><td><br></td><td><br></td></tr>';insertBlock(h+'</tbody></table></div>')}
  function command(){var t=sel().toString();insertBlock('<div class="code"><button class="copy" type="button" contenteditable="false">Kopieren</button><span class="p">$ </span>'+(t?esc(t):'befehl')+'</div>')}
  function preBlock(){var t=sel().toString();insertBlock('<pre><code>'+(t?esc(t):'code')+'</code></pre>')}
  function inlineCode(){var s=sel();if(!s.rangeCount)return;var n=s.anchorNode&&(s.anchorNode.nodeType===1?s.anchorNode:s.anchorNode.parentNode),c=n&&n.closest('code');
    if(c&&E.art.contains(c)&&!c.closest('pre')){c.replaceWith(D.createTextNode(c.textContent));changed();return}
    exec('insertHTML','<code>'+esc(s.toString()||'code')+'</code>&#8203;')}

  var ITEMS=[
    {t:'Text',d:'Normaler Absatz',i:ic('text'),k:'text absatz paragraph p',run:function(){block('p')}},
    {t:'Überschrift 2',d:'Neuer Abschnitt, erscheint im Inhaltsverzeichnis',i:ic('h2'),k:'ueberschrift h2 titel abschnitt',run:function(){block('h2')}},
    {t:'Überschrift 3',d:'Unterabschnitt',i:ic('h3'),k:'ueberschrift h3 unter',run:function(){block('h3')}},
    {t:'Überschrift 4',d:'Kleine Zwischenüberschrift',i:ic('h4'),k:'ueberschrift h4',run:function(){block('h4')}},
    {t:'Aufzählung',d:'Liste mit Punkten',i:ic('ul'),k:'liste aufzaehlung punkte bullet ul',run:function(){exec('insertUnorderedList')}},
    {t:'Nummerierte Liste',d:'Liste mit 1, 2, 3',i:ic('ol'),k:'liste nummeriert zahlen schritte ol',run:function(){exec('insertOrderedList')}},
    {t:'Bild',d:'Hochladen – oder einfügen bzw. hineinziehen',i:ic('image'),k:'bild foto screenshot grafik image',run:function(){pick(IMG.join(','))}},
    {t:'Tabelle',d:'3 × 3, Zeilen und Spalten später anpassen',i:ic('table'),k:'tabelle table',run:table},
    {t:'Hinweis',d:'Blaue Box für wichtige Informationen',i:sp('i-info'),k:'hinweis info box callout',run:function(){callout('info')}},
    {t:'Tipp',d:'Grüne Box für Tipps',i:sp('i-check'),k:'tipp gruen box callout',run:function(){callout('tip')}},
    {t:'Achtung',d:'Gelbe Box für Warnungen',i:sp('i-warn'),k:'achtung warnung warn box callout',run:function(){callout('warn')}},
    {t:'In Arbeit',d:'Graue Box für Unfertiges',i:sp('i-wip'),k:'in arbeit todo wip box',run:function(){callout('wip')}},
    {t:'Befehl',d:'Terminal-Befehl mit Kopier-Knopf',i:ic('block'),k:'befehl terminal shell kommando code',run:command},
    {t:'Codeblock',d:'Mehrzeiliger Code, vorformatiert',i:ic('pre'),k:'code codeblock pre quelltext',run:preBlock},
    {t:'Zitat',d:'Hervorgehobenes Zitat',i:ic('quote'),k:'zitat quote',run:function(){block('blockquote')}},
    {t:'Link',d:'Zu einer Docs-Seite oder einer Adresse',i:ic('link'),k:'link verweis url seite',run:function(){linkDialog()}},
    {t:'PDF-Datei',d:'Als Download anhängen',i:ic('file'),k:'pdf datei anhang download',run:function(){pick('application/pdf')}},
    {t:'Trennlinie',d:'Horizontale Linie',i:ic('hr'),k:'trennlinie linie hr',run:function(){exec('insertHorizontalRule')}}
  ];

  /* ── Schwebendes Menü (für „/“, „Einfügen“ und „⋯“) ── */
  var menu=el('div','ed-menu');menu.setAttribute('role','listbox');menu.hidden=true;D.body.appendChild(menu);
  var M={items:[],sel:0,slash:null,title:''};
  menu.addEventListener('mousedown',function(e){e.preventDefault()});
  function openMenu(items,x,y,o){o=o||{};M.items=items;M.sel=0;M.slash=o.slash||null;M.title=o.title||'';renderMenu();menu.hidden=false;
    var w=menu.offsetWidth,h=menu.offsetHeight;x=Math.max(8,Math.min(x,innerWidth-w-8));if(y+h>innerHeight-8&&o.above)y=o.above-h-6;menu.style.left=x+'px';menu.style.top=Math.max(8,Math.min(y,innerHeight-h-8))+'px'}
  function renderMenu(){menu.innerHTML=(M.title?'<div class="ed-menu-h">'+esc(M.title)+'</div>':'')+(M.items.length?M.items.map(function(it,i){
      return '<button type="button" role="option" class="ed-mi'+(i===M.sel?' on':'')+(it.danger?' danger':'')+'" data-i="'+i+'" aria-selected="'+(i===M.sel)+'"><span class="ed-mi-ic">'+(it.i||'')+'</span><span class="ed-mi-t"><b>'+esc(it.t)+'</b>'+(it.d?'<small>'+esc(it.d)+'</small>':'')+'</span>'+(it.kbd?'<kbd>'+esc(it.kbd)+'</kbd>':'')+'</button>'}).join(''):'<div class="ed-menu-empty">'+U.noHits+'</div>');
    menu.querySelectorAll('.ed-mi').forEach(function(b){b.onclick=function(){pickMenu(+b.dataset.i)};b.onmouseenter=function(){M.sel=+b.dataset.i;mark()}})}
  function mark(){menu.querySelectorAll('.ed-mi').forEach(function(b,i){b.classList.toggle('on',i===M.sel);b.setAttribute('aria-selected',String(i===M.sel))});var o=menu.querySelector('.ed-mi.on');if(o)o.scrollIntoView({block:'nearest'})}
  function closeMenu(){menu.hidden=true;M.slash=null}
  function pickMenu(i){var it=M.items[i];if(!it)return;var slash=M.slash;closeMenu();
    if(slash){var s=sel();if(s.rangeCount){var r=D.createRange();try{r.setStart(slash.node,slash.start);r.setEnd(s.anchorNode,s.anchorOffset);r.deleteContents();s.removeAllRanges();s.addRange(r)}catch(e){}}}
    else if(E.range&&!it.keepFocus){restoreSel()}
    it.run()}
  function filterItems(q){q=norm(q.trim());if(!q)return ITEMS.slice();return ITEMS.filter(function(it){return norm(it.t+' '+it.k).indexOf(q)>-1})}
  function caretRect(){var s=sel();if(!s.rangeCount)return null;var r=s.getRangeAt(0).cloneRange();r.collapse(true);var rs=r.getClientRects();if(rs.length)return rs[0];var n=s.anchorNode.nodeType===1?s.anchorNode:s.anchorNode.parentNode;return n.getBoundingClientRect()}
  function slashCheck(){var s=sel();if(!E.slug||E.src||!s.isCollapsed||!s.rangeCount||!inArt(s.anchorNode)){if(M.slash)closeMenu();return}
    var n=s.anchorNode;if(n.nodeType!==3){if(M.slash)closeMenu();return}
    var before=n.data.slice(0,s.anchorOffset),m=before.match(/(?:^|[\s ])\/([^\s\/]{0,24})$/);
    if(!m){if(M.slash)closeMenu();return}
    var start=s.anchorOffset-m[1].length-1,items=filterItems(m[1]),r=caretRect();
    if(menu.hidden&&r&&r.bottom+380>innerHeight){scrollBy(0,r.bottom+380-innerHeight);r=caretRect()}
    if(!items.length&&m[1].length>3){closeMenu();return}
    openMenu(items,r.left-8,r.bottom+6,{slash:{node:n,start:start},title:U.insert,above:r.top})}

  /* ── Blase über markiertem Text, Link-Karte, Tabellen- und Bildleiste ── */
  function floatBar(cls,btns){var b=el('div','ed-float '+cls);b.hidden=true;b.addEventListener('mousedown',function(e){if(!e.target.closest('a'))e.preventDefault()});btns.forEach(function(x){b.appendChild(x)});D.body.appendChild(b);return b}
  function fbtn(name,title,fn,label){var b=el('button','ed-b'+(label?' txt':''),label?(P[name]?ic(name):'')+'<span>'+esc(label)+'</span>':ic(name));b.type='button';b.title=title;b.setAttribute('aria-label',title);b.addEventListener('mousedown',function(e){e.preventDefault()});b.addEventListener('click',function(e){e.preventDefault();fn()});return b}
  function place(elm,rect,above){elm.hidden=false;var w=elm.offsetWidth,h=elm.offsetHeight,x=Math.max(8,Math.min(rect.left+rect.width/2-w/2,innerWidth-w-8)),y=above?rect.top-h-8:rect.bottom+8;
    var top=(bar?bar.getBoundingClientRect().bottom:0)+4;if(above&&y<top)y=rect.bottom+8;elm.style.left=x+'px';elm.style.top=y+'px'}
  var bubble=floatBar('ed-bubble',[fbtn('bold','Fett ('+U.ctrl+'+B)',function(){exec('bold')}),fbtn('italic','Kursiv ('+U.ctrl+'+I)',function(){exec('italic')}),fbtn('code','Code im Text',inlineCode),
    fbtn('link','Link ('+U.ctrl+'+K)',function(){linkDialog()}),fbtn('h2','Überschrift 2',function(){block('h2')}),fbtn('h3','Überschrift 3',function(){block('h3')}),fbtn('clear','Formatierung entfernen',function(){exec('removeFormat')})]);
  var linkCard=floatBar('ed-linkcard',[]),curLink=null;
  function showLinkCard(a){curLink=a;var href=a.getAttribute('href')||'';linkCard.innerHTML='';var go=el('a','ed-lc-url',ic('ext')+'<span>'+esc(href)+'</span>');go.href=href.charAt(0)==='#'?href:href;go.target=href.charAt(0)==='#'?'_self':'_blank';go.rel='noopener noreferrer';go.title=U.open;
    linkCard.append(go,fbtn('edit',U.editLink,function(){linkDialog(curLink)},U.editLink),fbtn('unlink',U.unlink,function(){var t=D.createTextNode(curLink.textContent);curLink.replaceWith(t);linkCard.hidden=true;changed()},U.unlink));place(linkCard,a.getBoundingClientRect(),false)}
  function tableOp(op){var td=cell();if(!td)return;var tr=td.parentNode,tbl=td.closest('table'),idx=[].indexOf.call(tr.children,td);
    if(op==='rowAdd'){var nr=tr.cloneNode(true);nr.querySelectorAll('td,th').forEach(function(x){var d=D.createElement(tr.parentNode.tagName==='THEAD'?'td':x.tagName);d.innerHTML='<br>';x.replaceWith(d)});
      if(tr.parentNode.tagName==='THEAD'){var tb=tbl.tBodies[0]||tbl.appendChild(D.createElement('tbody'));tb.insertBefore(nr,tb.firstChild)}else tr.after(nr)}
    else if(op==='colAdd'){tbl.querySelectorAll('tr').forEach(function(r){var x=r.children[idx];var d=D.createElement(x&&x.tagName==='TH'?'th':'td');d.innerHTML=x&&x.tagName==='TH'?T.colLabel:'<br>';if(x)x.after(d);else r.appendChild(d)})}
    else if(op==='rowDel'){if(tbl.querySelectorAll('tr').length>1)tr.remove()}
    else if(op==='colDel'){if(tr.children.length>1)tbl.querySelectorAll('tr').forEach(function(r){if(r.children[idx])r.children[idx].remove()})}
    else if(op==='del'){(tbl.closest('.tbl-wrap')||tbl).remove();tblBar.hidden=true}
    changed();refreshFloats()}
  var tblBar=floatBar('ed-tblbar',[fbtn('rowAdd','Zeile darunter einfügen',function(){tableOp('rowAdd')},'Zeile'),fbtn('colAdd','Spalte rechts einfügen',function(){tableOp('colAdd')},'Spalte'),
    fbtn('rowDel','Zeile löschen',function(){tableOp('rowDel')}),fbtn('colDel','Spalte löschen',function(){tableOp('colDel')}),fbtn('trash','Tabelle löschen',function(){tableOp('del')})]);
  function cell(){var s=sel();if(!s.rangeCount)return null;var n=s.anchorNode;n=n&&(n.nodeType===1?n:n.parentNode);var td=n&&n.closest('td,th');return td&&E.art&&E.art.contains(td)?td:null}
  var selImg=null;
  function setSize(c){var fg=selImg&&selImg.closest('figure');if(!fg)return;fg.classList.remove('img-s','img-m','img-l');fg.classList.add(c);changed();refreshFloats()}
  var imgBar=floatBar('ed-imgbar',[fbtn('sizeS','Klein',function(){setSize('img-s')}),fbtn('sizeM','Mittel',function(){setSize('img-m')}),fbtn('sizeL','Volle Breite',function(){setSize('img-l')}),
    fbtn('center','Zentrieren',function(){var fg=selImg&&selImg.closest('figure');if(fg){fg.classList.toggle('img-c');changed()}}),
    fbtn('alt','Alternativtext und Bildunterschrift',function(){if(selImg)altDialog(selImg)},'Beschreibung'),fbtn('trash','Bild entfernen',function(){if(!selImg)return;(selImg.closest('figure')||selImg).remove();selImg=null;imgBar.hidden=true;changed()})]);
  function hideFloats(){[bubble,linkCard,tblBar,imgBar].forEach(function(x){x.hidden=true})}
  function refreshFloats(){if(!E.slug||E.src){hideFloats();return}
    if(selImg&&E.art.contains(selImg)){place(imgBar,selImg.getBoundingClientRect(),true);bubble.hidden=linkCard.hidden=tblBar.hidden=true;return}imgBar.hidden=true;
    var s=sel(),ok=s.rangeCount&&inArt(s.anchorNode)&&inArt(s.focusNode);
    if(ok&&!s.isCollapsed&&menu.hidden&&s.toString().trim()){var r=s.getRangeAt(0).getBoundingClientRect();place(bubble,r,true)}else bubble.hidden=true;
    var n=ok&&(s.anchorNode.nodeType===1?s.anchorNode:s.anchorNode.parentNode),a=n&&n.closest('a');
    if(ok&&s.isCollapsed&&a&&E.art.contains(a))showLinkCard(a);else linkCard.hidden=true;
    var td=ok&&cell();if(td){var t=td.closest('.tbl-wrap')||td.closest('table'),rc=t.getBoundingClientRect();place(tblBar,{left:rc.left,width:rc.width,top:rc.top,bottom:rc.bottom},true)}else tblBar.hidden=true}

  /* ── Platzhalter in leeren Zeilen ── */
  var phEl=null;
  function placeholder(){if(phEl){phEl.classList.remove('ed-ph');if(!phEl.className)phEl.removeAttribute('class');phEl=null}
    if(!E.slug||E.src)return;var b=curBlock();if(!b||!/^(P|H2|H3|H4)$/.test(b.tagName)||b.textContent.replace(/​/g,'').trim()||b.querySelector('img,svg'))return;
    b.classList.add('ed-ph');b.setAttribute('data-ph',b.tagName==='P'?U.ph:U.phH);phEl=b}

  /* ── Kopfleiste und Formatleiste ── */
  function tbtn(name,title,fn,cls){var b=el('button','ed-b'+(cls?' '+cls:''),ic(name));b.type='button';b.title=title;b.setAttribute('aria-label',title);
    b.addEventListener('mousedown',function(e){e.preventDefault()});b.addEventListener('click',function(){if(E.src)return;fn(b)});return b}
  function sepEl(){return el('span','ed-sep')}
  function buildBar(p){
    bar=el('div','ed-bar');bar.setAttribute('role','region');bar.setAttribute('aria-label',U.edit);
    var head=el('div','ed-head','<div class="ed-doc"><span class="ed-kicker">'+ic('edit')+U.edit+'</span><b id="edDocTitle"></b></div>'+
      '<span class="ed-chip" id="edStatus" aria-live="polite"></span><span class="ed-words" id="edWords"></span>'+
      '<div class="ed-acts"><button type="button" class="ed-b" id="edMore" aria-haspopup="menu" title="'+U.more+'" aria-label="'+U.more+'">'+ic('more')+'</button>'+
      '<button type="button" class="btn btn--secondary" id="edCancel">'+T.cancel+'</button><button type="button" class="btn btn--primary" id="edSave" disabled>'+T.publish+'</button></div>');
    metaTitle=head.querySelector('#edDocTitle');
    var tl=el('div','ed-tools');tl.setAttribute('role','toolbar');tl.setAttribute('aria-label','Format');
    var st=el('select','ed-sel');st.id='edBlock';st.title=U.style;st.setAttribute('aria-label',U.style);
    [['p','Text'],['h2','Überschrift 2'],['h3','Überschrift 3'],['h4','Überschrift 4'],['blockquote','Zitat'],['pre','Code']].forEach(function(o){var op=el('option');op.value=o[0];op.textContent=o[1];st.appendChild(op)});
    st.addEventListener('mousedown',saveSel);st.onchange=function(){restoreSel();exec('formatBlock','<'+st.value+'>')};
    var ins=el('button','ed-b txt ed-ins',ic('plus')+'<span>'+U.insert+'</span>'+ic('chev'));ins.type='button';ins.setAttribute('aria-haspopup','listbox');ins.title=U.insert+' (/)';
    ins.addEventListener('mousedown',function(e){e.preventDefault();saveSel()});
    ins.onclick=function(){if(E.src)return;if(!menu.hidden&&!M.slash){closeMenu();return}var r=ins.getBoundingClientRect();openMenu(ITEMS,r.left,r.bottom+4,{title:U.insert})};
    tl.append(tbtn('undo','Rückgängig ('+U.ctrl+'+Z)',function(){exec('undo')}),tbtn('redo','Wiederholen ('+U.ctrl+'+Umschalt+Z)',function(){exec('redo')}),sepEl(),st,sepEl(),
      tbtn('bold','Fett ('+U.ctrl+'+B)',function(){exec('bold')},'cmd-bold'),tbtn('italic','Kursiv ('+U.ctrl+'+I)',function(){exec('italic')},'cmd-italic'),
      tbtn('under','Unterstrichen ('+U.ctrl+'+U)',function(){exec('underline')},'cmd-underline'),tbtn('strike','Durchgestrichen',function(){exec('strikeThrough')},'cmd-strikeThrough'),
      tbtn('code','Code im Text',inlineCode),tbtn('link','Link ('+U.ctrl+'+K)',function(){linkDialog()}),sepEl(),
      tbtn('ul','Aufzählung',function(){exec('insertUnorderedList')},'cmd-insertUnorderedList'),tbtn('ol','Nummerierte Liste',function(){exec('insertOrderedList')},'cmd-insertOrderedList'),sepEl(),
      ins,sepEl(),tbtn('clear','Formatierung entfernen',function(){exec('removeFormat');exec('unlink')}));
    var srcBack=el('button','ed-b txt ed-srcback',ic('source')+'<span>'+U.htmlBack+'</span>');srcBack.type='button';srcBack.hidden=true;srcBack.onclick=toggleSource;tl.appendChild(srcBack);
    bar.append(head,tl);
    head.querySelector('#edSave').onclick=publishDialog;head.querySelector('#edCancel').onclick=cancel;
    var more=head.querySelector('#edMore');more.addEventListener('mousedown',function(e){e.preventDefault();saveSel()});
    more.onclick=function(){if(!menu.hidden&&!M.slash){closeMenu();return}var r=more.getBoundingClientRect(),items=[
      {t:U.settings,d:T.group+' und '+T.level,i:ic('gear'),run:settingsDialog,keepFocus:true},
      {t:U.html,d:'Für Fortgeschrittene',i:ic('source'),run:toggleSource,keepFocus:true},
      {t:U.keys,d:U.ctrl+' + /',i:ic('keys'),run:showKeys,keepFocus:true}];
      if(E.slug!=='start')items.push({t:U.delete,d:'Der Verlauf bleibt erhalten',i:ic('trash'),run:delPage,danger:true,keepFocus:true});
      openMenu(items,r.right-320,r.bottom+4,{})};
    return bar}
  function updateTitle(){if(!metaTitle||!E.art)return;var h=E.art.querySelector('h1');metaTitle.textContent=(h&&h.textContent.trim())||A.byId[E.slug].dataset.title}
  function words(){var n=(E.art.textContent||'').trim().split(/\s+/).filter(Boolean).length,w=D.getElementById('edWords');if(w)w.textContent=f(U.words,{n:n.toLocaleString('de-DE')})}
  function status(kind,txt){var s=D.getElementById('edStatus');if(!s)return;s.className='ed-chip '+kind;s.textContent=txt}
  function changed(){if(!E.slug)return;E.dirty=true;var sb=D.getElementById('edSave');if(sb)sb.disabled=false;status('dirty',U.unsaved);updateTitle();
    clearTimeout(E.draftT);E.draftT=setTimeout(function(){saveDraft();status('draft',f(U.draftAt,{t:A.fmt(new Date().toISOString()).split(', ')[1]}));words()},700)}
  function saveDraft(){sset(dkey(E.slug),{html:serialize(),base:E.base,ts:new Date().toISOString(),group:E.group,level:E.level})}
  function saveSel(){var s=sel();if(s.rangeCount&&inArt(s.anchorNode))E.range=s.getRangeAt(0).cloneRange()}
  function restoreSel(){if(!E.range)return;E.art.focus();var s=sel();s.removeAllRanges();s.addRange(E.range)}
  function placeCaret(node,start){E.art.focus();var r=D.createRange();r.selectNodeContents(node);r.collapse(!!start);var s=sel();s.removeAllRanges();s.addRange(r)}

  /* ── Bearbeiten starten und beenden ── */
  function startEdit(slug){
    if(E.slug){if(E.slug!==slug)toast(T.leave,true);return}
    if(preview)closePreview();
    var p=A.byId[slug];if(!p)return;if(A.current()!==p)A.show(slug);
    api('GET','/pages/'+encodeURIComponent(slug)).then(function(r){
      if(!r.ok){toast(r.data.message||T.network,true);return}
      E.slug=slug;E.art=p;E.base=r.data.version;E.dirty=false;E.src=false;E.group=r.data.group;E.level=(r.data.attrs||{}).level||'';
      E.frag=D.createDocumentFragment();while(p.firstChild)E.frag.appendChild(p.firstChild);
      p.innerHTML=r.data.html;p.dataset.version=r.data.version;prepare();
      p.contentEditable='true';p.spellcheck=true;p.setAttribute('aria-label','Inhalt der Seite');try{D.execCommand('defaultParagraphSeparator',false,'p')}catch(e){}p.classList.add('ed-on');D.body.classList.add('ed-mode');
      var main=D.getElementById('main');main.insertBefore(buildBar(p),main.firstChild);updateTitle();words();status('clean',U.clean);
      var dr=sget(dkey(slug));
      if(dr&&dr.base===E.base&&dr.html){var bn=el('div','ed-banner ed-draft','<p>'+esc(f(T.draftFound,{d:A.fmt(dr.ts)}))+'</p><button type="button" class="by-btn by-edit">'+T.useDraft+'</button><button type="button" class="by-btn">'+T.dropDraft+'</button>');
        bn.setAttribute('contenteditable','false');p.prepend(bn);var bs=bn.querySelectorAll('button');
        bs[0].onclick=function(){bn.remove();p.innerHTML=dr.html;prepare();if(dr.group)E.group=dr.group;if(dr.level!==undefined)E.level=dr.level;changed()};
        bs[1].onclick=function(){bn.remove();sset(dkey(slug),null)}}
      else if(dr)sset(dkey(slug),null);
      scrollTo(0,0);var h1=p.querySelector('h1');placeCaret(h1||p,false)})}
  function prepare(){E.art.querySelectorAll('svg').forEach(function(s){if(!s.closest('[contenteditable="false"]'))s.setAttribute('contenteditable','false')});
    E.art.querySelectorAll('.copy').forEach(function(b){b.setAttribute('contenteditable','false')});
    E.art.querySelectorAll('[style]').forEach(function(x){E.origStyle.set(x,x.getAttribute('style'))})}
  function stop(){if(!E.art)return;var p=E.art;p.contentEditable='false';p.removeAttribute('contenteditable');p.removeAttribute('aria-label');p.classList.remove('ed-on');D.body.classList.remove('ed-mode');
    if(bar)bar.remove();bar=null;metaTitle=null;closeMenu();hideFloats();selImg=null;clearTimeout(E.draftT);E.slug=null;E.dirty=false;E.src=false;return p}
  function restoreOriginal(noShow){var p=stop();if(!p)return;p.innerHTML='';p.appendChild(E.frag);E.frag=null;E.art=null;A.refreshMeta(p);if(!noShow)A.show(p.dataset.page)}
  function cancel(){if(!E.dirty){sset(dkey(E.slug),null);return restoreOriginal()}
    dialog({title:T.discardTitle,body:T.discardBody,confirm:T.discard,danger:true}).then(function(v){if(v){sset(dkey(E.slug),null);restoreOriginal()}})}

  // HTML zum Speichern: Laufzeit-Zusätze und Editor-Spuren entfernen
  var JUNK=/^(font(-[a-z]+)?|color|background(-color)?|line-height|letter-spacing|word-spacing|text-(decoration[a-z-]*|transform|indent|align)|white-space|display|vertical-align|caret-color|outline|orphans|widows|-webkit-[a-z-]+)$/;
  function cleanStyles(){E.art.querySelectorAll('[style]').forEach(function(x){var st=x.getAttribute('style');if(E.origStyle.get(x)===st||x.closest('svg')||/var\(/.test(st))return;
    var props=st.split(';').map(function(d){return d.split(':')[0].trim().toLowerCase()}).filter(Boolean);if(props.every(function(pr){return JUNK.test(pr)}))x.removeAttribute('style')})}
  function serialize(){if(E.src){var ta=E.art.querySelector('.ed-src');return ta?ta.value:''}
    cleanStyles();var c=E.art.cloneNode(true);
    c.querySelectorAll('[data-runtime],.dx-pagemeta,.dx-byline,.anc,.ed-banner,.ed-uploading').forEach(function(x){x.remove()});
    c.querySelectorAll('[contenteditable]').forEach(function(x){x.removeAttribute('contenteditable')});
    c.querySelectorAll('[data-ph]').forEach(function(x){x.removeAttribute('data-ph')});
    c.querySelectorAll('.ed-ph,.ed-sel-img,.reveal.run').forEach(function(x){x.classList.remove('ed-ph','ed-sel-img','run');if(!x.className)x.removeAttribute('class')});
    c.querySelectorAll('.code').forEach(function(cd){var b=cd.querySelector('.copy');if(!b)return;var k=cd.cloneNode(true);k.querySelectorAll('.copy,.p,.c').forEach(function(x){x.remove()});
      k.querySelectorAll('br').forEach(function(x){x.replaceWith('\n')});b.setAttribute('data-copy',k.textContent.replace(/ /g,' ').replace(/[ \t]+\n/g,'\n').trim());b.setAttribute('type','button');b.textContent='Kopieren'});
    c.querySelectorAll('h2[id]').forEach(function(h){if(h.id.indexOf(E.slug+'--')===0)h.removeAttribute('id')});
    c.querySelectorAll('span:not([class]):not([style]):not([id])').forEach(function(s){s.replaceWith.apply(s,[].slice.call(s.childNodes))});
    return c.innerHTML.replace(/^\s+|\s+$/g,'')}

  /* ── Veröffentlichen, Einstellungen, Löschen, Tastenkürzel ── */
  function publishDialog(){if(E.busy||!E.dirty)return;var html=serialize(),tmp=el('div','',html),h1=tmp.querySelector('h1');
    if(!A.byId[E.slug].dataset.landing&&(!h1||!h1.textContent.trim())){toast(T.noTitle,true);return}
    dialog({title:U.pubTitle,body:U.pubBody,confirm:T.publish,
      fields:'<label>'+U.pubNote+' <small>'+U.pubNoteHint+'</small><textarea name="note" maxlength="300" placeholder="'+esc(T.notePh)+'"></textarea></label><p class="ed-dlg-meta">'+esc(f(U.pubVersion,{v:E.base+1}))+' · '+esc(D.getElementById('edWords').textContent)+'</p>'}).then(function(v){if(v)save(html,v.note||'')})}
  function save(html,note){E.busy=true;var sb=D.getElementById('edSave');sb.disabled=true;sb.textContent=T.publishing;
    var body={base_version:E.base,html:html,level:E.level,note:note};if(!A.byId[E.slug].dataset.landing)body.group=E.group;
    api('PUT','/pages/'+encodeURIComponent(E.slug),body).then(function(r){E.busy=false;sb.textContent=T.publish;
      if(r.ok){sset(dkey(E.slug),null);E.dirty=false;flash(f(T.published,{t:r.data.title,v:r.data.version}));location.hash=r.data.slug;reload();return}
      sb.disabled=false;
      if(r.status===409){dialog({title:T.confTitle,body:f(T.confBody,{a:r.data.updated_by,v:r.data.current_version}),confirm:T.confBtn,danger:true}).then(function(v){if(v){E.base=r.data.current_version;save(html,note)}});return}
      toast(r.data.message||T.network,true)})}
  function settingsDialog(){
    dialog({title:U.settingsTitle,confirm:U.apply,fields:(A.byId[E.slug].dataset.landing?'':'<label>'+T.group+' <small>Bestimmt, unter welcher Überschrift die Seite in der Navigation steht.</small><input name="group" type="text" list="edGroups" maxlength="60" required value="'+esc(E.group)+'" autocomplete="off"></label>'+groupsList())+
      '<label>'+T.level+' <small>Erscheint über dem Text, z. B. „Einsteiger“.</small>'+levelSelect('level',E.level)+'</label>'}).then(function(v){if(!v)return;
      var ng=v.group!==undefined?v.group.trim():E.group;if(ng!==E.group||v.level!==E.level){E.group=ng||E.group;E.level=v.level;changed()}})}
  function delPage(){var t=A.byId[E.slug].dataset.title,slug=E.slug;dialog({title:T.delTitle,body:f(T.delBody,{t:t}),confirm:T.delBtn,danger:true}).then(function(v){if(!v)return;
    api('DELETE','/pages/'+encodeURIComponent(slug)).then(function(r){if(!r.ok){toast(r.data.message,true);return}sset(dkey(slug),null);E.dirty=false;flash(f(T.deleted,{t:t}));location.hash='aenderungen';reload()})})}
  var keysPop=el('div','ed-keys');keysPop.hidden=true;keysPop.setAttribute('role','dialog');keysPop.setAttribute('aria-labelledby','edKeysT');D.body.appendChild(keysPop);
  function showKeys(){var c=U.ctrl,rows=[[c+' + S',T.publish+' …'],[c+' + B / I / U','Fett / Kursiv / Unterstrichen'],[c+' + K','Link'],[c+' + Z','Rückgängig'],['/','Befehle: Überschrift, Bild, Tabelle …'],
      ['## + Leertaste','Überschrift 2 (### für 3, #### für 4)'],['- + Leertaste','Aufzählung'],['1. + Leertaste','Nummerierte Liste'],['> + Leertaste','Zitat'],['``` + Leertaste','Codeblock'],['--- + Enter','Trennlinie'],['E','Seite bearbeiten (beim Lesen)'],['Esc','Menü schließen']];
    keysPop.innerHTML='<div class="ed-keys-h"><h2 id="edKeysT">'+U.keysTitle+'</h2><button type="button" class="dx-icon" aria-label="'+T.close+'">'+ic('x')+'</button></div><dl>'+rows.map(function(r){return '<dt><kbd>'+esc(r[0])+'</kbd></dt><dd>'+esc(r[1])+'</dd>'}).join('')+'</dl>';
    keysPop.hidden=false;var x=keysPop.querySelector('button');x.onclick=function(){keysPop.hidden=true;if(E.art)E.art.focus()};x.focus()}

  /* ── Link ── */
  function pageOptions(){return Object.keys(A.byId).map(function(k){return '<option value="#'+esc(k)+'">'+esc(A.byId[k].dataset.title)+'</option>'}).join('')}
  function linkDialog(a){saveSel();var s=sel(),n=s.anchorNode&&(s.anchorNode.nodeType===1?s.anchorNode:s.anchorNode.parentNode);a=a||(n&&n.closest('a'));if(a&&!E.art.contains(a))a=null;
    var text=a?a.textContent:s.toString();
    dialog({title:a?'Link bearbeiten':T.linkTitle,confirm:a?U.apply:T.insert,fields:'<label>'+T.linkUrl+' <small>'+T.linkHint+'</small><input name="u" type="text" list="edPages" value="'+esc(a?a.getAttribute('href'):'')+'" required autocomplete="off" placeholder="#seite oder https://…"></label><datalist id="edPages">'+pageOptions()+'</datalist><label>'+T.linkText+'<input name="t" type="text" value="'+esc(text)+'"></label><label class="chk"><input type="checkbox" name="n"'+(a&&a.target==='_blank'?' checked':'')+'>'+T.linkNew+'</label>',
      validate:function(v){var u=v.u.trim();return /^(#|\/|https?:\/\/|mailto:)/i.test(u)?'':T.linkHint}}).then(function(v){if(!v)return;restoreSel();
      var u=v.u.trim(),t=v.t.trim()||(u.charAt(0)==='#'&&A.byId[u.slice(1)]?A.byId[u.slice(1)].dataset.title:u),h='<a href="'+esc(u)+'"'+(v.n?' target="_blank" rel="noopener noreferrer"':'')+'>'+esc(t)+'</a>';
      if(a){a.outerHTML=h;changed()}else exec('insertHTML',h)})}

  /* ── HTML-Ansicht ── */
  function toggleSource(){var tl=bar.querySelector('.ed-tools'),back=tl.querySelector('.ed-srcback');
    if(!E.src){var h=serialize();E.src=true;E.art.contentEditable='false';E.art.innerHTML='';var ta=el('textarea','ed-src');ta.value=pretty(h);ta.spellcheck=false;ta.setAttribute('aria-label','HTML der Seite');ta.oninput=changed;E.art.appendChild(ta);ta.focus()}
    else{var v=E.art.querySelector('.ed-src').value;E.src=false;E.art.innerHTML=v;prepare();E.art.contentEditable='true';placeCaret(E.art.querySelector('h1')||E.art,false)}
    tl.classList.toggle('src',E.src);back.hidden=!E.src;hideFloats()}
  function pretty(h){return h.replace(/>\s*<(\/?(?:p|h[1-6]|div|ul|ol|li|table|thead|tbody|tr|figure|figcaption|blockquote|pre|details|summary|section|hr|dl|dt|dd)\b)/g,'>\n<$1')}

  /* ── Dateien ── */
  var picker=el('input');picker.type='file';picker.hidden=true;D.body.appendChild(picker);
  function pick(accept){saveSel();picker.accept=accept;picker.multiple=accept!=='application/pdf';picker.value='';picker.onchange=function(){restoreSel();[].slice.call(picker.files).forEach(upload)};picker.click()}
  function upload(file){
    if(IMG.indexOf(file.type)<0&&file.type!=='application/pdf'){toast(T.badType,true);return}
    if(file.size>MAX){toast(f(T.tooBig,{mb:Math.round(MAX/1048576)}),true);return}
    var id='up'+Math.random().toString(36).slice(2);
    exec('insertHTML','<div class="ed-uploading" id="'+id+'" contenteditable="false">'+esc(file.name)+' – '+f(T.uploading,{n:0})+'<span><i></i></span></div><p><br></p>');
    var ph=D.getElementById(id);if(!ph){ph=el('div','ed-uploading',esc(file.name)+'<span><i></i></span>');ph.id=id;E.art.appendChild(ph)}
    var x=new XMLHttpRequest();x.open('POST',B.api+'/assets');x.setRequestHeader('X-CSRF-Token',B.csrf||'');x.setRequestHeader('Content-Type',file.type);
    x.upload.onprogress=function(e){if(e.lengthComputable&&ph){var n=Math.round(e.loaded/e.total*100);ph.firstChild.nodeValue=file.name+' – '+f(T.uploading,{n:n});ph.querySelector('i').style.width=n+'%'}};
    x.onload=function(){var d={};try{d=JSON.parse(x.responseText)}catch(e){}if(x.status!==201||!d.url){if(ph)ph.remove();toast(d.message||T.uploadFail,true);return}
      var name=file.name.replace(/\.[^.]+$/,'').replace(/[-_]+/g,' ');
      if(file.type==='application/pdf'){var a=el('a','dx-file',ic('file')+esc(file.name));a.href=d.url;ph.replaceWith(a);changed();return}
      var fig=el('figure','dx-img img-l','<img src="'+esc(d.url)+'" alt="'+esc(name)+'" loading="lazy"><figcaption></figcaption>');ph.replaceWith(fig);changed();
      var img=fig.querySelector('img');img.onload=function(){if(img.naturalWidth<480){fig.classList.remove('img-l');fig.classList.add(img.naturalWidth<300?'img-s':'img-m')}};altDialog(img)};
    x.onerror=function(){if(ph)ph.remove();toast(T.network,true)};x.send(file)}
  function altDialog(img){var fig=img.closest('figure'),cap=fig&&fig.querySelector('figcaption');
    dialog({title:T.imgTitle,confirm:T.save,fields:'<label>'+T.alt+' <small>'+T.altHint+'</small><input name="a" type="text" maxlength="200" value="'+esc(img.alt)+'"></label>'+(cap?'<label>'+T.caption+'<input name="c" type="text" maxlength="300" value="'+esc(cap.textContent)+'"></label>':'')}).then(function(v){if(!v)return;
      img.alt=v.a.trim();if(cap)cap.textContent=(v.c||'').trim();changed();refreshFloats()})}

  // Einfügen aus der Zwischenablage: Dateien hochladen, fremdes HTML vereinfachen
  var KEEP={P:1,H2:1,H3:1,H4:1,UL:1,OL:1,LI:1,A:1,B:1,STRONG:1,I:1,EM:1,U:1,S:1,CODE:1,PRE:1,BLOCKQUOTE:1,BR:1,TABLE:1,THEAD:1,TBODY:1,TR:1,TH:1,TD:1,HR:1,KBD:1};
  function simplify(html){var box=new DOMParser().parseFromString(html,'text/html').body;box.querySelectorAll('script,style,meta,link,title,img,svg,iframe,object').forEach(function(x){x.remove()});
    (function walk(n){[].slice.call(n.childNodes).forEach(function(c){if(c.nodeType===8){c.remove();return}if(c.nodeType!==1)return;walk(c);
      if(c.tagName==='H1'){var h=D.createElement('h2');h.innerHTML=c.innerHTML;c.replaceWith(h);return}
      if(!KEEP[c.tagName]){if(/^(DIV|SECTION|ARTICLE)$/.test(c.tagName)){var p=D.createElement('p');p.innerHTML=c.innerHTML;c.replaceWith(p)}else c.replaceWith.apply(c,[].slice.call(c.childNodes));return}
      [].slice.call(c.attributes).forEach(function(a){if(!(c.tagName==='A'&&a.name==='href'))c.removeAttribute(a.name)})})})(box);
    box.querySelectorAll('table').forEach(function(t){if(!t.parentNode.classList||!t.parentNode.classList.contains('tbl-wrap')){var w=el('div','tbl-wrap');t.replaceWith(w);w.appendChild(t)}});
    box.querySelectorAll('p,li,h2,h3,h4').forEach(function(x){if(!x.textContent.trim()&&!x.querySelector('br'))x.remove()});
    return box.innerHTML}
  D.addEventListener('paste',function(e){if(!E.slug||E.src||!inArt(e.target))return;var cd=e.clipboardData;if(!cd)return;
    var files=[].slice.call(cd.files||[]).filter(function(x){return IMG.indexOf(x.type)>-1||x.type==='application/pdf'});
    if(files.length){e.preventDefault();files.forEach(upload);return}
    var t=cd.getData('text/plain'),h=cd.getData('text/html');
    if(t&&/^(https?:\/\/|#)\S+$/.test(t.trim())&&!sel().isCollapsed){e.preventDefault();exec('createLink',t.trim());return}
    if(h&&!e.target.closest('pre,.code')){e.preventDefault();exec('insertHTML',simplify(h));return}
    if(t){e.preventDefault();exec('insertText',t)}},true);
  var drop=el('div','ed-drop','<b>'+ic('image')+T.dropHere+'</b>'),dragN=0;D.body.appendChild(drop);
  function hasFiles(e){return e.dataTransfer&&[].indexOf.call(e.dataTransfer.types,'Files')>-1}
  D.addEventListener('dragenter',function(e){if(E.slug&&!E.src&&hasFiles(e)){dragN++;drop.classList.add('on')}});
  D.addEventListener('dragleave',function(){if(--dragN<=0){dragN=0;drop.classList.remove('on')}});
  D.addEventListener('dragover',function(e){if(E.slug&&hasFiles(e))e.preventDefault()});
  D.addEventListener('drop',function(e){dragN=0;drop.classList.remove('on');if(!E.slug||E.src||!e.dataTransfer||!e.dataTransfer.files.length)return;e.preventDefault();
    var r=D.caretRangeFromPoint?D.caretRangeFromPoint(e.clientX,e.clientY):null;if(!r&&D.caretPositionFromPoint){var cp=D.caretPositionFromPoint(e.clientX,e.clientY);if(cp){r=D.createRange();r.setStart(cp.offsetNode,cp.offset)}}
    if(r&&E.art.contains(r.startContainer)){var s=sel();s.removeAllRanges();s.addRange(r)}else placeCaret(E.art,false);
    [].slice.call(e.dataTransfer.files).forEach(upload)});

  /* ── Tastatur ── */
  var MD={'#':'h2','##':'h2','###':'h3','####':'h4','-':'ul','*':'ul','1.':'ol','>':'blockquote','```':'pre'};
  function markdown(e){var s=sel();if(!s.isCollapsed||!s.rangeCount)return false;var p=curBlock();if(!p||!(p.tagName==='P'||p.tagName==='DIV'&&!p.className)||p.parentNode!==E.art&&!p.parentNode.closest('.callout'))return false;
    var r=D.createRange();r.selectNodeContents(p);r.setEnd(s.anchorNode,s.anchorOffset);var before=r.toString().replace(/ /g,' ');
    if(e.key===' '&&MD[before]!==undefined&&before===p.textContent.replace(/ /g,' ')){e.preventDefault();var tag=MD[before];p.innerHTML='<br>';placeCaret(p,true);
      if(tag==='ul')exec('insertUnorderedList');else if(tag==='ol')exec('insertOrderedList');else exec('formatBlock','<'+tag+'>');return true}
    if(e.key==='Enter'&&before==='---'&&p.textContent==='---'){e.preventDefault();p.innerHTML='<br>';placeCaret(p,true);exec('insertHorizontalRule');return true}
    return false}
  D.addEventListener('keydown',function(e){if(!E.slug)return;var k=e.key,mod=e.ctrlKey||e.metaKey;
    if(!menu.hidden){if(k==='ArrowDown'||k==='ArrowUp'){e.preventDefault();var n=M.items.length;if(n){M.sel=(M.sel+(k==='ArrowDown'?1:-1)+n)%n;mark()}return}
      if(k==='Enter'||k==='Tab'){if(M.items.length){e.preventDefault();e.stopPropagation();pickMenu(M.sel)}else closeMenu();return}
      if(k==='Escape'){e.preventDefault();e.stopPropagation();closeMenu();return}}
    if(k==='Escape'&&!keysPop.hidden){keysPop.hidden=true;return}
    if(mod&&k.toLowerCase()==='s'){e.preventDefault();e.stopPropagation();publishDialog();return}
    if(mod&&k==='/'){e.preventDefault();e.stopPropagation();showKeys();return}
    if(E.src||!inArt(e.target))return;
    if(mod&&k.toLowerCase()==='k'){e.preventDefault();e.stopPropagation();linkDialog();return}
    if(!mod&&(k===' '||k==='Enter')&&markdown(e))return;
    if(k==='Tab'){var b=curBlock();if(b&&b.closest('pre')){e.preventDefault();D.execCommand('insertText',false,'  ')}}
  },true);
  D.addEventListener('input',function(e){if(E.slug&&inArt(e.target)){changed();slashCheck()}});
  D.addEventListener('selectionchange',function(){if(!E.slug||E.src||!bar)return;var s=sel();
    if(s.rangeCount&&inArt(s.anchorNode)){
      var an=s.anchorNode.nodeType===1?s.anchorNode:s.anchorNode.parentNode,inHead=!!an.closest('h1,h2,h3,h4,h5,th,.callout h5'),inLink=!!an.closest('a');
      ['bold','italic','underline','strikeThrough','insertUnorderedList','insertOrderedList'].forEach(function(c){var b=bar.querySelector('.cmd-'+c);if(!b)return;var on=D.queryCommandState(c);
        if(c==='bold'&&inHead)on=!!an.closest('b,strong');if(c==='underline'&&inLink)on=!!an.closest('u');b.setAttribute('aria-pressed',String(on))});
      var blk=curBlock(),st=D.getElementById('edBlock'),t=blk&&blk.closest('h2,h3,h4,blockquote,pre');if(st)st.value=t&&E.art.contains(t)?t.tagName.toLowerCase():'p';
      placeholder();if(M.slash)slashCheck()}
    refreshFloats()});
  D.addEventListener('click',function(e){if(!E.slug||E.src)return;
    if(!e.target.closest('.ed-menu')&&!e.target.closest('.ed-ins')&&!e.target.closest('#edMore'))closeMenu();
    if(!keysPop.hidden&&!e.target.closest('.ed-keys'))keysPop.hidden=true;
    var im=e.target.closest('img');D.querySelectorAll('.ed-sel-img').forEach(function(x){x.classList.remove('ed-sel-img')});
    if(im&&E.art.contains(im)){selImg=im;im.classList.add('ed-sel-img')}else if(!e.target.closest('.ed-imgbar'))selImg=null;
    var a=e.target.closest('a');if(a&&E.art.contains(a))e.preventDefault();refreshFloats()},true);
  addEventListener('scroll',function(){if(E.slug){refreshFloats();if(!menu.hidden&&!M.slash)closeMenu()}},{passive:true});
  addEventListener('resize',function(){if(E.slug)refreshFloats()});
  addEventListener('beforeunload',function(e){if(E.slug&&E.dirty){e.preventDefault();e.returnValue=''}});
  addEventListener('hashchange',function(){if(!E.slug)return;setTimeout(function(){if(A.current()!==E.art){if(E.dirty){saveDraft();toast(T.leave)}restoreOriginal(true)}},0)});
})();
