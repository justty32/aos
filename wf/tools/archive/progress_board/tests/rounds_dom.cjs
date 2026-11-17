// Provide a dependency-free DOM fixture for executing the actual rounds page script.
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
class Node {
  constructor(tag) { this.tagName=tag.toUpperCase(); this.children=[]; this.attributes={}; this.dataset=new Proxy({}, {set:(o,k,v)=>{o[k]=String(v);this.attributes['data-'+k.replace(/[A-Z]/g,c=>'-'+c.toLowerCase())]=String(v);return true;}}); this.listeners={}; this.text=''; this.style={}; this.open=false; }
  set textContent(v) { this.replaceChildren(); this.text=String(v); }
  get textContent() { return this.text+this.children.map(n=>n.textContent).join(''); }
  get className() { return this.getAttribute('class')||''; }
  set className(v) { this.setAttribute('class',v); }
  get id() { return this.getAttribute('id')||''; }
  set id(v) { this.setAttribute('id',v); }
  get classList() { const n=this; return {contains:c=>n.className.split(/\s+/).includes(c),add(...cs){n.className=[...new Set([...n.className.split(/\s+/).filter(Boolean),...cs])].join(' ');},remove(...cs){n.className=n.className.split(/\s+/).filter(c=>!cs.includes(c)).join(' ');}}; }
  setAttribute(k,v) { this.attributes[k]=String(v); if(k.startsWith('data-')) this.dataset[k.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]=String(v); }
  getAttribute(k) { return this.attributes[k]??null; }
  removeAttribute(k) { delete this.attributes[k]; }
  append(...ns) { for(let n of ns){if(typeof n==='string'){const t=new Node('#text');t.textContent=n;n=t;} n.remove();n.parentNode=this;this.children.push(n);} }
  appendChild(n) { this.append(n);return n; }
  replaceChildren(...ns) { this.text='';for(const n of this.children)n.parentNode=null;this.children=[];this.append(...ns); }
  remove() { if(this.parentNode){const a=this.parentNode.children;a.splice(a.indexOf(this),1);this.parentNode=null;} }
  replaceWith(n) { const p=this.parentNode,i=p.children.indexOf(this);n.remove();p.children[i]=n;n.parentNode=p;this.parentNode=null; }
  insertBefore(n,b) { const i=this.children.indexOf(b);if(i<0)this.append(n);else{n.remove();this.children.splice(i,0,n);n.parentNode=this;}return n; }
  get firstChild() {return this.children[0]||null;}
  get parentElement() {return this.parentNode;}
  get nextSibling() {const a=this.parentNode?.children||[];return a[a.indexOf(this)+1]||null;}
  addEventListener(k,f) { (this.listeners[k]??=[]).push(f); }
  click() {for(const f of this.listeners.click||[])f({target:this,preventDefault(){}});}
  matches(s) {
    const attrs=[...s.matchAll(/\[([^\]=]+)(?:=["']?([^\]"']*)["']?)?\]/g)];
    if(attrs.some(([,k,v])=>this.getAttribute(k)===null||(v!==undefined&&this.getAttribute(k)!==v)))return false;
    s=s.replace(/\[[^\]]*\]/g,'');
    const tag=s.match(/^[\w-]+/);if(tag&&this.tagName!==tag[0].toUpperCase())return false;
    if([...s.matchAll(/\.([\w-]+)/g)].some(([,c])=>!this.classList.contains(c)))return false;
    const id=s.match(/#([\w-]+)/);return !id||this.id===id[1];
  }
  querySelectorAll(s) {
    if(s.includes(','))return [...new Set(s.split(',').flatMap(x=>this.querySelectorAll(x.trim())))];
    const parts=s.trim().split(/\s+/),last=parts.pop();
    const descendants=this.children.flatMap(n=>[n,...n.querySelectorAll('*')]);
    return descendants.filter(n=>n.matches(last)&&parts.slice().reverse().every((p,i,a)=>{
      // Selectors here use descendant relationships; fixture does not emulate CSS rendering.
      let ancestor=i===0?n.parentNode:n._ancestor;while(ancestor&&!ancestor.matches(p))ancestor=ancestor.parentNode;n._ancestor=ancestor?.parentNode;return Boolean(ancestor);
    }));
  }
  querySelector(s) {return this.querySelectorAll(s)[0]||null;}
  closest(s) {for(let n=this;n;n=n.parentNode)if(n.matches(s))return n;return null;}
  scrollIntoView() {this.scrolled=true;}
}
function parse(html) {
  const root=new Node('document'),stack=[root];
  for(const token of html.match(/<!--[\s\S]*?-->|<[^>]+>|[^<]+/g)||[]) {
    if(token.startsWith('<!--')||token.startsWith('<!'))continue;
    if(token.startsWith('</')){stack.pop();continue;}
    if(token.startsWith('<')) {
      const tag=token.match(/^<([\w-]+)/)?.[1];if(!tag)continue;
      const n=new Node(tag);for(const [,k,a,b,c] of token.matchAll(/([\w:-]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/g))if(k!==tag)n.setAttribute(k,a??b??c??'');
      stack.at(-1).append(n);if(!['meta','link','br','hr','input','img'].includes(tag)&&!token.endsWith('/>'))stack.push(n);
    } else {const n=new Node('#text');n.textContent=token;stack.at(-1).append(n);}
  }
  return root;
}
async function boot(state,{protocol='http:',search='?line=alpha',hash=''}={}) {
  const web=path.join(__dirname,'..','web'),document=parse(fs.readFileSync(path.join(web,'rounds.html'),'utf8'));
  document.createElement=t=>new Node(t);document.createElementNS=(_,t)=>new Node(t);document.createTextNode=t=>{const n=new Node('#text');n.textContent=t;return n;};document.getElementById=id=>document.querySelector('#'+id);
  const intervals=[],listeners={},requests=[];let next=state;
  const location={protocol,search,hash,pathname:'/rounds.html',href:`${protocol}//localhost/rounds.html${search}${hash}`};
  const window={AOS_STATE:state,location,scrollX:13,scrollY:287,addEventListener(k,f){listeners[k]=f;},scrollTo(x,y){this.scrollX=x;this.scrollY=y;}};
  const context={window,document,location,URLSearchParams,URL,console,Date,Map,Set,Promise,encodeURIComponent,decodeURIComponent,setInterval(f,ms){intervals.push({f,ms});return intervals.length;},clearInterval(){},setTimeout(f){f();},fetch:async url=>{requests.push(url);return {ok:true,json:async()=>next};}};
  Object.assign(window,{setInterval:context.setInterval,fetch:context.fetch});
  vm.runInNewContext(fs.readFileSync(path.join(web,'rounds.js'),'utf8'),context,{filename:'rounds.js'});
  const flush=async()=>{for(let i=0;i<12;i++)await Promise.resolve();};await flush();
  return {document,window,location,intervals,requests,listeners,async poll(value){next=value;for(const {f} of intervals)await f();await flush();}};
}
module.exports={Node,boot};
