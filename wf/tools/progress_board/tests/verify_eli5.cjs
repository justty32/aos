// Verify ELI5 updates preserve surrounding controls and per-item freshness.
const fs = require('fs'), vm = require('vm'), assert = require('assert'), path = require('path');
class Node {
  constructor(tag) { this.tagName=tag; this.children=[];this.dataset={};this.attributes={};this.listeners={};this.text=''; }
  set textContent(v) {this.text=String(v);this.children=[];}
  get textContent() {return this.text+this.children.map(c=>c.textContent).join('');}
  append(...nodes) {for(const n of nodes){n.parentNode=this;this.children.push(n);}}
  setAttribute(k,v){this.attributes[k]=v;}
  insertBefore(n,b){n.parentNode=this;const i=this.children.indexOf(b);if(i<0)this.children.push(n);else this.children.splice(i,0,n);}
  remove(){const a=this.parentNode.children;a.splice(a.indexOf(this),1);}
  replaceChildren(...ns){this.children=[];this.text='';this.append(...ns);}
  addEventListener(k,f){this.listeners[k]=f;}
  get firstChild(){return this.children[0];}
  get nextSibling(){const a=this.parentNode.children;return a[a.indexOf(this)+1]||null;}
  querySelector(s){return this.querySelectorAll(s)[0]||null;}
  querySelectorAll(s){const match=n=>s.startsWith('.')?n.className?.split(' ').includes(s.slice(1)):n.tagName===s;return this.children.flatMap(n=>[...(match(n)?[n]:[]),...n.querySelectorAll(s)]);}
}
global.window={scrollX:10,scrollY:80,scrollTo(x,y){assert.equal(x,10);assert.equal(y,80);}};
global.document={createElement:t=>new Node(t),createElementNS:(_,t)=>new Node(t),createTextNode:t=>{const n=new Node('#text');n.textContent=t;return n;}};
global.location={protocol:'http:'};
for(const file of ['eli5','asks'])vm.runInThisContext(fs.readFileSync(path.join(__dirname, '..', 'web', `${file}.js`),'utf8'));
const host=new Node('section'),draft=new Node('textarea'),fold=new Node('details');draft.value='Keep my draft';fold.open=true;host.append(draft,fold);
const set=window.AosEli5.set, item={text:'Explanation',updated_at:'2026-11-07T10:12:00+08:00',stale:false};
set(host,'test',item,draft);const box=host.firstChild;assert.match(box.textContent,/白話更新於 \d\d:\d\d/);assert.equal(box.children[2].children[1].hidden,true);
set(host,'test',{...item,stale:true});assert.strictEqual(host.firstChild,box);assert.equal(box.children[2].children[1].hidden,false);
set(host,'test',{...item,updated_at:'2026-11-07T10:13:00+08:00'});assert.strictEqual(host.firstChild,box);assert.match(box.children[2].textContent,/13/);
set(host,'test',{text:'Authored',provided:true,stale:true});assert.match(box.textContent,/各線自己寫的白話/);assert.equal(box.children[2].children[1].hidden,true);assert.equal(draft.value,'Keep my draft');assert.equal(fold.open,true);
set(host,'test',{text:''});assert.equal(host.children.length,2);
const el=(t,c,v)=>{const n=new Node(t);n.className=c||'';if(v!=null)n.textContent=v;return n;};
const asks=window.AOSAsks({el,heading(){},details(p,t){const d=el('details');p.append(d);return d;},chip:t=>el('span','',t),link:t=>el('a','',t),poll(){}});
const question={id:'q',text:'Question',line:'line',options:[],eli5:item};asks.update({asks:[question]});const card=asks.panel.querySelector('.ask-card'),control=card.querySelector('textarea');control.value='Unsent draft';control.listeners.input();
asks.update({asks:[{...question,eli5:{...item,text:'New explanation',stale:true}}]});assert.strictEqual(asks.panel.querySelector('.ask-card'),card);assert.strictEqual(card.querySelector('textarea'),control);assert.equal(control.value,'Unsent draft');assert.match(card.textContent,/New explanation/);
set(host,'test',item,draft);const recreated=host.firstChild;assert.notStrictEqual(recreated,box);
host.replaceChildren(draft,fold);recreated.parentNode=null;set(host,'test',item,draft);assert.equal(host.firstChild.dataset.eli5,'test');assert.notStrictEqual(host.firstChild,recreated);
set(host,'test',{text:'No date',updated_at:'invalid'});assert.equal(host.firstChild.children[2].children[0].textContent,'');
set(host,'test',{...item,updated_at:new Date(2026,10,7,0,3).toISOString()});assert.equal(host.firstChild.children[2].children[0].textContent,'白話更新於 00:03');
console.log('ELI5 DOM checks passed: timestamps, stale, provided, empty removal, control and fold identity, ask draft preservation.');
