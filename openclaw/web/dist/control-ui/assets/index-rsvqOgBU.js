(function(){const t=document.createElement("link").relList;if(t&&t.supports&&t.supports("modulepreload"))return;for(const s of document.querySelectorAll('link[rel="modulepreload"]'))i(s);new MutationObserver(s=>{for(const a of s)if(a.type==="childList")for(const o of a.addedNodes)o.tagName==="LINK"&&o.rel==="modulepreload"&&i(o)}).observe(document,{childList:!0,subtree:!0});function n(s){const a={};return s.integrity&&(a.integrity=s.integrity),s.referrerPolicy&&(a.referrerPolicy=s.referrerPolicy),s.crossOrigin==="use-credentials"?a.credentials="include":s.crossOrigin==="anonymous"?a.credentials="omit":a.credentials="same-origin",a}function i(s){if(s.ep)return;s.ep=!0;const a=n(s);fetch(s.href,a)}})();const un=globalThis,Qi=un.ShadowRoot&&(un.ShadyCSS===void 0||un.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,Ji=Symbol(),oa=new WeakMap;let Eo=class{constructor(t,n,i){if(this._$cssResult$=!0,i!==Ji)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=n}get styleSheet(){let t=this.o;const n=this.t;if(Qi&&t===void 0){const i=n!==void 0&&n.length===1;i&&(t=oa.get(n)),t===void 0&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),i&&oa.set(n,t))}return t}toString(){return this.cssText}};const wr=e=>new Eo(typeof e=="string"?e:e+"",void 0,Ji),kr=(e,...t)=>{const n=e.length===1?e[0]:t.reduce((i,s,a)=>i+(o=>{if(o._$cssResult$===!0)return o.cssText;if(typeof o=="number")return o;throw Error("Value passed to 'css' function must be a 'css' function result: "+o+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(s)+e[a+1],e[0]);return new Eo(n,e,Ji)},Ar=(e,t)=>{if(Qi)e.adoptedStyleSheets=t.map(n=>n instanceof CSSStyleSheet?n:n.styleSheet);else for(const n of t){const i=document.createElement("style"),s=un.litNonce;s!==void 0&&i.setAttribute("nonce",s),i.textContent=n.cssText,e.appendChild(i)}},la=Qi?e=>e:e=>e instanceof CSSStyleSheet?(t=>{let n="";for(const i of t.cssRules)n+=i.cssText;return wr(n)})(e):e;const{is:xr,defineProperty:Sr,getOwnPropertyDescriptor:_r,getOwnPropertyNames:Cr,getOwnPropertySymbols:Er,getPrototypeOf:Tr}=Object,_n=globalThis,ra=_n.trustedTypes,Lr=ra?ra.emptyScript:"",Ir=_n.reactiveElementPolyfillSupport,Et=(e,t)=>e,vn={toAttribute(e,t){switch(t){case Boolean:e=e?Lr:null;break;case Object:case Array:e=e==null?e:JSON.stringify(e)}return e},fromAttribute(e,t){let n=e;switch(t){case Boolean:n=e!==null;break;case Number:n=e===null?null:Number(e);break;case Object:case Array:try{n=JSON.parse(e)}catch{n=null}}return n}},Zi=(e,t)=>!xr(e,t),ca={attribute:!0,type:String,converter:vn,reflect:!1,useDefault:!1,hasChanged:Zi};Symbol.metadata??=Symbol("metadata"),_n.litPropertyMetadata??=new WeakMap;let lt=class extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??=[]).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,n=ca){if(n.state&&(n.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t)&&((n=Object.create(n)).wrapped=!0),this.elementProperties.set(t,n),!n.noAccessor){const i=Symbol(),s=this.getPropertyDescriptor(t,i,n);s!==void 0&&Sr(this.prototype,t,s)}}static getPropertyDescriptor(t,n,i){const{get:s,set:a}=_r(this.prototype,t)??{get(){return this[n]},set(o){this[n]=o}};return{get:s,set(o){const r=s?.call(this);a?.call(this,o),this.requestUpdate(t,r,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)??ca}static _$Ei(){if(this.hasOwnProperty(Et("elementProperties")))return;const t=Tr(this);t.finalize(),t.l!==void 0&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(Et("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(Et("properties"))){const n=this.properties,i=[...Cr(n),...Er(n)];for(const s of i)this.createProperty(s,n[s])}const t=this[Symbol.metadata];if(t!==null){const n=litPropertyMetadata.get(t);if(n!==void 0)for(const[i,s]of n)this.elementProperties.set(i,s)}this._$Eh=new Map;for(const[n,i]of this.elementProperties){const s=this._$Eu(n,i);s!==void 0&&this._$Eh.set(s,n)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){const n=[];if(Array.isArray(t)){const i=new Set(t.flat(1/0).reverse());for(const s of i)n.unshift(la(s))}else t!==void 0&&n.push(la(t));return n}static _$Eu(t,n){const i=n.attribute;return i===!1?void 0:typeof i=="string"?i:typeof t=="string"?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??=new Set).add(t),this.renderRoot!==void 0&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){const t=new Map,n=this.constructor.elementProperties;for(const i of n.keys())this.hasOwnProperty(i)&&(t.set(i,this[i]),delete this[i]);t.size>0&&(this._$Ep=t)}createRenderRoot(){const t=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return Ar(t,this.constructor.elementStyles),t}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,n,i){this._$AK(t,i)}_$ET(t,n){const i=this.constructor.elementProperties.get(t),s=this.constructor._$Eu(t,i);if(s!==void 0&&i.reflect===!0){const a=(i.converter?.toAttribute!==void 0?i.converter:vn).toAttribute(n,i.type);this._$Em=t,a==null?this.removeAttribute(s):this.setAttribute(s,a),this._$Em=null}}_$AK(t,n){const i=this.constructor,s=i._$Eh.get(t);if(s!==void 0&&this._$Em!==s){const a=i.getPropertyOptions(s),o=typeof a.converter=="function"?{fromAttribute:a.converter}:a.converter?.fromAttribute!==void 0?a.converter:vn;this._$Em=s;const r=o.fromAttribute(n,a.type);this[s]=r??this._$Ej?.get(s)??r,this._$Em=null}}requestUpdate(t,n,i,s=!1,a){if(t!==void 0){const o=this.constructor;if(s===!1&&(a=this[t]),i??=o.getPropertyOptions(t),!((i.hasChanged??Zi)(a,n)||i.useDefault&&i.reflect&&a===this._$Ej?.get(t)&&!this.hasAttribute(o._$Eu(t,i))))return;this.C(t,n,i)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(t,n,{useDefault:i,reflect:s,wrapped:a},o){i&&!(this._$Ej??=new Map).has(t)&&(this._$Ej.set(t,o??n??this[t]),a!==!0||o!==void 0)||(this._$AL.has(t)||(this.hasUpdated||i||(n=void 0),this._$AL.set(t,n)),s===!0&&this._$Em!==t&&(this._$Eq??=new Set).add(t))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(n){Promise.reject(n)}const t=this.scheduleUpdate();return t!=null&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(const[s,a]of this._$Ep)this[s]=a;this._$Ep=void 0}const i=this.constructor.elementProperties;if(i.size>0)for(const[s,a]of i){const{wrapped:o}=a,r=this[s];o!==!0||this._$AL.has(s)||r===void 0||this.C(s,void 0,a,r)}}let t=!1;const n=this._$AL;try{t=this.shouldUpdate(n),t?(this.willUpdate(n),this._$EO?.forEach(i=>i.hostUpdate?.()),this.update(n)):this._$EM()}catch(i){throw t=!1,this._$EM(),i}t&&this._$AE(n)}willUpdate(t){}_$AE(t){this._$EO?.forEach(n=>n.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return!0}update(t){this._$Eq&&=this._$Eq.forEach(n=>this._$ET(n,this[n])),this._$EM()}updated(t){}firstUpdated(t){}};lt.elementStyles=[],lt.shadowRootOptions={mode:"open"},lt[Et("elementProperties")]=new Map,lt[Et("finalized")]=new Map,Ir?.({ReactiveElement:lt}),(_n.reactiveElementVersions??=[]).push("2.1.2");const Xi=globalThis,da=e=>e,mn=Xi.trustedTypes,ua=mn?mn.createPolicy("lit-html",{createHTML:e=>e}):void 0,To="$lit$",Ie=`lit$${Math.random().toFixed(9).slice(2)}$`,Lo="?"+Ie,Rr=`<${Lo}>`,We=document,Mt=()=>We.createComment(""),Pt=e=>e===null||typeof e!="object"&&typeof e!="function",es=Array.isArray,Mr=e=>es(e)||typeof e?.[Symbol.iterator]=="function",ni=`[ 	
\f\r]`,mt=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,fa=/-->/g,pa=/>/g,Ue=RegExp(`>|${ni}(?:([^\\s"'>=/]+)(${ni}*=${ni}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),ga=/'/g,ha=/"/g,Io=/^(?:script|style|textarea|title)$/i,Pr=e=>(t,...n)=>({_$litType$:e,strings:t,values:n}),l=Pr(1),Me=Symbol.for("lit-noChange"),g=Symbol.for("lit-nothing"),va=new WeakMap,Ge=We.createTreeWalker(We,129);function Ro(e,t){if(!es(e)||!e.hasOwnProperty("raw"))throw Error("invalid template strings array");return ua!==void 0?ua.createHTML(t):t}const Fr=(e,t)=>{const n=e.length-1,i=[];let s,a=t===2?"<svg>":t===3?"<math>":"",o=mt;for(let r=0;r<n;r++){const c=e[r];let u,f,p=-1,m=0;for(;m<c.length&&(o.lastIndex=m,f=o.exec(c),f!==null);)m=o.lastIndex,o===mt?f[1]==="!--"?o=fa:f[1]!==void 0?o=pa:f[2]!==void 0?(Io.test(f[2])&&(s=RegExp("</"+f[2],"g")),o=Ue):f[3]!==void 0&&(o=Ue):o===Ue?f[0]===">"?(o=s??mt,p=-1):f[1]===void 0?p=-2:(p=o.lastIndex-f[2].length,u=f[1],o=f[3]===void 0?Ue:f[3]==='"'?ha:ga):o===ha||o===ga?o=Ue:o===fa||o===pa?o=mt:(o=Ue,s=void 0);const v=o===Ue&&e[r+1].startsWith("/>")?" ":"";a+=o===mt?c+Rr:p>=0?(i.push(u),c.slice(0,p)+To+c.slice(p)+Ie+v):c+Ie+(p===-2?r:v)}return[Ro(e,a+(e[n]||"<?>")+(t===2?"</svg>":t===3?"</math>":"")),i]};class Ft{constructor({strings:t,_$litType$:n},i){let s;this.parts=[];let a=0,o=0;const r=t.length-1,c=this.parts,[u,f]=Fr(t,n);if(this.el=Ft.createElement(u,i),Ge.currentNode=this.el.content,n===2||n===3){const p=this.el.content.firstChild;p.replaceWith(...p.childNodes)}for(;(s=Ge.nextNode())!==null&&c.length<r;){if(s.nodeType===1){if(s.hasAttributes())for(const p of s.getAttributeNames())if(p.endsWith(To)){const m=f[o++],v=s.getAttribute(p).split(Ie),b=/([.?@])?(.*)/.exec(m);c.push({type:1,index:a,name:b[2],strings:v,ctor:b[1]==="."?Dr:b[1]==="?"?Or:b[1]==="@"?Br:En}),s.removeAttribute(p)}else p.startsWith(Ie)&&(c.push({type:6,index:a}),s.removeAttribute(p));if(Io.test(s.tagName)){const p=s.textContent.split(Ie),m=p.length-1;if(m>0){s.textContent=mn?mn.emptyScript:"";for(let v=0;v<m;v++)s.append(p[v],Mt()),Ge.nextNode(),c.push({type:2,index:++a});s.append(p[m],Mt())}}}else if(s.nodeType===8)if(s.data===Lo)c.push({type:2,index:a});else{let p=-1;for(;(p=s.data.indexOf(Ie,p+1))!==-1;)c.push({type:7,index:a}),p+=Ie.length-1}a++}}static createElement(t,n){const i=We.createElement("template");return i.innerHTML=t,i}}function dt(e,t,n=e,i){if(t===Me)return t;let s=i!==void 0?n._$Co?.[i]:n._$Cl;const a=Pt(t)?void 0:t._$litDirective$;return s?.constructor!==a&&(s?._$AO?.(!1),a===void 0?s=void 0:(s=new a(e),s._$AT(e,n,i)),i!==void 0?(n._$Co??=[])[i]=s:n._$Cl=s),s!==void 0&&(t=dt(e,s._$AS(e,t.values),s,i)),t}class Nr{constructor(t,n){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=n}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){const{el:{content:n},parts:i}=this._$AD,s=(t?.creationScope??We).importNode(n,!0);Ge.currentNode=s;let a=Ge.nextNode(),o=0,r=0,c=i[0];for(;c!==void 0;){if(o===c.index){let u;c.type===2?u=new Cn(a,a.nextSibling,this,t):c.type===1?u=new c.ctor(a,c.name,c.strings,this,t):c.type===6&&(u=new Ur(a,this,t)),this._$AV.push(u),c=i[++r]}o!==c?.index&&(a=Ge.nextNode(),o++)}return Ge.currentNode=We,s}p(t){let n=0;for(const i of this._$AV)i!==void 0&&(i.strings!==void 0?(i._$AI(t,i,n),n+=i.strings.length-2):i._$AI(t[n])),n++}}let Cn=class Mo{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,n,i,s){this.type=2,this._$AH=g,this._$AN=void 0,this._$AA=t,this._$AB=n,this._$AM=i,this.options=s,this._$Cv=s?.isConnected??!0}get parentNode(){let t=this._$AA.parentNode;const n=this._$AM;return n!==void 0&&t?.nodeType===11&&(t=n.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,n=this){t=dt(this,t,n),Pt(t)?t===g||t==null||t===""?(this._$AH!==g&&this._$AR(),this._$AH=g):t!==this._$AH&&t!==Me&&this._(t):t._$litType$!==void 0?this.$(t):t.nodeType!==void 0?this.T(t):Mr(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==g&&Pt(this._$AH)?this._$AA.nextSibling.data=t:this.T(We.createTextNode(t)),this._$AH=t}$(t){const{values:n,_$litType$:i}=t,s=typeof i=="number"?this._$AC(t):(i.el===void 0&&(i.el=Ft.createElement(Ro(i.h,i.h[0]),this.options)),i);if(this._$AH?._$AD===s)this._$AH.p(n);else{const a=new Nr(s,this),o=a.u(this.options);a.p(n),this.T(o),this._$AH=a}}_$AC(t){let n=va.get(t.strings);return n===void 0&&va.set(t.strings,n=new Ft(t)),n}k(t){es(this._$AH)||(this._$AH=[],this._$AR());const n=this._$AH;let i,s=0;for(const a of t)s===n.length?n.push(i=new Mo(this.O(Mt()),this.O(Mt()),this,this.options)):i=n[s],i._$AI(a),s++;s<n.length&&(this._$AR(i&&i._$AB.nextSibling,s),n.length=s)}_$AR(t=this._$AA.nextSibling,n){for(this._$AP?.(!1,!0,n);t!==this._$AB;){const i=da(t).nextSibling;da(t).remove(),t=i}}setConnected(t){this._$AM===void 0&&(this._$Cv=t,this._$AP?.(t))}},En=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,n,i,s,a){this.type=1,this._$AH=g,this._$AN=void 0,this.element=t,this.name=n,this._$AM=s,this.options=a,i.length>2||i[0]!==""||i[1]!==""?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=g}_$AI(t,n=this,i,s){const a=this.strings;let o=!1;if(a===void 0)t=dt(this,t,n,0),o=!Pt(t)||t!==this._$AH&&t!==Me,o&&(this._$AH=t);else{const r=t;let c,u;for(t=a[0],c=0;c<a.length-1;c++)u=dt(this,r[i+c],n,c),u===Me&&(u=this._$AH[c]),o||=!Pt(u)||u!==this._$AH[c],u===g?t=g:t!==g&&(t+=(u??"")+a[c+1]),this._$AH[c]=u}o&&!s&&this.j(t)}j(t){t===g?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??"")}},Dr=class extends En{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===g?void 0:t}},Or=class extends En{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==g)}},Br=class extends En{constructor(t,n,i,s,a){super(t,n,i,s,a),this.type=5}_$AI(t,n=this){if((t=dt(this,t,n,0)??g)===Me)return;const i=this._$AH,s=t===g&&i!==g||t.capture!==i.capture||t.once!==i.once||t.passive!==i.passive,a=t!==g&&(i===g||s);s&&this.element.removeEventListener(this.name,this,i),a&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}},Ur=class{constructor(t,n,i){this.element=t,this.type=6,this._$AN=void 0,this._$AM=n,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(t){dt(this,t)}};const Kr={I:Cn},zr=Xi.litHtmlPolyfillSupport;zr?.(Ft,Cn),(Xi.litHtmlVersions??=[]).push("3.3.2");const Hr=(e,t,n)=>{const i=n?.renderBefore??t;let s=i._$litPart$;if(s===void 0){const a=n?.renderBefore??null;i._$litPart$=s=new Cn(t.insertBefore(Mt(),a),a,void 0,n??{})}return s._$AI(e),s};const ts=globalThis;let ct=class extends lt{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){const t=super.createRenderRoot();return this.renderOptions.renderBefore??=t.firstChild,t}update(t){const n=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=Hr(n,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return Me}};ct._$litElement$=!0,ct.finalized=!0,ts.litElementHydrateSupport?.({LitElement:ct});const jr=ts.litElementPolyfillSupport;jr?.({LitElement:ct});(ts.litElementVersions??=[]).push("4.2.2");const Po=e=>(t,n)=>{n!==void 0?n.addInitializer(()=>{customElements.define(e,t)}):customElements.define(e,t)};const Gr={attribute:!0,type:String,converter:vn,reflect:!1,hasChanged:Zi},qr=(e=Gr,t,n)=>{const{kind:i,metadata:s}=n;let a=globalThis.litPropertyMetadata.get(s);if(a===void 0&&globalThis.litPropertyMetadata.set(s,a=new Map),i==="setter"&&((e=Object.create(e)).wrapped=!0),a.set(n.name,e),i==="accessor"){const{name:o}=n;return{set(r){const c=t.get.call(this);t.set.call(this,r),this.requestUpdate(o,c,e,!0,r)},init(r){return r!==void 0&&this.C(o,void 0,e,r),r}}}if(i==="setter"){const{name:o}=n;return function(r){const c=this[o];t.call(this,r),this.requestUpdate(o,c,e,!0,r)}}throw Error("Unsupported decorator location: "+i)};function Tn(e){return(t,n)=>typeof n=="object"?qr(e,t,n):((i,s,a)=>{const o=s.hasOwnProperty(a);return s.constructor.createProperty(a,i),o?Object.getOwnPropertyDescriptor(s,a):void 0})(e,t,n)}function k(e){return Tn({...e,state:!0,attribute:!1})}async function se(e,t){if(!(!e.client||!e.connected)&&!e.channelsLoading){e.channelsLoading=!0,e.channelsError=null;try{const n=await e.client.request("channels.status",{probe:t,timeoutMs:8e3});e.channelsSnapshot=n,e.channelsLastSuccess=Date.now()}catch(n){e.channelsError=String(n)}finally{e.channelsLoading=!1}}}async function Wr(e,t){if(!(!e.client||!e.connected||e.whatsappBusy)){e.whatsappBusy=!0;try{const n=await e.client.request("web.login.start",{force:t,timeoutMs:3e4});e.whatsappLoginMessage=n.message??null,e.whatsappLoginQrDataUrl=n.qrDataUrl??null,e.whatsappLoginConnected=null}catch(n){e.whatsappLoginMessage=String(n),e.whatsappLoginQrDataUrl=null,e.whatsappLoginConnected=null}finally{e.whatsappBusy=!1}}}async function Vr(e){if(!(!e.client||!e.connected||e.whatsappBusy)){e.whatsappBusy=!0;try{const t=await e.client.request("web.login.wait",{timeoutMs:12e4});e.whatsappLoginMessage=t.message??null,e.whatsappLoginConnected=t.connected??null,t.connected&&(e.whatsappLoginQrDataUrl=null)}catch(t){e.whatsappLoginMessage=String(t),e.whatsappLoginConnected=null}finally{e.whatsappBusy=!1}}}async function Yr(e){if(!(!e.client||!e.connected||e.whatsappBusy)){e.whatsappBusy=!0;try{await e.client.request("channels.logout",{channel:"whatsapp"}),e.whatsappLoginMessage="Logged out.",e.whatsappLoginQrDataUrl=null,e.whatsappLoginConnected=null}catch(t){e.whatsappLoginMessage=String(t)}finally{e.whatsappBusy=!1}}}function Ve(e){return typeof structuredClone=="function"?structuredClone(e):JSON.parse(JSON.stringify(e))}function ut(e){return`${JSON.stringify(e,null,2).trimEnd()}
`}function Fo(e,t,n){if(t.length===0)return;let i=e;for(let a=0;a<t.length-1;a+=1){const o=t[a],r=t[a+1];if(typeof o=="number"){if(!Array.isArray(i))return;i[o]==null&&(i[o]=typeof r=="number"?[]:{}),i=i[o]}else{if(typeof i!="object"||i==null)return;const c=i;c[o]==null&&(c[o]=typeof r=="number"?[]:{}),i=c[o]}}const s=t[t.length-1];if(typeof s=="number"){Array.isArray(i)&&(i[s]=n);return}typeof i=="object"&&i!=null&&(i[s]=n)}function No(e,t){if(t.length===0)return;let n=e;for(let s=0;s<t.length-1;s+=1){const a=t[s];if(typeof a=="number"){if(!Array.isArray(n))return;n=n[a]}else{if(typeof n!="object"||n==null)return;n=n[a]}if(n==null)return}const i=t[t.length-1];if(typeof i=="number"){Array.isArray(n)&&n.splice(i,1);return}typeof n=="object"&&n!=null&&delete n[i]}async function ge(e){if(!(!e.client||!e.connected)){e.configLoading=!0,e.lastError=null;try{const t=await e.client.request("config.get",{});Jr(e,t)}catch(t){e.lastError=String(t)}finally{e.configLoading=!1}}}async function Do(e){if(!(!e.client||!e.connected)&&!e.configSchemaLoading){e.configSchemaLoading=!0;try{const t=await e.client.request("config.schema",{});Qr(e,t)}catch(t){e.lastError=String(t)}finally{e.configSchemaLoading=!1}}}function Qr(e,t){e.configSchema=t.schema??null,e.configUiHints=t.uiHints??{},e.configSchemaVersion=t.version??null}function Jr(e,t){e.configSnapshot=t;const n=typeof t.raw=="string"?t.raw:t.config&&typeof t.config=="object"?ut(t.config):e.configRaw;!e.configFormDirty||e.configFormMode==="raw"?e.configRaw=n:e.configForm?e.configRaw=ut(e.configForm):e.configRaw=n,e.configValid=typeof t.valid=="boolean"?t.valid:null,e.configIssues=Array.isArray(t.issues)?t.issues:[],e.configFormDirty||(e.configForm=Ve(t.config??{}),e.configFormOriginal=Ve(t.config??{}),e.configRawOriginal=n)}async function fn(e){if(!(!e.client||!e.connected)){e.configSaving=!0,e.lastError=null;try{const t=e.configFormMode==="form"&&e.configForm?ut(e.configForm):e.configRaw,n=e.configSnapshot?.hash;if(!n){e.lastError="Config hash missing; reload and retry.";return}await e.client.request("config.set",{raw:t,baseHash:n}),e.configFormDirty=!1,await ge(e)}catch(t){e.lastError=String(t)}finally{e.configSaving=!1}}}async function Zr(e){if(!(!e.client||!e.connected)){e.configApplying=!0,e.lastError=null;try{const t=e.configFormMode==="form"&&e.configForm?ut(e.configForm):e.configRaw,n=e.configSnapshot?.hash;if(!n){e.lastError="Config hash missing; reload and retry.";return}await e.client.request("config.apply",{raw:t,baseHash:n,sessionKey:e.applySessionKey}),e.configFormDirty=!1,await ge(e)}catch(t){e.lastError=String(t)}finally{e.configApplying=!1}}}async function Xr(e){if(!(!e.client||!e.connected)){e.updateRunning=!0,e.lastError=null;try{await e.client.request("update.run",{sessionKey:e.applySessionKey})}catch(t){e.lastError=String(t)}finally{e.updateRunning=!1}}}function G(e,t,n){const i=Ve(e.configForm??e.configSnapshot?.config??{});Fo(i,t,n),e.configForm=i,e.configFormDirty=!0,e.configFormMode==="form"&&(e.configRaw=ut(i))}function de(e,t){const n=Ve(e.configForm??e.configSnapshot?.config??{});No(n,t),e.configForm=n,e.configFormDirty=!0,e.configFormMode==="form"&&(e.configRaw=ut(n))}function ec(e){const{values:t,original:n}=e;return t.name!==n.name||t.displayName!==n.displayName||t.about!==n.about||t.picture!==n.picture||t.banner!==n.banner||t.website!==n.website||t.nip05!==n.nip05||t.lud16!==n.lud16}function tc(e){const{state:t,callbacks:n,accountId:i}=e,s=ec(t),a=(r,c,u={})=>{const{type:f="text",placeholder:p,maxLength:m,help:v}=u,b=t.values[r]??"",d=t.fieldErrors[r],y=`nostr-profile-${r}`;return f==="textarea"?l`
        <div class="form-field" style="margin-bottom: 12px;">
          <label for="${y}" style="display: block; margin-bottom: 4px; font-weight: 500;">
            ${c}
          </label>
          <textarea
            id="${y}"
            .value=${b}
            placeholder=${p??""}
            maxlength=${m??2e3}
            rows="3"
            style="width: 100%; padding: 8px; border: 1px solid var(--border-color); border-radius: 4px; resize: vertical; font-family: inherit;"
            @input=${A=>{const x=A.target;n.onFieldChange(r,x.value)}}
            ?disabled=${t.saving}
          ></textarea>
          ${v?l`<div style="font-size: 12px; color: var(--text-muted); margin-top: 2px;">${v}</div>`:g}
          ${d?l`<div style="font-size: 12px; color: var(--danger-color); margin-top: 2px;">${d}</div>`:g}
        </div>
      `:l`
      <div class="form-field" style="margin-bottom: 12px;">
        <label for="${y}" style="display: block; margin-bottom: 4px; font-weight: 500;">
          ${c}
        </label>
        <input
          id="${y}"
          type=${f}
          .value=${b}
          placeholder=${p??""}
          maxlength=${m??256}
          style="width: 100%; padding: 8px; border: 1px solid var(--border-color); border-radius: 4px;"
          @input=${A=>{const x=A.target;n.onFieldChange(r,x.value)}}
          ?disabled=${t.saving}
        />
        ${v?l`<div style="font-size: 12px; color: var(--text-muted); margin-top: 2px;">${v}</div>`:g}
        ${d?l`<div style="font-size: 12px; color: var(--danger-color); margin-top: 2px;">${d}</div>`:g}
      </div>
    `},o=()=>{const r=t.values.picture;return r?l`
      <div style="margin-bottom: 12px;">
        <img
          src=${r}
          alt="Profile picture preview"
          style="max-width: 80px; max-height: 80px; border-radius: 50%; object-fit: cover; border: 2px solid var(--border-color);"
          @error=${c=>{const u=c.target;u.style.display="none"}}
          @load=${c=>{const u=c.target;u.style.display="block"}}
        />
      </div>
    `:g};return l`
    <div class="nostr-profile-form" style="padding: 16px; background: var(--bg-secondary); border-radius: 8px; margin-top: 12px;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
        <div style="font-weight: 600; font-size: 16px;">Edit Profile</div>
        <div style="font-size: 12px; color: var(--text-muted);">Account: ${i}</div>
      </div>

      ${t.error?l`<div class="callout danger" style="margin-bottom: 12px;">${t.error}</div>`:g}

      ${t.success?l`<div class="callout success" style="margin-bottom: 12px;">${t.success}</div>`:g}

      ${o()}

      ${a("name","Username",{placeholder:"satoshi",maxLength:256,help:"Short username (e.g., satoshi)"})}

      ${a("displayName","Display Name",{placeholder:"Satoshi Nakamoto",maxLength:256,help:"Your full display name"})}

      ${a("about","Bio",{type:"textarea",placeholder:"Tell people about yourself...",maxLength:2e3,help:"A brief bio or description"})}

      ${a("picture","Avatar URL",{type:"url",placeholder:"https://example.com/avatar.jpg",help:"HTTPS URL to your profile picture"})}

      ${t.showAdvanced?l`
            <div style="border-top: 1px solid var(--border-color); padding-top: 12px; margin-top: 12px;">
              <div style="font-weight: 500; margin-bottom: 12px; color: var(--text-muted);">Advanced</div>

              ${a("banner","Banner URL",{type:"url",placeholder:"https://example.com/banner.jpg",help:"HTTPS URL to a banner image"})}

              ${a("website","Website",{type:"url",placeholder:"https://example.com",help:"Your personal website"})}

              ${a("nip05","NIP-05 Identifier",{placeholder:"you@example.com",help:"Verifiable identifier (e.g., you@domain.com)"})}

              ${a("lud16","Lightning Address",{placeholder:"you@getalby.com",help:"Lightning address for tips (LUD-16)"})}
            </div>
          `:g}

      <div style="display: flex; gap: 8px; margin-top: 16px; flex-wrap: wrap;">
        <button
          class="btn primary"
          @click=${n.onSave}
          ?disabled=${t.saving||!s}
        >
          ${t.saving?"Saving...":"Save & Publish"}
        </button>

        <button
          class="btn"
          @click=${n.onImport}
          ?disabled=${t.importing||t.saving}
        >
          ${t.importing?"Importing...":"Import from Relays"}
        </button>

        <button
          class="btn"
          @click=${n.onToggleAdvanced}
        >
          ${t.showAdvanced?"Hide Advanced":"Show Advanced"}
        </button>

        <button
          class="btn"
          @click=${n.onCancel}
          ?disabled=${t.saving}
        >
          Cancel
        </button>
      </div>

      ${s?l`
              <div style="font-size: 12px; color: var(--warning-color); margin-top: 8px">
                You have unsaved changes
              </div>
            `:g}
    </div>
  `}function nc(e){const t={name:e?.name??"",displayName:e?.displayName??"",about:e?.about??"",picture:e?.picture??"",banner:e?.banner??"",website:e?.website??"",nip05:e?.nip05??"",lud16:e?.lud16??""};return{values:t,original:{...t},saving:!1,importing:!1,error:null,success:null,fieldErrors:{},showAdvanced:!!(e?.banner||e?.website||e?.nip05||e?.lud16)}}async function ic(e,t){await Wr(e,t),await se(e,!0)}async function sc(e){await Vr(e),await se(e,!0)}async function ac(e){await Yr(e),await se(e,!0)}async function oc(e){await fn(e),await ge(e),await se(e,!0)}async function lc(e){await ge(e),await se(e,!0)}function rc(e){if(!Array.isArray(e))return{};const t={};for(const n of e){if(typeof n!="string")continue;const[i,...s]=n.split(":");if(!i||s.length===0)continue;const a=i.trim(),o=s.join(":").trim();a&&o&&(t[a]=o)}return t}function Oo(e){return(e.channelsSnapshot?.channelAccounts?.nostr??[])[0]?.accountId??e.nostrProfileAccountId??"default"}function Bo(e,t=""){return`/api/channels/nostr/${encodeURIComponent(e)}/profile${t}`}function cc(e,t,n){e.nostrProfileAccountId=t,e.nostrProfileFormState=nc(n??void 0)}function dc(e){e.nostrProfileFormState=null,e.nostrProfileAccountId=null}function uc(e,t,n){const i=e.nostrProfileFormState;i&&(e.nostrProfileFormState={...i,values:{...i.values,[t]:n},fieldErrors:{...i.fieldErrors,[t]:""}})}function fc(e){const t=e.nostrProfileFormState;t&&(e.nostrProfileFormState={...t,showAdvanced:!t.showAdvanced})}async function pc(e){const t=e.nostrProfileFormState;if(!t||t.saving)return;const n=Oo(e);e.nostrProfileFormState={...t,saving:!0,error:null,success:null,fieldErrors:{}};try{const i=await fetch(Bo(n),{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(t.values)}),s=await i.json().catch(()=>null);if(!i.ok||s?.ok===!1||!s){const a=s?.error??`Profile update failed (${i.status})`;e.nostrProfileFormState={...t,saving:!1,error:a,success:null,fieldErrors:rc(s?.details)};return}if(!s.persisted){e.nostrProfileFormState={...t,saving:!1,error:"Profile publish failed on all relays.",success:null};return}e.nostrProfileFormState={...t,saving:!1,error:null,success:"Profile published to relays.",fieldErrors:{},original:{...t.values}},await se(e,!0)}catch(i){e.nostrProfileFormState={...t,saving:!1,error:`Profile update failed: ${String(i)}`,success:null}}}async function gc(e){const t=e.nostrProfileFormState;if(!t||t.importing)return;const n=Oo(e);e.nostrProfileFormState={...t,importing:!0,error:null,success:null};try{const i=await fetch(Bo(n,"/import"),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({autoMerge:!0})}),s=await i.json().catch(()=>null);if(!i.ok||s?.ok===!1||!s){const c=s?.error??`Profile import failed (${i.status})`;e.nostrProfileFormState={...t,importing:!1,error:c,success:null};return}const a=s.merged??s.imported??null,o=a?{...t.values,...a}:t.values,r=!!(o.banner||o.website||o.nip05||o.lud16);e.nostrProfileFormState={...t,importing:!1,values:o,error:null,success:s.saved?"Profile imported from relays. Review and publish.":"Profile imported. Review and publish.",showAdvanced:r},s.saved&&await se(e,!0)}catch(i){e.nostrProfileFormState={...t,importing:!1,error:`Profile import failed: ${String(i)}`,success:null}}}function Uo(e){const t=(e??"").trim();if(!t)return null;const n=t.split(":").filter(Boolean);if(n.length<3||n[0]!=="agent")return null;const i=n[1]?.trim(),s=n.slice(2).join(":");return!i||!s?null:{agentId:i,rest:s}}const xi=450;function Kt(e,t=!1){e.chatScrollFrame&&cancelAnimationFrame(e.chatScrollFrame),e.chatScrollTimeout!=null&&(clearTimeout(e.chatScrollTimeout),e.chatScrollTimeout=null);const n=()=>{const i=e.querySelector(".chat-thread");if(i){const s=getComputedStyle(i).overflowY;if(s==="auto"||s==="scroll"||i.scrollHeight-i.clientHeight>1)return i}return document.scrollingElement??document.documentElement};e.updateComplete.then(()=>{e.chatScrollFrame=requestAnimationFrame(()=>{e.chatScrollFrame=null;const i=n();if(!i)return;const s=i.scrollHeight-i.scrollTop-i.clientHeight,a=t&&!e.chatHasAutoScrolled;if(!(a||e.chatUserNearBottom||s<xi)){e.chatNewMessagesBelow=!0;return}a&&(e.chatHasAutoScrolled=!0),i.scrollTop=i.scrollHeight,e.chatUserNearBottom=!0,e.chatNewMessagesBelow=!1;const r=a?150:120;e.chatScrollTimeout=window.setTimeout(()=>{e.chatScrollTimeout=null;const c=n();if(!c)return;const u=c.scrollHeight-c.scrollTop-c.clientHeight;(a||e.chatUserNearBottom||u<xi)&&(c.scrollTop=c.scrollHeight,e.chatUserNearBottom=!0)},r)})})}function Ko(e,t=!1){e.logsScrollFrame&&cancelAnimationFrame(e.logsScrollFrame),e.updateComplete.then(()=>{e.logsScrollFrame=requestAnimationFrame(()=>{e.logsScrollFrame=null;const n=e.querySelector(".log-stream");if(!n)return;const i=n.scrollHeight-n.scrollTop-n.clientHeight;(t||i<80)&&(n.scrollTop=n.scrollHeight)})})}function hc(e,t){const n=t.currentTarget;if(!n)return;const i=n.scrollHeight-n.scrollTop-n.clientHeight;e.chatUserNearBottom=i<xi,e.chatUserNearBottom&&(e.chatNewMessagesBelow=!1)}function vc(e,t){const n=t.currentTarget;if(!n)return;const i=n.scrollHeight-n.scrollTop-n.clientHeight;e.logsAtBottom=i<80}function ma(e){e.chatHasAutoScrolled=!1,e.chatUserNearBottom=!0,e.chatNewMessagesBelow=!1}function mc(e,t){if(e.length===0)return;const n=new Blob([`${e.join(`
`)}
`],{type:"text/plain"}),i=URL.createObjectURL(n),s=document.createElement("a"),a=new Date().toISOString().slice(0,19).replace(/[:T]/g,"-");s.href=i,s.download=`openclaw-logs-${t}-${a}.log`,s.click(),URL.revokeObjectURL(i)}function yc(e){if(typeof ResizeObserver>"u")return;const t=e.querySelector(".topbar");if(!t)return;const n=()=>{const{height:i}=t.getBoundingClientRect();e.style.setProperty("--topbar-height",`${i}px`)};n(),e.topbarObserver=new ResizeObserver(()=>n()),e.topbarObserver.observe(t)}async function Ln(e){if(!(!e.client||!e.connected)&&!e.debugLoading){e.debugLoading=!0;try{const[t,n,i,s]=await Promise.all([e.client.request("status",{}),e.client.request("health",{}),e.client.request("models.list",{}),e.client.request("last-heartbeat",{})]);e.debugStatus=t,e.debugHealth=n;const a=i;e.debugModels=Array.isArray(a?.models)?a?.models:[],e.debugHeartbeat=s}catch(t){e.debugCallError=String(t)}finally{e.debugLoading=!1}}}async function bc(e){if(!(!e.client||!e.connected)){e.debugCallError=null,e.debugCallResult=null;try{const t=e.debugCallParams.trim()?JSON.parse(e.debugCallParams):{},n=await e.client.request(e.debugCallMethod.trim(),t);e.debugCallResult=JSON.stringify(n,null,2)}catch(t){e.debugCallError=String(t)}}}const $c=2e3,wc=new Set(["trace","debug","info","warn","error","fatal"]);function kc(e){if(typeof e!="string")return null;const t=e.trim();if(!t.startsWith("{")||!t.endsWith("}"))return null;try{const n=JSON.parse(t);return!n||typeof n!="object"?null:n}catch{return null}}function Ac(e){if(typeof e!="string")return null;const t=e.toLowerCase();return wc.has(t)?t:null}function xc(e){if(!e.trim())return{raw:e,message:e};try{const t=JSON.parse(e),n=t&&typeof t._meta=="object"&&t._meta!==null?t._meta:null,i=typeof t.time=="string"?t.time:typeof n?.date=="string"?n?.date:null,s=Ac(n?.logLevelName??n?.level),a=typeof t[0]=="string"?t[0]:typeof n?.name=="string"?n?.name:null,o=kc(a);let r=null;o&&(typeof o.subsystem=="string"?r=o.subsystem:typeof o.module=="string"&&(r=o.module)),!r&&a&&a.length<120&&(r=a);let c=null;return typeof t[1]=="string"?c=t[1]:!o&&typeof t[0]=="string"?c=t[0]:typeof t.message=="string"&&(c=t.message),{raw:e,time:i,level:s,subsystem:r,message:c??e,meta:n??void 0}}catch{return{raw:e,message:e}}}async function ns(e,t){if(!(!e.client||!e.connected)&&!(e.logsLoading&&!t?.quiet)){t?.quiet||(e.logsLoading=!0),e.logsError=null;try{const i=await e.client.request("logs.tail",{cursor:t?.reset?void 0:e.logsCursor??void 0,limit:e.logsLimit,maxBytes:e.logsMaxBytes}),a=(Array.isArray(i.lines)?i.lines.filter(r=>typeof r=="string"):[]).map(xc),o=!!(t?.reset||i.reset||e.logsCursor==null);e.logsEntries=o?a:[...e.logsEntries,...a].slice(-$c),typeof i.cursor=="number"&&(e.logsCursor=i.cursor),typeof i.file=="string"&&(e.logsFile=i.file),e.logsTruncated=!!i.truncated,e.logsLastFetchAt=Date.now()}catch(n){e.logsError=String(n)}finally{t?.quiet||(e.logsLoading=!1)}}}async function In(e,t){if(!(!e.client||!e.connected)&&!e.nodesLoading){e.nodesLoading=!0,t?.quiet||(e.lastError=null);try{const n=await e.client.request("node.list",{});e.nodes=Array.isArray(n.nodes)?n.nodes:[]}catch(n){t?.quiet||(e.lastError=String(n))}finally{e.nodesLoading=!1}}}function Sc(e){e.nodesPollInterval==null&&(e.nodesPollInterval=window.setInterval(()=>{In(e,{quiet:!0})},5e3))}function _c(e){e.nodesPollInterval!=null&&(clearInterval(e.nodesPollInterval),e.nodesPollInterval=null)}function is(e){e.logsPollInterval==null&&(e.logsPollInterval=window.setInterval(()=>{e.tab==="logs"&&ns(e,{quiet:!0})},2e3))}function ss(e){e.logsPollInterval!=null&&(clearInterval(e.logsPollInterval),e.logsPollInterval=null)}function as(e){e.debugPollInterval==null&&(e.debugPollInterval=window.setInterval(()=>{e.tab==="debug"&&Ln(e)},3e3))}function os(e){e.debugPollInterval!=null&&(clearInterval(e.debugPollInterval),e.debugPollInterval=null)}async function zo(e,t){if(!(!e.client||!e.connected||e.agentIdentityLoading)&&!e.agentIdentityById[t]){e.agentIdentityLoading=!0,e.agentIdentityError=null;try{const n=await e.client.request("agent.identity.get",{agentId:t});n&&(e.agentIdentityById={...e.agentIdentityById,[t]:n})}catch(n){e.agentIdentityError=String(n)}finally{e.agentIdentityLoading=!1}}}async function Ho(e,t){if(!e.client||!e.connected||e.agentIdentityLoading)return;const n=t.filter(i=>!e.agentIdentityById[i]);if(n.length!==0){e.agentIdentityLoading=!0,e.agentIdentityError=null;try{for(const i of n){const s=await e.client.request("agent.identity.get",{agentId:i});s&&(e.agentIdentityById={...e.agentIdentityById,[i]:s})}}catch(i){e.agentIdentityError=String(i)}finally{e.agentIdentityLoading=!1}}}async function pn(e,t){if(!(!e.client||!e.connected)&&!e.agentSkillsLoading){e.agentSkillsLoading=!0,e.agentSkillsError=null;try{const n=await e.client.request("skills.status",{agentId:t});n&&(e.agentSkillsReport=n,e.agentSkillsAgentId=t)}catch(n){e.agentSkillsError=String(n)}finally{e.agentSkillsLoading=!1}}}async function ls(e){if(!(!e.client||!e.connected)&&!e.agentsLoading){e.agentsLoading=!0,e.agentsError=null;try{const t=await e.client.request("agents.list",{});if(t){e.agentsList=t;const n=e.agentsSelectedId,i=t.agents.some(s=>s.id===n);(!n||!i)&&(e.agentsSelectedId=t.defaultId??t.agents[0]?.id??null)}}catch(t){e.agentsError=String(t)}finally{e.agentsLoading=!1}}}const Cc=/<\s*\/?\s*(?:think(?:ing)?|thought|antthinking|final)\b/i,en=/<\s*\/?\s*final\b[^<>]*>/gi,ya=/<\s*(\/?)\s*(?:think(?:ing)?|thought|antthinking)\b[^<>]*>/gi;function ba(e){const t=[],n=/(^|\n)(```|~~~)[^\n]*\n[\s\S]*?(?:\n\2(?:\n|$)|$)/g;for(const s of e.matchAll(n)){const a=(s.index??0)+s[1].length;t.push({start:a,end:a+s[0].length-s[1].length})}const i=/`+[^`]+`+/g;for(const s of e.matchAll(i)){const a=s.index??0,o=a+s[0].length;t.some(c=>a>=c.start&&o<=c.end)||t.push({start:a,end:o})}return t.sort((s,a)=>s.start-a.start),t}function $a(e,t){return t.some(n=>e>=n.start&&e<n.end)}function Ec(e,t){return e.trimStart()}function Tc(e,t){if(!e||!Cc.test(e))return e;let n=e;if(en.test(n)){en.lastIndex=0;const r=[],c=ba(n);for(const u of n.matchAll(en)){const f=u.index??0;r.push({start:f,length:u[0].length,inCode:$a(f,c)})}for(let u=r.length-1;u>=0;u--){const f=r[u];f.inCode||(n=n.slice(0,f.start)+n.slice(f.start+f.length))}}else en.lastIndex=0;const i=ba(n);ya.lastIndex=0;let s="",a=0,o=!1;for(const r of n.matchAll(ya)){const c=r.index??0,u=r[1]==="/";$a(c,i)||(o?u&&(o=!1):(s+=n.slice(a,c),u||(o=!0)),a=c+r[0].length)}return s+=n.slice(a),Ec(s)}function Nt(e){return!e&&e!==0?"n/a":new Date(e).toLocaleString()}function O(e){if(!e&&e!==0)return"n/a";const t=Date.now()-e,n=Math.abs(t),i=t<0?"from now":"ago",s=Math.round(n/1e3);if(s<60)return t<0?"just now":`${s}s ago`;const a=Math.round(s/60);if(a<60)return`${a}m ${i}`;const o=Math.round(a/60);return o<48?`${o}h ${i}`:`${Math.round(o/24)}d ${i}`}function jo(e){if(!e&&e!==0)return"n/a";if(e<1e3)return`${e}ms`;const t=Math.round(e/1e3);if(t<60)return`${t}s`;const n=Math.round(t/60);if(n<60)return`${n}m`;const i=Math.round(n/60);return i<48?`${i}h`:`${Math.round(i/24)}d`}function Si(e){return!e||e.length===0?"none":e.filter(t=>!!(t&&t.trim())).join(", ")}function _i(e,t=120){return e.length<=t?e:`${e.slice(0,Math.max(0,t-1))}…`}function Go(e,t){return e.length<=t?{text:e,truncated:!1,total:e.length}:{text:e.slice(0,Math.max(0,t)),truncated:!0,total:e.length}}function yn(e,t){const n=Number(e);return Number.isFinite(n)?n:t}function ii(e){return Tc(e)}async function zt(e){if(!(!e.client||!e.connected))try{const t=await e.client.request("cron.status",{});e.cronStatus=t}catch(t){e.cronError=String(t)}}async function Rn(e){if(!(!e.client||!e.connected)&&!e.cronLoading){e.cronLoading=!0,e.cronError=null;try{const t=await e.client.request("cron.list",{includeDisabled:!0});e.cronJobs=Array.isArray(t.jobs)?t.jobs:[]}catch(t){e.cronError=String(t)}finally{e.cronLoading=!1}}}function Lc(e){if(e.scheduleKind==="at"){const n=Date.parse(e.scheduleAt);if(!Number.isFinite(n))throw new Error("Invalid run time.");return{kind:"at",at:new Date(n).toISOString()}}if(e.scheduleKind==="every"){const n=yn(e.everyAmount,0);if(n<=0)throw new Error("Invalid interval amount.");const i=e.everyUnit;return{kind:"every",everyMs:n*(i==="minutes"?6e4:i==="hours"?36e5:864e5)}}const t=e.cronExpr.trim();if(!t)throw new Error("Cron expression required.");return{kind:"cron",expr:t,tz:e.cronTz.trim()||void 0}}function Ic(e){if(e.payloadKind==="systemEvent"){const s=e.payloadText.trim();if(!s)throw new Error("System event text required.");return{kind:"systemEvent",text:s}}const t=e.payloadText.trim();if(!t)throw new Error("Agent message required.");const n={kind:"agentTurn",message:t},i=yn(e.timeoutSeconds,0);return i>0&&(n.timeoutSeconds=i),n}async function Rc(e){if(!(!e.client||!e.connected||e.cronBusy)){e.cronBusy=!0,e.cronError=null;try{const t=Lc(e.cronForm),n=Ic(e.cronForm),i=e.cronForm.sessionTarget==="isolated"&&e.cronForm.payloadKind==="agentTurn"&&e.cronForm.deliveryMode?{mode:e.cronForm.deliveryMode==="announce"?"announce":"none",channel:e.cronForm.deliveryChannel.trim()||"last",to:e.cronForm.deliveryTo.trim()||void 0}:void 0,s=e.cronForm.agentId.trim(),a={name:e.cronForm.name.trim(),description:e.cronForm.description.trim()||void 0,agentId:s||void 0,enabled:e.cronForm.enabled,schedule:t,sessionTarget:e.cronForm.sessionTarget,wakeMode:e.cronForm.wakeMode,payload:n,delivery:i};if(!a.name)throw new Error("Name required.");await e.client.request("cron.add",a),e.cronForm={...e.cronForm,name:"",description:"",payloadText:""},await Rn(e),await zt(e)}catch(t){e.cronError=String(t)}finally{e.cronBusy=!1}}}async function Mc(e,t,n){if(!(!e.client||!e.connected||e.cronBusy)){e.cronBusy=!0,e.cronError=null;try{await e.client.request("cron.update",{id:t.id,patch:{enabled:n}}),await Rn(e),await zt(e)}catch(i){e.cronError=String(i)}finally{e.cronBusy=!1}}}async function Pc(e,t){if(!(!e.client||!e.connected||e.cronBusy)){e.cronBusy=!0,e.cronError=null;try{await e.client.request("cron.run",{id:t.id,mode:"force"}),await qo(e,t.id)}catch(n){e.cronError=String(n)}finally{e.cronBusy=!1}}}async function Fc(e,t){if(!(!e.client||!e.connected||e.cronBusy)){e.cronBusy=!0,e.cronError=null;try{await e.client.request("cron.remove",{id:t.id}),e.cronRunsJobId===t.id&&(e.cronRunsJobId=null,e.cronRuns=[]),await Rn(e),await zt(e)}catch(n){e.cronError=String(n)}finally{e.cronBusy=!1}}}async function qo(e,t){if(!(!e.client||!e.connected))try{const n=await e.client.request("cron.runs",{id:t,limit:50});e.cronRunsJobId=t,e.cronRuns=Array.isArray(n.entries)?n.entries:[]}catch(n){e.cronError=String(n)}}const Wo="openclaw.device.auth.v1";function rs(e){return e.trim()}function Nc(e){if(!Array.isArray(e))return[];const t=new Set;for(const n of e){const i=n.trim();i&&t.add(i)}return[...t].toSorted()}function cs(){try{const e=window.localStorage.getItem(Wo);if(!e)return null;const t=JSON.parse(e);return!t||t.version!==1||!t.deviceId||typeof t.deviceId!="string"||!t.tokens||typeof t.tokens!="object"?null:t}catch{return null}}function Vo(e){try{window.localStorage.setItem(Wo,JSON.stringify(e))}catch{}}function Dc(e){const t=cs();if(!t||t.deviceId!==e.deviceId)return null;const n=rs(e.role),i=t.tokens[n];return!i||typeof i.token!="string"?null:i}function Yo(e){const t=rs(e.role),n={version:1,deviceId:e.deviceId,tokens:{}},i=cs();i&&i.deviceId===e.deviceId&&(n.tokens={...i.tokens});const s={token:e.token,role:t,scopes:Nc(e.scopes),updatedAtMs:Date.now()};return n.tokens[t]=s,Vo(n),s}function Qo(e){const t=cs();if(!t||t.deviceId!==e.deviceId)return;const n=rs(e.role);if(!t.tokens[n])return;const i={...t,tokens:{...t.tokens}};delete i.tokens[n],Vo(i)}const Jo={p:0x7fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffedn,n:0x1000000000000000000000000000000014def9dea2f79cd65812631a5cf5d3edn,h:8n,a:0x7fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffecn,d:0x52036cee2b6ffe738cc740797779e89800700a4d4141d8ab75eb4dca135978a3n,Gx:0x216936d3cd6e53fec0a4e231fdd6dc5c692cc7609525a7b2c9562d608f25d51an,Gy:0x6666666666666666666666666666666666666666666666666666666666666658n},{p:Z,n:gn,Gx:wa,Gy:ka,a:si,d:ai,h:Oc}=Jo,Ye=32,ds=64,Bc=(...e)=>{"captureStackTrace"in Error&&typeof Error.captureStackTrace=="function"&&Error.captureStackTrace(...e)},q=(e="")=>{const t=new Error(e);throw Bc(t,q),t},Uc=e=>typeof e=="bigint",Kc=e=>typeof e=="string",zc=e=>e instanceof Uint8Array||ArrayBuffer.isView(e)&&e.constructor.name==="Uint8Array",Fe=(e,t,n="")=>{const i=zc(e),s=e?.length,a=t!==void 0;if(!i||a&&s!==t){const o=n&&`"${n}" `,r=a?` of length ${t}`:"",c=i?`length=${s}`:`type=${typeof e}`;q(o+"expected Uint8Array"+r+", got "+c)}return e},Mn=e=>new Uint8Array(e),Zo=e=>Uint8Array.from(e),Xo=(e,t)=>e.toString(16).padStart(t,"0"),el=e=>Array.from(Fe(e)).map(t=>Xo(t,2)).join(""),xe={_0:48,_9:57,A:65,F:70,a:97,f:102},Aa=e=>{if(e>=xe._0&&e<=xe._9)return e-xe._0;if(e>=xe.A&&e<=xe.F)return e-(xe.A-10);if(e>=xe.a&&e<=xe.f)return e-(xe.a-10)},tl=e=>{const t="hex invalid";if(!Kc(e))return q(t);const n=e.length,i=n/2;if(n%2)return q(t);const s=Mn(i);for(let a=0,o=0;a<i;a++,o+=2){const r=Aa(e.charCodeAt(o)),c=Aa(e.charCodeAt(o+1));if(r===void 0||c===void 0)return q(t);s[a]=r*16+c}return s},nl=()=>globalThis?.crypto,Hc=()=>nl()?.subtle??q("crypto.subtle must be defined, consider polyfill"),Dt=(...e)=>{const t=Mn(e.reduce((i,s)=>i+Fe(s).length,0));let n=0;return e.forEach(i=>{t.set(i,n),n+=i.length}),t},jc=(e=Ye)=>nl().getRandomValues(Mn(e)),bn=BigInt,He=(e,t,n,i="bad number: out of range")=>Uc(e)&&t<=e&&e<n?e:q(i),L=(e,t=Z)=>{const n=e%t;return n>=0n?n:t+n},il=e=>L(e,gn),Gc=(e,t)=>{(e===0n||t<=0n)&&q("no inverse n="+e+" mod="+t);let n=L(e,t),i=t,s=0n,a=1n;for(;n!==0n;){const o=i/n,r=i%n,c=s-a*o;i=n,n=r,s=a,a=c}return i===1n?L(s,t):q("no inverse")},qc=e=>{const t=ll[e];return typeof t!="function"&&q("hashes."+e+" not set"),t},oi=e=>e instanceof oe?e:q("Point expected"),Ci=2n**256n;class oe{static BASE;static ZERO;X;Y;Z;T;constructor(t,n,i,s){const a=Ci;this.X=He(t,0n,a),this.Y=He(n,0n,a),this.Z=He(i,1n,a),this.T=He(s,0n,a),Object.freeze(this)}static CURVE(){return Jo}static fromAffine(t){return new oe(t.x,t.y,1n,L(t.x*t.y))}static fromBytes(t,n=!1){const i=ai,s=Zo(Fe(t,Ye)),a=t[31];s[31]=a&-129;const o=al(s);He(o,0n,n?Ci:Z);const c=L(o*o),u=L(c-1n),f=L(i*c+1n);let{isValid:p,value:m}=Vc(u,f);p||q("bad point: y not sqrt");const v=(m&1n)===1n,b=(a&128)!==0;return!n&&m===0n&&b&&q("bad point: x==0, isLastByteOdd"),b!==v&&(m=L(-m)),new oe(m,o,1n,L(m*o))}static fromHex(t,n){return oe.fromBytes(tl(t),n)}get x(){return this.toAffine().x}get y(){return this.toAffine().y}assertValidity(){const t=si,n=ai,i=this;if(i.is0())return q("bad point: ZERO");const{X:s,Y:a,Z:o,T:r}=i,c=L(s*s),u=L(a*a),f=L(o*o),p=L(f*f),m=L(c*t),v=L(f*L(m+u)),b=L(p+L(n*L(c*u)));if(v!==b)return q("bad point: equation left != right (1)");const d=L(s*a),y=L(o*r);return d!==y?q("bad point: equation left != right (2)"):this}equals(t){const{X:n,Y:i,Z:s}=this,{X:a,Y:o,Z:r}=oi(t),c=L(n*r),u=L(a*s),f=L(i*r),p=L(o*s);return c===u&&f===p}is0(){return this.equals(rt)}negate(){return new oe(L(-this.X),this.Y,this.Z,L(-this.T))}double(){const{X:t,Y:n,Z:i}=this,s=si,a=L(t*t),o=L(n*n),r=L(2n*L(i*i)),c=L(s*a),u=t+n,f=L(L(u*u)-a-o),p=c+o,m=p-r,v=c-o,b=L(f*m),d=L(p*v),y=L(f*v),A=L(m*p);return new oe(b,d,A,y)}add(t){const{X:n,Y:i,Z:s,T:a}=this,{X:o,Y:r,Z:c,T:u}=oi(t),f=si,p=ai,m=L(n*o),v=L(i*r),b=L(a*p*u),d=L(s*c),y=L((n+i)*(o+r)-m-v),A=L(d-b),x=L(d+b),T=L(v-f*m),S=L(y*A),E=L(x*T),C=L(y*T),P=L(A*x);return new oe(S,E,P,C)}subtract(t){return this.add(oi(t).negate())}multiply(t,n=!0){if(!n&&(t===0n||this.is0()))return rt;if(He(t,1n,gn),t===1n)return this;if(this.equals(Qe))return ad(t).p;let i=rt,s=Qe;for(let a=this;t>0n;a=a.double(),t>>=1n)t&1n?i=i.add(a):n&&(s=s.add(a));return i}multiplyUnsafe(t){return this.multiply(t,!1)}toAffine(){const{X:t,Y:n,Z:i}=this;if(this.equals(rt))return{x:0n,y:1n};const s=Gc(i,Z);L(i*s)!==1n&&q("invalid inverse");const a=L(t*s),o=L(n*s);return{x:a,y:o}}toBytes(){const{x:t,y:n}=this.assertValidity().toAffine(),i=sl(n);return i[31]|=t&1n?128:0,i}toHex(){return el(this.toBytes())}clearCofactor(){return this.multiply(bn(Oc),!1)}isSmallOrder(){return this.clearCofactor().is0()}isTorsionFree(){let t=this.multiply(gn/2n,!1).double();return gn%2n&&(t=t.add(this)),t.is0()}}const Qe=new oe(wa,ka,1n,L(wa*ka)),rt=new oe(0n,1n,1n,0n);oe.BASE=Qe;oe.ZERO=rt;const sl=e=>tl(Xo(He(e,0n,Ci),ds)).reverse(),al=e=>bn("0x"+el(Zo(Fe(e)).reverse())),ye=(e,t)=>{let n=e;for(;t-- >0n;)n*=n,n%=Z;return n},Wc=e=>{const n=e*e%Z*e%Z,i=ye(n,2n)*n%Z,s=ye(i,1n)*e%Z,a=ye(s,5n)*s%Z,o=ye(a,10n)*a%Z,r=ye(o,20n)*o%Z,c=ye(r,40n)*r%Z,u=ye(c,80n)*c%Z,f=ye(u,80n)*c%Z,p=ye(f,10n)*a%Z;return{pow_p_5_8:ye(p,2n)*e%Z,b2:n}},xa=0x2b8324804fc1df0b2b4d00993dfbd7a72f431806ad2fe478c4ee1b274a0ea0b0n,Vc=(e,t)=>{const n=L(t*t*t),i=L(n*n*t),s=Wc(e*i).pow_p_5_8;let a=L(e*n*s);const o=L(t*a*a),r=a,c=L(a*xa),u=o===e,f=o===L(-e),p=o===L(-e*xa);return u&&(a=r),(f||p)&&(a=c),(L(a)&1n)===1n&&(a=L(-a)),{isValid:u||f,value:a}},Ei=e=>il(al(e)),us=(...e)=>ll.sha512Async(Dt(...e)),Yc=(...e)=>qc("sha512")(Dt(...e)),ol=e=>{const t=e.slice(0,Ye);t[0]&=248,t[31]&=127,t[31]|=64;const n=e.slice(Ye,ds),i=Ei(t),s=Qe.multiply(i),a=s.toBytes();return{head:t,prefix:n,scalar:i,point:s,pointBytes:a}},fs=e=>us(Fe(e,Ye)).then(ol),Qc=e=>ol(Yc(Fe(e,Ye))),Jc=e=>fs(e).then(t=>t.pointBytes),Zc=e=>us(e.hashable).then(e.finish),Xc=(e,t,n)=>{const{pointBytes:i,scalar:s}=e,a=Ei(t),o=Qe.multiply(a).toBytes();return{hashable:Dt(o,i,n),finish:u=>{const f=il(a+Ei(u)*s);return Fe(Dt(o,sl(f)),ds)}}},ed=async(e,t)=>{const n=Fe(e),i=await fs(t),s=await us(i.prefix,n);return Zc(Xc(i,s,n))},ll={sha512Async:async e=>{const t=Hc(),n=Dt(e);return Mn(await t.digest("SHA-512",n.buffer))},sha512:void 0},td=(e=jc(Ye))=>e,nd={getExtendedPublicKeyAsync:fs,getExtendedPublicKey:Qc,randomSecretKey:td},$n=8,id=256,rl=Math.ceil(id/$n)+1,Ti=2**($n-1),sd=()=>{const e=[];let t=Qe,n=t;for(let i=0;i<rl;i++){n=t,e.push(n);for(let s=1;s<Ti;s++)n=n.add(t),e.push(n);t=n.double()}return e};let Sa;const _a=(e,t)=>{const n=t.negate();return e?n:t},ad=e=>{const t=Sa||(Sa=sd());let n=rt,i=Qe;const s=2**$n,a=s,o=bn(s-1),r=bn($n);for(let c=0;c<rl;c++){let u=Number(e&o);e>>=r,u>Ti&&(u-=a,e+=1n);const f=c*Ti,p=f,m=f+Math.abs(u)-1,v=c%2!==0,b=u<0;u===0?i=i.add(_a(v,t[p])):n=n.add(_a(b,t[m]))}return e!==0n&&q("invalid wnaf"),{p:n,f:i}},li="openclaw-device-identity-v1";function Li(e){let t="";for(const n of e)t+=String.fromCharCode(n);return btoa(t).replaceAll("+","-").replaceAll("/","_").replace(/=+$/g,"")}function cl(e){const t=e.replaceAll("-","+").replaceAll("_","/"),n=t+"=".repeat((4-t.length%4)%4),i=atob(n),s=new Uint8Array(i.length);for(let a=0;a<i.length;a+=1)s[a]=i.charCodeAt(a);return s}function od(e){return Array.from(e).map(t=>t.toString(16).padStart(2,"0")).join("")}async function dl(e){const t=await crypto.subtle.digest("SHA-256",e.slice().buffer);return od(new Uint8Array(t))}async function ld(){const e=nd.randomSecretKey(),t=await Jc(e);return{deviceId:await dl(t),publicKey:Li(t),privateKey:Li(e)}}async function ps(){try{const n=localStorage.getItem(li);if(n){const i=JSON.parse(n);if(i?.version===1&&typeof i.deviceId=="string"&&typeof i.publicKey=="string"&&typeof i.privateKey=="string"){const s=await dl(cl(i.publicKey));if(s!==i.deviceId){const a={...i,deviceId:s};return localStorage.setItem(li,JSON.stringify(a)),{deviceId:s,publicKey:i.publicKey,privateKey:i.privateKey}}return{deviceId:i.deviceId,publicKey:i.publicKey,privateKey:i.privateKey}}}}catch{}const e=await ld(),t={version:1,deviceId:e.deviceId,publicKey:e.publicKey,privateKey:e.privateKey,createdAtMs:Date.now()};return localStorage.setItem(li,JSON.stringify(t)),e}async function rd(e,t){const n=cl(e),i=new TextEncoder().encode(t),s=await ed(i,n);return Li(s)}async function Ne(e,t){if(!(!e.client||!e.connected)&&!e.devicesLoading){e.devicesLoading=!0,t?.quiet||(e.devicesError=null);try{const n=await e.client.request("device.pair.list",{});e.devicesList={pending:Array.isArray(n?.pending)?n.pending:[],paired:Array.isArray(n?.paired)?n.paired:[]}}catch(n){t?.quiet||(e.devicesError=String(n))}finally{e.devicesLoading=!1}}}async function cd(e,t){if(!(!e.client||!e.connected))try{await e.client.request("device.pair.approve",{requestId:t}),await Ne(e)}catch(n){e.devicesError=String(n)}}async function dd(e,t){if(!(!e.client||!e.connected||!window.confirm("Reject this device pairing request?")))try{await e.client.request("device.pair.reject",{requestId:t}),await Ne(e)}catch(i){e.devicesError=String(i)}}async function ud(e,t){if(!(!e.client||!e.connected))try{const n=await e.client.request("device.token.rotate",t);if(n?.token){const i=await ps(),s=n.role??t.role;(n.deviceId===i.deviceId||t.deviceId===i.deviceId)&&Yo({deviceId:i.deviceId,role:s,token:n.token,scopes:n.scopes??t.scopes??[]}),window.prompt("New device token (copy and store securely):",n.token)}await Ne(e)}catch(n){e.devicesError=String(n)}}async function fd(e,t){if(!(!e.client||!e.connected||!window.confirm(`Revoke token for ${t.deviceId} (${t.role})?`)))try{await e.client.request("device.token.revoke",t);const i=await ps();t.deviceId===i.deviceId&&Qo({deviceId:i.deviceId,role:t.role}),await Ne(e)}catch(i){e.devicesError=String(i)}}function pd(e){if(!e||e.kind==="gateway")return{method:"exec.approvals.get",params:{}};const t=e.nodeId.trim();return t?{method:"exec.approvals.node.get",params:{nodeId:t}}:null}function gd(e,t){if(!e||e.kind==="gateway")return{method:"exec.approvals.set",params:t};const n=e.nodeId.trim();return n?{method:"exec.approvals.node.set",params:{...t,nodeId:n}}:null}async function gs(e,t){if(!(!e.client||!e.connected)&&!e.execApprovalsLoading){e.execApprovalsLoading=!0,e.lastError=null;try{const n=pd(t);if(!n){e.lastError="Select a node before loading exec approvals.";return}const i=await e.client.request(n.method,n.params);hd(e,i)}catch(n){e.lastError=String(n)}finally{e.execApprovalsLoading=!1}}}function hd(e,t){e.execApprovalsSnapshot=t,e.execApprovalsDirty||(e.execApprovalsForm=Ve(t.file??{}))}async function vd(e,t){if(!(!e.client||!e.connected)){e.execApprovalsSaving=!0,e.lastError=null;try{const n=e.execApprovalsSnapshot?.hash;if(!n){e.lastError="Exec approvals hash missing; reload and retry.";return}const i=e.execApprovalsForm??e.execApprovalsSnapshot?.file??{},s=gd(t,{file:i,baseHash:n});if(!s){e.lastError="Select a node before saving exec approvals.";return}await e.client.request(s.method,s.params),e.execApprovalsDirty=!1,await gs(e,t)}catch(n){e.lastError=String(n)}finally{e.execApprovalsSaving=!1}}}function md(e,t,n){const i=Ve(e.execApprovalsForm??e.execApprovalsSnapshot?.file??{});Fo(i,t,n),e.execApprovalsForm=i,e.execApprovalsDirty=!0}function yd(e,t){const n=Ve(e.execApprovalsForm??e.execApprovalsSnapshot?.file??{});No(n,t),e.execApprovalsForm=n,e.execApprovalsDirty=!0}async function hs(e){if(!(!e.client||!e.connected)&&!e.presenceLoading){e.presenceLoading=!0,e.presenceError=null,e.presenceStatus=null;try{const t=await e.client.request("system-presence",{});Array.isArray(t)?(e.presenceEntries=t,e.presenceStatus=t.length===0?"No instances yet.":null):(e.presenceEntries=[],e.presenceStatus="No presence payload.")}catch(t){e.presenceError=String(t)}finally{e.presenceLoading=!1}}}async function Ze(e,t){if(!(!e.client||!e.connected)&&!e.sessionsLoading){e.sessionsLoading=!0,e.sessionsError=null;try{const n=t?.includeGlobal??e.sessionsIncludeGlobal,i=t?.includeUnknown??e.sessionsIncludeUnknown,s=t?.activeMinutes??yn(e.sessionsFilterActive,0),a=t?.limit??yn(e.sessionsFilterLimit,0),o={includeGlobal:n,includeUnknown:i};s>0&&(o.activeMinutes=s),a>0&&(o.limit=a);const r=await e.client.request("sessions.list",o);r&&(e.sessionsResult=r)}catch(n){e.sessionsError=String(n)}finally{e.sessionsLoading=!1}}}async function bd(e,t,n){if(!e.client||!e.connected)return;const i={key:t};"label"in n&&(i.label=n.label),"thinkingLevel"in n&&(i.thinkingLevel=n.thinkingLevel),"verboseLevel"in n&&(i.verboseLevel=n.verboseLevel),"reasoningLevel"in n&&(i.reasoningLevel=n.reasoningLevel);try{await e.client.request("sessions.patch",i),await Ze(e)}catch(s){e.sessionsError=String(s)}}async function $d(e,t){if(!(!e.client||!e.connected||e.sessionsLoading||!window.confirm(`Delete session "${t}"?

Deletes the session entry and archives its transcript.`))){e.sessionsLoading=!0,e.sessionsError=null;try{await e.client.request("sessions.delete",{key:t,deleteTranscript:!0}),await Ze(e)}catch(i){e.sessionsError=String(i)}finally{e.sessionsLoading=!1}}}function ft(e,t,n){if(!t.trim())return;const i={...e.skillMessages};n?i[t]=n:delete i[t],e.skillMessages=i}function Pn(e){return e instanceof Error?e.message:String(e)}async function Ht(e,t){if(t?.clearMessages&&Object.keys(e.skillMessages).length>0&&(e.skillMessages={}),!(!e.client||!e.connected)&&!e.skillsLoading){e.skillsLoading=!0,e.skillsError=null;try{const n=await e.client.request("skills.status",{});n&&(e.skillsReport=n)}catch(n){e.skillsError=Pn(n)}finally{e.skillsLoading=!1}}}function wd(e,t,n){e.skillEdits={...e.skillEdits,[t]:n}}async function kd(e,t,n){if(!(!e.client||!e.connected)){e.skillsBusyKey=t,e.skillsError=null;try{await e.client.request("skills.update",{skillKey:t,enabled:n}),await Ht(e),ft(e,t,{kind:"success",message:n?"Skill enabled":"Skill disabled"})}catch(i){const s=Pn(i);e.skillsError=s,ft(e,t,{kind:"error",message:s})}finally{e.skillsBusyKey=null}}}async function Ad(e,t){if(!(!e.client||!e.connected)){e.skillsBusyKey=t,e.skillsError=null;try{const n=e.skillEdits[t]??"";await e.client.request("skills.update",{skillKey:t,apiKey:n}),await Ht(e),ft(e,t,{kind:"success",message:"API key saved"})}catch(n){const i=Pn(n);e.skillsError=i,ft(e,t,{kind:"error",message:i})}finally{e.skillsBusyKey=null}}}async function xd(e,t,n,i){if(!(!e.client||!e.connected)){e.skillsBusyKey=t,e.skillsError=null;try{const s=await e.client.request("skills.install",{name:n,installId:i,timeoutMs:12e4});await Ht(e),ft(e,t,{kind:"success",message:s?.message??"Installed"})}catch(s){const a=Pn(s);e.skillsError=a,ft(e,t,{kind:"error",message:a})}finally{e.skillsBusyKey=null}}}const Sd=[{label:"Chat",tabs:["chat"]},{label:"Control",tabs:["overview","channels","instances","sessions","cron"]},{label:"Agent",tabs:["agents","skills","nodes"]},{label:"Settings",tabs:["config","debug","logs"]}],ul={agents:"/agents",overview:"/overview",channels:"/channels",instances:"/instances",sessions:"/sessions",cron:"/cron",skills:"/skills",nodes:"/nodes",chat:"/chat",config:"/config",debug:"/debug",logs:"/logs"},fl=new Map(Object.entries(ul).map(([e,t])=>[t,e]));function jt(e){if(!e)return"";let t=e.trim();return t.startsWith("/")||(t=`/${t}`),t==="/"?"":(t.endsWith("/")&&(t=t.slice(0,-1)),t)}function Ot(e){if(!e)return"/";let t=e.trim();return t.startsWith("/")||(t=`/${t}`),t.length>1&&t.endsWith("/")&&(t=t.slice(0,-1)),t}function vs(e,t=""){const n=jt(t),i=ul[e];return n?`${n}${i}`:i}function pl(e,t=""){const n=jt(t);let i=e||"/";n&&(i===n?i="/":i.startsWith(`${n}/`)&&(i=i.slice(n.length)));let s=Ot(i).toLowerCase();return s.endsWith("/index.html")&&(s="/"),s==="/"?"chat":fl.get(s)??null}function _d(e){let t=Ot(e);if(t.endsWith("/index.html")&&(t=Ot(t.slice(0,-11))),t==="/")return"";const n=t.split("/").filter(Boolean);if(n.length===0)return"";for(let i=0;i<n.length;i++){const s=`/${n.slice(i).join("/")}`.toLowerCase();if(fl.has(s)){const a=n.slice(0,i);return a.length?`/${a.join("/")}`:""}}return`/${n.join("/")}`}function Cd(e){switch(e){case"agents":return"folder";case"chat":return"messageSquare";case"overview":return"barChart";case"channels":return"link";case"instances":return"radio";case"sessions":return"fileText";case"cron":return"loader";case"skills":return"zap";case"nodes":return"monitor";case"config":return"settings";case"debug":return"bug";case"logs":return"scrollText";default:return"folder"}}function Ii(e){switch(e){case"agents":return"Agents";case"overview":return"Overview";case"channels":return"Channels";case"instances":return"Instances";case"sessions":return"Sessions";case"cron":return"Cron Jobs";case"skills":return"Skills";case"nodes":return"Nodes";case"chat":return"Chat";case"config":return"Config";case"debug":return"Debug";case"logs":return"Logs";default:return"Control"}}function Ed(e){switch(e){case"agents":return"Manage agent workspaces, tools, and identities.";case"overview":return"Gateway status, entry points, and a fast health read.";case"channels":return"Manage channels and settings.";case"instances":return"Presence beacons from connected clients and nodes.";case"sessions":return"Inspect active sessions and adjust per-session defaults.";case"cron":return"Schedule wakeups and recurring agent runs.";case"skills":return"Manage skill availability and API key injection.";case"nodes":return"Paired devices, capabilities, and command exposure.";case"chat":return"Direct gateway chat session for quick interventions.";case"config":return"Edit ~/.openclaw/openclaw.json safely.";case"debug":return"Gateway snapshots, events, and manual RPC calls.";case"logs":return"Live tail of the gateway file logs.";default:return""}}const gl="openclaw.control.settings.v1";function Td(){const t={gatewayUrl:`${location.protocol==="https:"?"wss":"ws"}://${location.host}`,token:"",sessionKey:"main",lastActiveSessionKey:"main",theme:"system",chatFocusMode:!1,chatShowThinking:!0,splitRatio:.6,navCollapsed:!1,navGroupsCollapsed:{}};try{const n=localStorage.getItem(gl);if(!n)return t;const i=JSON.parse(n);return{gatewayUrl:typeof i.gatewayUrl=="string"&&i.gatewayUrl.trim()?i.gatewayUrl.trim():t.gatewayUrl,token:typeof i.token=="string"?i.token:t.token,sessionKey:typeof i.sessionKey=="string"&&i.sessionKey.trim()?i.sessionKey.trim():t.sessionKey,lastActiveSessionKey:typeof i.lastActiveSessionKey=="string"&&i.lastActiveSessionKey.trim()?i.lastActiveSessionKey.trim():typeof i.sessionKey=="string"&&i.sessionKey.trim()||t.lastActiveSessionKey,theme:i.theme==="light"||i.theme==="dark"||i.theme==="system"?i.theme:t.theme,chatFocusMode:typeof i.chatFocusMode=="boolean"?i.chatFocusMode:t.chatFocusMode,chatShowThinking:typeof i.chatShowThinking=="boolean"?i.chatShowThinking:t.chatShowThinking,splitRatio:typeof i.splitRatio=="number"&&i.splitRatio>=.4&&i.splitRatio<=.7?i.splitRatio:t.splitRatio,navCollapsed:typeof i.navCollapsed=="boolean"?i.navCollapsed:t.navCollapsed,navGroupsCollapsed:typeof i.navGroupsCollapsed=="object"&&i.navGroupsCollapsed!==null?i.navGroupsCollapsed:t.navGroupsCollapsed}}catch{return t}}function Ld(e){localStorage.setItem(gl,JSON.stringify(e))}const tn=e=>Number.isNaN(e)?.5:e<=0?0:e>=1?1:e,Id=()=>typeof window>"u"||typeof window.matchMedia!="function"?!1:window.matchMedia("(prefers-reduced-motion: reduce)").matches??!1,nn=e=>{e.classList.remove("theme-transition"),e.style.removeProperty("--theme-switch-x"),e.style.removeProperty("--theme-switch-y")},Rd=({nextTheme:e,applyTheme:t,context:n,currentTheme:i})=>{if(i===e)return;const s=globalThis.document??null;if(!s){t();return}const a=s.documentElement,o=s,r=Id();if(!!o.startViewTransition&&!r){let u=.5,f=.5;if(n?.pointerClientX!==void 0&&n?.pointerClientY!==void 0&&typeof window<"u")u=tn(n.pointerClientX/window.innerWidth),f=tn(n.pointerClientY/window.innerHeight);else if(n?.element){const p=n.element.getBoundingClientRect();p.width>0&&p.height>0&&typeof window<"u"&&(u=tn((p.left+p.width/2)/window.innerWidth),f=tn((p.top+p.height/2)/window.innerHeight))}a.style.setProperty("--theme-switch-x",`${u*100}%`),a.style.setProperty("--theme-switch-y",`${f*100}%`),a.classList.add("theme-transition");try{const p=o.startViewTransition?.(()=>{t()});p?.finished?p.finished.finally(()=>nn(a)):nn(a)}catch{nn(a),t()}return}t(),nn(a)};function Md(){return typeof window>"u"||typeof window.matchMedia!="function"||window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"}function ms(e){return e==="system"?Md():e}function Pd(){try{return window.top===window.self}catch{return!1}}function Fd(e){const t=e.trim();if(!t)return null;try{const n=new URL(t);return n.protocol!=="ws:"&&n.protocol!=="wss:"?null:t}catch{return null}}function Pe(e,t){const n={...t,lastActiveSessionKey:t.lastActiveSessionKey?.trim()||t.sessionKey.trim()||"main"};e.settings=n,Ld(n),t.theme!==e.theme&&(e.theme=t.theme,Fn(e,ms(t.theme))),e.applySessionKey=e.settings.lastActiveSessionKey}function hl(e,t){const n=t.trim();n&&e.settings.lastActiveSessionKey!==n&&Pe(e,{...e.settings,lastActiveSessionKey:n})}function Nd(e){if(!window.location.search)return;const t=new URLSearchParams(window.location.search),n=t.get("token"),i=t.get("password"),s=t.get("session"),a=t.get("gatewayUrl");let o=!1;if(n!=null){const c=n.trim();c&&c!==e.settings.token&&Pe(e,{...e.settings,token:c}),t.delete("token"),o=!0}if(i!=null){const c=i.trim();c&&(e.password=c),t.delete("password"),o=!0}if(s!=null){const c=s.trim();c&&(e.sessionKey=c,Pe(e,{...e.settings,sessionKey:c,lastActiveSessionKey:c}))}if(a!=null){const c=Fd(a);c&&c!==e.settings.gatewayUrl&&Pd()&&(e.pendingGatewayUrl=c),t.delete("gatewayUrl"),o=!0}if(!o)return;const r=new URL(window.location.href);r.search=t.toString(),window.history.replaceState({},"",r.toString())}function Dd(e,t){e.tab!==t&&(e.tab=t),t==="chat"&&(e.chatHasAutoScrolled=!1),t==="logs"?is(e):ss(e),t==="debug"?as(e):os(e),ys(e),ml(e,t,!1)}function Od(e,t,n){Rd({nextTheme:t,applyTheme:()=>{e.theme=t,Pe(e,{...e.settings,theme:t}),Fn(e,ms(t))},context:n,currentTheme:e.theme})}async function ys(e){if(e.tab==="overview"&&await yl(e),e.tab==="channels"&&await qd(e),e.tab==="instances"&&await hs(e),e.tab==="sessions"&&await Ze(e),e.tab==="cron"&&await wn(e),e.tab==="skills"&&await Ht(e),e.tab==="agents"){const t=e;await ls(t),await ge(t);const n=t.agentsList?.agents?.map(s=>s.id)??[];n.length>0&&Ho(t,n);const i=t.agentsSelectedId??t.agentsList?.defaultId??t.agentsList?.agents?.[0]?.id;i&&(zo(t,i),t.agentsPanel==="skills"&&pn(t,i),t.agentsPanel==="channels"&&se(t,!1),t.agentsPanel==="cron"&&wn(e))}e.tab==="nodes"&&(await In(e),await Ne(e),await ge(e),await gs(e)),e.tab==="chat"&&(await Sl(e),Kt(e,!e.chatHasAutoScrolled)),e.tab==="config"&&(await Do(e),await ge(e)),e.tab==="debug"&&(await Ln(e),e.eventLog=e.eventLogBuffer),e.tab==="logs"&&(e.logsAtBottom=!0,await ns(e,{reset:!0}),Ko(e,!0))}function Bd(){if(typeof window>"u")return"";const e=window.__OPENCLAW_CONTROL_UI_BASE_PATH__;return typeof e=="string"&&e.trim()?jt(e):_d(window.location.pathname)}function Ud(e){e.theme=e.settings.theme??"system",Fn(e,ms(e.theme))}function Fn(e,t){if(e.themeResolved=t,typeof document>"u")return;const n=document.documentElement;n.dataset.theme=t,n.style.colorScheme=t}function Kd(e){if(typeof window>"u"||typeof window.matchMedia!="function")return;if(e.themeMedia=window.matchMedia("(prefers-color-scheme: dark)"),e.themeMediaHandler=n=>{e.theme==="system"&&Fn(e,n.matches?"dark":"light")},typeof e.themeMedia.addEventListener=="function"){e.themeMedia.addEventListener("change",e.themeMediaHandler);return}e.themeMedia.addListener(e.themeMediaHandler)}function zd(e){if(!e.themeMedia||!e.themeMediaHandler)return;if(typeof e.themeMedia.removeEventListener=="function"){e.themeMedia.removeEventListener("change",e.themeMediaHandler);return}e.themeMedia.removeListener(e.themeMediaHandler),e.themeMedia=null,e.themeMediaHandler=null}function Hd(e,t){if(typeof window>"u")return;const n=pl(window.location.pathname,e.basePath)??"chat";vl(e,n),ml(e,n,t)}function jd(e){if(typeof window>"u")return;const t=pl(window.location.pathname,e.basePath);if(!t)return;const i=new URL(window.location.href).searchParams.get("session")?.trim();i&&(e.sessionKey=i,Pe(e,{...e.settings,sessionKey:i,lastActiveSessionKey:i})),vl(e,t)}function vl(e,t){e.tab!==t&&(e.tab=t),t==="chat"&&(e.chatHasAutoScrolled=!1),t==="logs"?is(e):ss(e),t==="debug"?as(e):os(e),e.connected&&ys(e)}function ml(e,t,n){if(typeof window>"u")return;const i=Ot(vs(t,e.basePath)),s=Ot(window.location.pathname),a=new URL(window.location.href);t==="chat"&&e.sessionKey?a.searchParams.set("session",e.sessionKey):a.searchParams.delete("session"),s!==i&&(a.pathname=i),n?window.history.replaceState({},"",a.toString()):window.history.pushState({},"",a.toString())}function Gd(e,t){if(typeof window>"u")return;const n=new URL(window.location.href);n.searchParams.set("session",e),window.history.replaceState({},"",n.toString())}async function yl(e){await Promise.all([se(e,!1),hs(e),Ze(e),zt(e),Ln(e)])}async function qd(e){await Promise.all([se(e,!0),Do(e),ge(e)])}async function wn(e){await Promise.all([se(e,!1),zt(e),Rn(e)])}const Ca=50,Wd=80,Vd=12e4;function Yd(e){if(!e||typeof e!="object")return null;const t=e;if(typeof t.text=="string")return t.text;const n=t.content;if(!Array.isArray(n))return null;const i=n.map(s=>{if(!s||typeof s!="object")return null;const a=s;return a.type==="text"&&typeof a.text=="string"?a.text:null}).filter(s=>!!s);return i.length===0?null:i.join(`
`)}function Ea(e){if(e==null)return null;if(typeof e=="number"||typeof e=="boolean")return String(e);const t=Yd(e);let n;if(typeof e=="string")n=e;else if(t)n=t;else try{n=JSON.stringify(e,null,2)}catch{n=String(e)}const i=Go(n,Vd);return i.truncated?`${i.text}

… truncated (${i.total} chars, showing first ${i.text.length}).`:i.text}function Qd(e){const t=[];return t.push({type:"toolcall",name:e.name,arguments:e.args??{}}),e.output&&t.push({type:"toolresult",name:e.name,text:e.output}),{role:"assistant",toolCallId:e.toolCallId,runId:e.runId,content:t,timestamp:e.startedAt}}function Jd(e){if(e.toolStreamOrder.length<=Ca)return;const t=e.toolStreamOrder.length-Ca,n=e.toolStreamOrder.splice(0,t);for(const i of n)e.toolStreamById.delete(i)}function Zd(e){e.chatToolMessages=e.toolStreamOrder.map(t=>e.toolStreamById.get(t)?.message).filter(t=>!!t)}function Ri(e){e.toolStreamSyncTimer!=null&&(clearTimeout(e.toolStreamSyncTimer),e.toolStreamSyncTimer=null),Zd(e)}function Xd(e,t=!1){if(t){Ri(e);return}e.toolStreamSyncTimer==null&&(e.toolStreamSyncTimer=window.setTimeout(()=>Ri(e),Wd))}function Nn(e){e.toolStreamById.clear(),e.toolStreamOrder=[],e.chatToolMessages=[],Ri(e)}const eu=5e3;function tu(e,t){const n=t.data??{},i=typeof n.phase=="string"?n.phase:"";e.compactionClearTimer!=null&&(window.clearTimeout(e.compactionClearTimer),e.compactionClearTimer=null),i==="start"?e.compactionStatus={active:!0,startedAt:Date.now(),completedAt:null}:i==="end"&&(e.compactionStatus={active:!1,startedAt:e.compactionStatus?.startedAt??null,completedAt:Date.now()},e.compactionClearTimer=window.setTimeout(()=>{e.compactionStatus=null,e.compactionClearTimer=null},eu))}function nu(e,t){if(!t)return;if(t.stream==="compaction"){tu(e,t);return}if(t.stream!=="tool")return;const n=typeof t.sessionKey=="string"?t.sessionKey:void 0;if(n&&n!==e.sessionKey||!n&&e.chatRunId&&t.runId!==e.chatRunId||e.chatRunId&&t.runId!==e.chatRunId||!e.chatRunId)return;const i=t.data??{},s=typeof i.toolCallId=="string"?i.toolCallId:"";if(!s)return;const a=typeof i.name=="string"?i.name:"tool",o=typeof i.phase=="string"?i.phase:"",r=o==="start"?i.args:void 0,c=o==="update"?Ea(i.partialResult):o==="result"?Ea(i.result):void 0,u=Date.now();let f=e.toolStreamById.get(s);f?(f.name=a,r!==void 0&&(f.args=r),c!==void 0&&(f.output=c||void 0),f.updatedAt=u):(f={toolCallId:s,runId:t.runId,sessionKey:n,name:a,args:r,output:c||void 0,startedAt:typeof t.ts=="number"?t.ts:u,updatedAt:u,message:{}},e.toolStreamById.set(s,f),e.toolStreamOrder.push(s)),f.message=Qd(f),Jd(e),Xd(e,o==="result")}const iu=/^\[([^\]]+)\]\s*/,su=["WebChat","WhatsApp","Telegram","Signal","Slack","Discord","iMessage","Teams","Matrix","Zalo","Zalo Personal","BlueBubbles"],ri=new WeakMap,ci=new WeakMap;function au(e){return/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z\b/.test(e)||/\d{4}-\d{2}-\d{2} \d{2}:\d{2}\b/.test(e)?!0:su.some(t=>e.startsWith(`${t} `))}function di(e){const t=e.match(iu);if(!t)return e;const n=t[1]??"";return au(n)?e.slice(t[0].length):e}function Mi(e){const t=e,n=typeof t.role=="string"?t.role:"",i=t.content;if(typeof i=="string")return n==="assistant"?ii(i):di(i);if(Array.isArray(i)){const s=i.map(a=>{const o=a;return o.type==="text"&&typeof o.text=="string"?o.text:null}).filter(a=>typeof a=="string");if(s.length>0){const a=s.join(`
`);return n==="assistant"?ii(a):di(a)}}return typeof t.text=="string"?n==="assistant"?ii(t.text):di(t.text):null}function bl(e){if(!e||typeof e!="object")return Mi(e);const t=e;if(ri.has(t))return ri.get(t)??null;const n=Mi(e);return ri.set(t,n),n}function Ta(e){const n=e.content,i=[];if(Array.isArray(n))for(const r of n){const c=r;if(c.type==="thinking"&&typeof c.thinking=="string"){const u=c.thinking.trim();u&&i.push(u)}}if(i.length>0)return i.join(`
`);const s=lu(e);if(!s)return null;const o=[...s.matchAll(/<\s*think(?:ing)?\s*>([\s\S]*?)<\s*\/\s*think(?:ing)?\s*>/gi)].map(r=>(r[1]??"").trim()).filter(Boolean);return o.length>0?o.join(`
`):null}function ou(e){if(!e||typeof e!="object")return Ta(e);const t=e;if(ci.has(t))return ci.get(t)??null;const n=Ta(e);return ci.set(t,n),n}function lu(e){const t=e,n=t.content;if(typeof n=="string")return n;if(Array.isArray(n)){const i=n.map(s=>{const a=s;return a.type==="text"&&typeof a.text=="string"?a.text:null}).filter(s=>typeof s=="string");if(i.length>0)return i.join(`
`)}return typeof t.text=="string"?t.text:null}function ru(e){const t=e.trim();if(!t)return"";const n=t.split(/\r?\n/).map(i=>i.trim()).filter(Boolean).map(i=>`_${i}_`);return n.length?["_Reasoning:_",...n].join(`
`):""}let La=!1;function Ia(e){e[6]=e[6]&15|64,e[8]=e[8]&63|128;let t="";for(let n=0;n<e.length;n++)t+=e[n].toString(16).padStart(2,"0");return`${t.slice(0,8)}-${t.slice(8,12)}-${t.slice(12,16)}-${t.slice(16,20)}-${t.slice(20)}`}function cu(){const e=new Uint8Array(16),t=Date.now();for(let n=0;n<e.length;n++)e[n]=Math.floor(Math.random()*256);return e[0]^=t&255,e[1]^=t>>>8&255,e[2]^=t>>>16&255,e[3]^=t>>>24&255,e}function du(){La||(La=!0,console.warn("[uuid] crypto API missing; falling back to weak randomness"))}function bs(e=globalThis.crypto){if(e&&typeof e.randomUUID=="function")return e.randomUUID();if(e&&typeof e.getRandomValues=="function"){const t=new Uint8Array(16);return e.getRandomValues(t),Ia(t)}return du(),Ia(cu())}async function Bt(e){if(!(!e.client||!e.connected)){e.chatLoading=!0,e.lastError=null;try{const t=await e.client.request("chat.history",{sessionKey:e.sessionKey,limit:200});e.chatMessages=Array.isArray(t.messages)?t.messages:[],e.chatThinkingLevel=t.thinkingLevel??null}catch(t){e.lastError=String(t)}finally{e.chatLoading=!1}}}function uu(e){const t=/^data:([^;]+);base64,(.+)$/.exec(e);return t?{mimeType:t[1],content:t[2]}:null}async function fu(e,t,n){if(!e.client||!e.connected)return null;const i=t.trim(),s=n&&n.length>0;if(!i&&!s)return null;const a=Date.now(),o=[];if(i&&o.push({type:"text",text:i}),s)for(const u of n)o.push({type:"image",source:{type:"base64",media_type:u.mimeType,data:u.dataUrl}});e.chatMessages=[...e.chatMessages,{role:"user",content:o,timestamp:a}],e.chatSending=!0,e.lastError=null;const r=bs();e.chatRunId=r,e.chatStream="",e.chatStreamStartedAt=a;const c=s?n.map(u=>{const f=uu(u.dataUrl);return f?{type:"image",mimeType:f.mimeType,content:f.content}:null}).filter(u=>u!==null):void 0;try{return await e.client.request("chat.send",{sessionKey:e.sessionKey,message:i,deliver:!1,idempotencyKey:r,attachments:c}),r}catch(u){const f=String(u);return e.chatRunId=null,e.chatStream=null,e.chatStreamStartedAt=null,e.lastError=f,e.chatMessages=[...e.chatMessages,{role:"assistant",content:[{type:"text",text:"Error: "+f}],timestamp:Date.now()}],null}finally{e.chatSending=!1}}async function pu(e){if(!e.client||!e.connected)return!1;const t=e.chatRunId;try{return await e.client.request("chat.abort",t?{sessionKey:e.sessionKey,runId:t}:{sessionKey:e.sessionKey}),!0}catch(n){return e.lastError=String(n),!1}}function gu(e,t){if(!t||t.sessionKey!==e.sessionKey)return null;if(t.runId&&e.chatRunId&&t.runId!==e.chatRunId)return t.state==="final"?"final":null;if(t.state==="delta"){const n=Mi(t.message);if(typeof n=="string"){const i=e.chatStream??"";(!i||n.length>=i.length)&&(e.chatStream=n)}}else t.state==="final"||t.state==="aborted"?(e.chatStream=null,e.chatRunId=null,e.chatStreamStartedAt=null):t.state==="error"&&(e.chatStream=null,e.chatRunId=null,e.chatStreamStartedAt=null,e.lastError=t.errorMessage??"chat error");return t.state}const $l=120;function wl(e){return e.chatSending||!!e.chatRunId}function hu(e){const t=e.trim();if(!t)return!1;const n=t.toLowerCase();return n==="/stop"?!0:n==="stop"||n==="esc"||n==="abort"||n==="wait"||n==="exit"}function vu(e){const t=e.trim();if(!t)return!1;const n=t.toLowerCase();return n==="/new"||n==="/reset"?!0:n.startsWith("/new ")||n.startsWith("/reset ")}async function kl(e){e.connected&&(e.chatMessage="",await pu(e))}function mu(e,t,n,i){const s=t.trim(),a=!!(n&&n.length>0);!s&&!a||(e.chatQueue=[...e.chatQueue,{id:bs(),text:s,createdAt:Date.now(),attachments:a?n?.map(o=>({...o})):void 0,refreshSessions:i}])}async function Al(e,t,n){Nn(e);const i=await fu(e,t,n?.attachments),s=!!i;return!s&&n?.previousDraft!=null&&(e.chatMessage=n.previousDraft),!s&&n?.previousAttachments&&(e.chatAttachments=n.previousAttachments),s&&hl(e,e.sessionKey),s&&n?.restoreDraft&&n.previousDraft?.trim()&&(e.chatMessage=n.previousDraft),s&&n?.restoreAttachments&&n.previousAttachments?.length&&(e.chatAttachments=n.previousAttachments),Kt(e),s&&!e.chatRunId&&xl(e),s&&n?.refreshSessions&&i&&e.refreshSessionsAfterChat.add(i),s}async function xl(e){if(!e.connected||wl(e))return;const[t,...n]=e.chatQueue;if(!t)return;e.chatQueue=n,await Al(e,t.text,{attachments:t.attachments,refreshSessions:t.refreshSessions})||(e.chatQueue=[t,...e.chatQueue])}function yu(e,t){e.chatQueue=e.chatQueue.filter(n=>n.id!==t)}async function bu(e,t,n){if(!e.connected)return;const i=e.chatMessage,s=(t??e.chatMessage).trim(),a=e.chatAttachments??[],o=t==null?a:[],r=o.length>0;if(!s&&!r)return;if(hu(s)){await kl(e);return}const c=vu(s);if(t==null&&(e.chatMessage="",e.chatAttachments=[]),wl(e)){mu(e,s,o,c);return}await Al(e,s,{previousDraft:t==null?i:void 0,restoreDraft:!!(t&&n?.restoreDraft),attachments:r?o:void 0,previousAttachments:t==null?a:void 0,restoreAttachments:!!(t&&n?.restoreDraft),refreshSessions:c})}async function Sl(e){await Promise.all([Bt(e),Ze(e,{activeMinutes:$l}),Pi(e)]),Kt(e)}const $u=xl;function wu(e){const t=Uo(e.sessionKey);return t?.agentId?t.agentId:e.hello?.snapshot?.sessionDefaults?.defaultAgentId?.trim()||"main"}function ku(e,t){const n=jt(e),i=encodeURIComponent(t);return n?`${n}/avatar/${i}?meta=1`:`/avatar/${i}?meta=1`}async function Pi(e){if(!e.connected){e.chatAvatarUrl=null;return}const t=wu(e);if(!t){e.chatAvatarUrl=null;return}e.chatAvatarUrl=null;const n=ku(e.basePath,t);try{const i=await fetch(n,{method:"GET"});if(!i.ok){e.chatAvatarUrl=null;return}const s=await i.json(),a=typeof s.avatarUrl=="string"?s.avatarUrl.trim():"";e.chatAvatarUrl=a||null}catch{e.chatAvatarUrl=null}}const Au={trace:!0,debug:!0,info:!0,warn:!0,error:!0,fatal:!0},xu={name:"",description:"",agentId:"",enabled:!0,scheduleKind:"every",scheduleAt:"",everyAmount:"30",everyUnit:"minutes",cronExpr:"0 7 * * *",cronTz:"",sessionTarget:"isolated",wakeMode:"next-heartbeat",payloadKind:"agentTurn",payloadText:"",deliveryMode:"announce",deliveryChannel:"last",deliveryTo:"",timeoutSeconds:""},Su=50,_u=200,Cu="Assistant";function Ra(e,t){if(typeof e!="string")return;const n=e.trim();if(n)return n.length<=t?n:n.slice(0,t)}function Fi(e){const t=Ra(e?.name,Su)??Cu,n=Ra(e?.avatar??void 0,_u)??null;return{agentId:typeof e?.agentId=="string"&&e.agentId.trim()?e.agentId.trim():null,name:t,avatar:n}}function Eu(){return Fi(typeof window>"u"?{}:{name:window.__OPENCLAW_ASSISTANT_NAME__,avatar:window.__OPENCLAW_ASSISTANT_AVATAR__})}async function _l(e,t){if(!e.client||!e.connected)return;const n=e.sessionKey.trim(),i=n?{sessionKey:n}:{};try{const s=await e.client.request("agent.identity.get",i);if(!s)return;const a=Fi(s);e.assistantName=a.name,e.assistantAvatar=a.avatar,e.assistantAgentId=a.agentId??null}catch{}}function Ni(e){return typeof e=="object"&&e!==null}function Tu(e){if(!Ni(e))return null;const t=typeof e.id=="string"?e.id.trim():"",n=e.request;if(!t||!Ni(n))return null;const i=typeof n.command=="string"?n.command.trim():"";if(!i)return null;const s=typeof e.createdAtMs=="number"?e.createdAtMs:0,a=typeof e.expiresAtMs=="number"?e.expiresAtMs:0;return!s||!a?null:{id:t,request:{command:i,cwd:typeof n.cwd=="string"?n.cwd:null,host:typeof n.host=="string"?n.host:null,security:typeof n.security=="string"?n.security:null,ask:typeof n.ask=="string"?n.ask:null,agentId:typeof n.agentId=="string"?n.agentId:null,resolvedPath:typeof n.resolvedPath=="string"?n.resolvedPath:null,sessionKey:typeof n.sessionKey=="string"?n.sessionKey:null},createdAtMs:s,expiresAtMs:a}}function Lu(e){if(!Ni(e))return null;const t=typeof e.id=="string"?e.id.trim():"";return t?{id:t,decision:typeof e.decision=="string"?e.decision:null,resolvedBy:typeof e.resolvedBy=="string"?e.resolvedBy:null,ts:typeof e.ts=="number"?e.ts:null}:null}function Cl(e){const t=Date.now();return e.filter(n=>n.expiresAtMs>t)}function Iu(e,t){const n=Cl(e).filter(i=>i.id!==t.id);return n.push(t),n}function Ma(e,t){return Cl(e).filter(n=>n.id!==t)}function Ru(e){const t=e.version??(e.nonce?"v2":"v1"),n=e.scopes.join(","),i=e.token??"",s=[t,e.deviceId,e.clientId,e.clientMode,e.role,n,String(e.signedAtMs),i];return t==="v2"&&s.push(e.nonce??""),s.join("|")}const Mu={CONTROL_UI:"openclaw-control-ui"},Pa=Mu,Fa={WEBCHAT:"webchat"},Pu=4008;class Fu{constructor(t){this.opts=t,this.ws=null,this.pending=new Map,this.closed=!1,this.lastSeq=null,this.connectNonce=null,this.connectSent=!1,this.connectTimer=null,this.backoffMs=800}start(){this.closed=!1,this.connect()}stop(){this.closed=!0,this.ws?.close(),this.ws=null,this.flushPending(new Error("gateway client stopped"))}get connected(){return this.ws?.readyState===WebSocket.OPEN}connect(){this.closed||(this.ws=new WebSocket(this.opts.url),this.ws.addEventListener("open",()=>this.queueConnect()),this.ws.addEventListener("message",t=>this.handleMessage(String(t.data??""))),this.ws.addEventListener("close",t=>{const n=String(t.reason??"");this.ws=null,this.flushPending(new Error(`gateway closed (${t.code}): ${n}`)),this.opts.onClose?.({code:t.code,reason:n}),this.scheduleReconnect()}),this.ws.addEventListener("error",()=>{}))}scheduleReconnect(){if(this.closed)return;const t=this.backoffMs;this.backoffMs=Math.min(this.backoffMs*1.7,15e3),window.setTimeout(()=>this.connect(),t)}flushPending(t){for(const[,n]of this.pending)n.reject(t);this.pending.clear()}async sendConnect(){if(this.connectSent)return;this.connectSent=!0,this.connectTimer!==null&&(window.clearTimeout(this.connectTimer),this.connectTimer=null);const t=typeof crypto<"u"&&!!crypto.subtle,n=["operator.admin","operator.approvals","operator.pairing"],i="operator";let s=null,a=!1,o=this.opts.token;if(t){s=await ps();const f=Dc({deviceId:s.deviceId,role:i})?.token;o=f??this.opts.token,a=!!(f&&this.opts.token)}const r=o||this.opts.password?{token:o,password:this.opts.password}:void 0;let c;if(t&&s){const f=Date.now(),p=this.connectNonce??void 0,m=Ru({deviceId:s.deviceId,clientId:this.opts.clientName??Pa.CONTROL_UI,clientMode:this.opts.mode??Fa.WEBCHAT,role:i,scopes:n,signedAtMs:f,token:o??null,nonce:p}),v=await rd(s.privateKey,m);c={id:s.deviceId,publicKey:s.publicKey,signature:v,signedAt:f,nonce:p}}const u={minProtocol:3,maxProtocol:3,client:{id:this.opts.clientName??Pa.CONTROL_UI,version:this.opts.clientVersion??"dev",platform:this.opts.platform??navigator.platform??"web",mode:this.opts.mode??Fa.WEBCHAT,instanceId:this.opts.instanceId},role:i,scopes:n,device:c,caps:[],auth:r,userAgent:navigator.userAgent,locale:navigator.language};this.request("connect",u).then(f=>{f?.auth?.deviceToken&&s&&Yo({deviceId:s.deviceId,role:f.auth.role??i,token:f.auth.deviceToken,scopes:f.auth.scopes??[]}),this.backoffMs=800,this.opts.onHello?.(f)}).catch(()=>{a&&s&&Qo({deviceId:s.deviceId,role:i}),this.ws?.close(Pu,"connect failed")})}handleMessage(t){let n;try{n=JSON.parse(t)}catch{return}const i=n;if(i.type==="event"){const s=n;if(s.event==="connect.challenge"){const o=s.payload,r=o&&typeof o.nonce=="string"?o.nonce:null;r&&(this.connectNonce=r,this.sendConnect());return}const a=typeof s.seq=="number"?s.seq:null;a!==null&&(this.lastSeq!==null&&a>this.lastSeq+1&&this.opts.onGap?.({expected:this.lastSeq+1,received:a}),this.lastSeq=a);try{this.opts.onEvent?.(s)}catch(o){console.error("[gateway] event handler error:",o)}return}if(i.type==="res"){const s=n,a=this.pending.get(s.id);if(!a)return;this.pending.delete(s.id),s.ok?a.resolve(s.payload):a.reject(new Error(s.error?.message??"request failed"));return}}request(t,n){if(!this.ws||this.ws.readyState!==WebSocket.OPEN)return Promise.reject(new Error("gateway not connected"));const i=bs(),s={type:"req",id:i,method:t,params:n},a=new Promise((o,r)=>{this.pending.set(i,{resolve:c=>o(c),reject:r})});return this.ws.send(JSON.stringify(s)),a}queueConnect(){this.connectNonce=null,this.connectSent=!1,this.connectTimer!==null&&window.clearTimeout(this.connectTimer),this.connectTimer=window.setTimeout(()=>{this.sendConnect()},750)}}function ui(e,t){const n=(e??"").trim(),i=t.mainSessionKey?.trim();if(!i)return n;if(!n)return i;const s=t.mainKey?.trim()||"main",a=t.defaultAgentId?.trim();return n==="main"||n===s||a&&(n===`agent:${a}:main`||n===`agent:${a}:${s}`)?i:n}function Nu(e,t){if(!t?.mainSessionKey)return;const n=ui(e.sessionKey,t),i=ui(e.settings.sessionKey,t),s=ui(e.settings.lastActiveSessionKey,t),a=n||i||e.sessionKey,o={...e.settings,sessionKey:i||a,lastActiveSessionKey:s||a},r=o.sessionKey!==e.settings.sessionKey||o.lastActiveSessionKey!==e.settings.lastActiveSessionKey;a!==e.sessionKey&&(e.sessionKey=a),r&&Pe(e,o)}function El(e){e.lastError=null,e.hello=null,e.connected=!1,e.execApprovalQueue=[],e.execApprovalError=null,e.client?.stop(),e.client=new Fu({url:e.settings.gatewayUrl,token:e.settings.token.trim()?e.settings.token:void 0,password:e.password.trim()?e.password:void 0,clientName:"openclaw-control-ui",mode:"webchat",onHello:t=>{e.connected=!0,e.lastError=null,e.hello=t,Bu(e,t),e.chatRunId=null,e.chatStream=null,e.chatStreamStartedAt=null,Nn(e),_l(e),ls(e),In(e,{quiet:!0}),Ne(e,{quiet:!0}),ys(e)},onClose:({code:t,reason:n})=>{e.connected=!1,t!==1012&&(e.lastError=`disconnected (${t}): ${n||"no reason"}`)},onEvent:t=>Du(e,t),onGap:({expected:t,received:n})=>{e.lastError=`event gap detected (expected seq ${t}, got ${n}); refresh recommended`}}),e.client.start()}function Du(e,t){try{Ou(e,t)}catch(n){console.error("[gateway] handleGatewayEvent error:",t.event,n)}}function Ou(e,t){if(e.eventLogBuffer=[{ts:Date.now(),event:t.event,payload:t.payload},...e.eventLogBuffer].slice(0,250),e.tab==="debug"&&(e.eventLog=e.eventLogBuffer),t.event==="agent"){if(e.onboarding)return;nu(e,t.payload);return}if(t.event==="chat"){const n=t.payload;n?.sessionKey&&hl(e,n.sessionKey);const i=gu(e,n);if(i==="final"||i==="error"||i==="aborted"){Nn(e),$u(e);const s=n?.runId;s&&e.refreshSessionsAfterChat.has(s)&&(e.refreshSessionsAfterChat.delete(s),i==="final"&&Ze(e,{activeMinutes:$l}))}i==="final"&&Bt(e);return}if(t.event==="presence"){const n=t.payload;n?.presence&&Array.isArray(n.presence)&&(e.presenceEntries=n.presence,e.presenceError=null,e.presenceStatus=null);return}if(t.event==="cron"&&e.tab==="cron"&&wn(e),(t.event==="device.pair.requested"||t.event==="device.pair.resolved")&&Ne(e,{quiet:!0}),t.event==="exec.approval.requested"){const n=Tu(t.payload);if(n){e.execApprovalQueue=Iu(e.execApprovalQueue,n),e.execApprovalError=null;const i=Math.max(0,n.expiresAtMs-Date.now()+500);window.setTimeout(()=>{e.execApprovalQueue=Ma(e.execApprovalQueue,n.id)},i)}return}if(t.event==="exec.approval.resolved"){const n=Lu(t.payload);n&&(e.execApprovalQueue=Ma(e.execApprovalQueue,n.id))}}function Bu(e,t){const n=t.snapshot;n?.presence&&Array.isArray(n.presence)&&(e.presenceEntries=n.presence),n?.health&&(e.debugHealth=n.health),n?.sessionDefaults&&Nu(e,n.sessionDefaults)}function Uu(e){e.basePath=Bd(),Nd(e),Hd(e,!0),Ud(e),Kd(e),window.addEventListener("popstate",e.popStateHandler),El(e),Sc(e),e.tab==="logs"&&is(e),e.tab==="debug"&&as(e)}function Ku(e){yc(e)}function zu(e){window.removeEventListener("popstate",e.popStateHandler),_c(e),ss(e),os(e),zd(e),e.topbarObserver?.disconnect(),e.topbarObserver=null}function Hu(e,t){if(e.tab==="chat"&&(t.has("chatMessages")||t.has("chatToolMessages")||t.has("chatStream")||t.has("chatLoading")||t.has("tab"))){const n=t.has("tab"),i=t.has("chatLoading")&&t.get("chatLoading")===!0&&!e.chatLoading;Kt(e,n||i||!e.chatHasAutoScrolled)}e.tab==="logs"&&(t.has("logsEntries")||t.has("logsAutoFollow")||t.has("tab"))&&e.logsAutoFollow&&e.logsAtBottom&&Ko(e,t.has("tab")||t.has("logsAutoFollow"))}const $s={CHILD:2},ws=e=>(...t)=>({_$litDirective$:e,values:t});let ks=class{constructor(t){}get _$AU(){return this._$AM._$AU}_$AT(t,n,i){this._$Ct=t,this._$AM=n,this._$Ci=i}_$AS(t,n){return this.update(t,n)}update(t,n){return this.render(...n)}};const{I:ju}=Kr,Na=e=>e,Gu=e=>e.strings===void 0,Da=()=>document.createComment(""),yt=(e,t,n)=>{const i=e._$AA.parentNode,s=t===void 0?e._$AB:t._$AA;if(n===void 0){const a=i.insertBefore(Da(),s),o=i.insertBefore(Da(),s);n=new ju(a,o,e,e.options)}else{const a=n._$AB.nextSibling,o=n._$AM,r=o!==e;if(r){let c;n._$AQ?.(e),n._$AM=e,n._$AP!==void 0&&(c=e._$AU)!==o._$AU&&n._$AP(c)}if(a!==s||r){let c=n._$AA;for(;c!==a;){const u=Na(c).nextSibling;Na(i).insertBefore(c,s),c=u}}}return n},Ke=(e,t,n=e)=>(e._$AI(t,n),e),qu={},Wu=(e,t=qu)=>e._$AH=t,Vu=e=>e._$AH,fi=e=>{e._$AR(),e._$AA.remove()};const Oa=(e,t,n)=>{const i=new Map;for(let s=t;s<=n;s++)i.set(e[s],s);return i},Tl=ws(class extends ks{constructor(e){if(super(e),e.type!==$s.CHILD)throw Error("repeat() can only be used in text expressions")}dt(e,t,n){let i;n===void 0?n=t:t!==void 0&&(i=t);const s=[],a=[];let o=0;for(const r of e)s[o]=i?i(r,o):o,a[o]=n(r,o),o++;return{values:a,keys:s}}render(e,t,n){return this.dt(e,t,n).values}update(e,[t,n,i]){const s=Vu(e),{values:a,keys:o}=this.dt(t,n,i);if(!Array.isArray(s))return this.ut=o,a;const r=this.ut??=[],c=[];let u,f,p=0,m=s.length-1,v=0,b=a.length-1;for(;p<=m&&v<=b;)if(s[p]===null)p++;else if(s[m]===null)m--;else if(r[p]===o[v])c[v]=Ke(s[p],a[v]),p++,v++;else if(r[m]===o[b])c[b]=Ke(s[m],a[b]),m--,b--;else if(r[p]===o[b])c[b]=Ke(s[p],a[b]),yt(e,c[b+1],s[p]),p++,b--;else if(r[m]===o[v])c[v]=Ke(s[m],a[v]),yt(e,s[p],s[m]),m--,v++;else if(u===void 0&&(u=Oa(o,v,b),f=Oa(r,p,m)),u.has(r[p]))if(u.has(r[m])){const d=f.get(o[v]),y=d!==void 0?s[d]:null;if(y===null){const A=yt(e,s[p]);Ke(A,a[v]),c[v]=A}else c[v]=Ke(y,a[v]),yt(e,s[p],y),s[d]=null;v++}else fi(s[m]),m--;else fi(s[p]),p++;for(;v<=b;){const d=yt(e,c[b+1]);Ke(d,a[v]),c[v++]=d}for(;p<=m;){const d=s[p++];d!==null&&fi(d)}return this.ut=o,Wu(e,c),Me}}),Y={messageSquare:l`
    <svg viewBox="0 0 24 24">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  `,barChart:l`
    <svg viewBox="0 0 24 24">
      <line x1="12" x2="12" y1="20" y2="10" />
      <line x1="18" x2="18" y1="20" y2="4" />
      <line x1="6" x2="6" y1="20" y2="16" />
    </svg>
  `,link:l`
    <svg viewBox="0 0 24 24">
      <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
      <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
    </svg>
  `,radio:l`
    <svg viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="2" />
      <path
        d="M16.24 7.76a6 6 0 0 1 0 8.49m-8.48-.01a6 6 0 0 1 0-8.49m11.31-2.82a10 10 0 0 1 0 14.14m-14.14 0a10 10 0 0 1 0-14.14"
      />
    </svg>
  `,fileText:l`
    <svg viewBox="0 0 24 24">
      <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" x2="8" y1="13" y2="13" />
      <line x1="16" x2="8" y1="17" y2="17" />
      <line x1="10" x2="8" y1="9" y2="9" />
    </svg>
  `,zap:l`
    <svg viewBox="0 0 24 24"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" /></svg>
  `,monitor:l`
    <svg viewBox="0 0 24 24">
      <rect width="20" height="14" x="2" y="3" rx="2" />
      <line x1="8" x2="16" y1="21" y2="21" />
      <line x1="12" x2="12" y1="17" y2="21" />
    </svg>
  `,settings:l`
    <svg viewBox="0 0 24 24">
      <path
        d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"
      />
      <circle cx="12" cy="12" r="3" />
    </svg>
  `,bug:l`
    <svg viewBox="0 0 24 24">
      <path d="m8 2 1.88 1.88" />
      <path d="M14.12 3.88 16 2" />
      <path d="M9 7.13v-1a3.003 3.003 0 1 1 6 0v1" />
      <path d="M12 20c-3.3 0-6-2.7-6-6v-3a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v3c0 3.3-2.7 6-6 6" />
      <path d="M12 20v-9" />
      <path d="M6.53 9C4.6 8.8 3 7.1 3 5" />
      <path d="M6 13H2" />
      <path d="M3 21c0-2.1 1.7-3.9 3.8-4" />
      <path d="M20.97 5c0 2.1-1.6 3.8-3.5 4" />
      <path d="M22 13h-4" />
      <path d="M17.2 17c2.1.1 3.8 1.9 3.8 4" />
    </svg>
  `,scrollText:l`
    <svg viewBox="0 0 24 24">
      <path d="M8 21h12a2 2 0 0 0 2-2v-2H10v2a2 2 0 1 1-4 0V5a2 2 0 1 0-4 0v3h4" />
      <path d="M19 17V5a2 2 0 0 0-2-2H4" />
      <path d="M15 8h-5" />
      <path d="M15 12h-5" />
    </svg>
  `,folder:l`
    <svg viewBox="0 0 24 24">
      <path
        d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"
      />
    </svg>
  `,menu:l`
    <svg viewBox="0 0 24 24">
      <line x1="4" x2="20" y1="12" y2="12" />
      <line x1="4" x2="20" y1="6" y2="6" />
      <line x1="4" x2="20" y1="18" y2="18" />
    </svg>
  `,x:l`
    <svg viewBox="0 0 24 24">
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </svg>
  `,check:l`
    <svg viewBox="0 0 24 24"><path d="M20 6 9 17l-5-5" /></svg>
  `,arrowDown:l`
    <svg viewBox="0 0 24 24">
      <path d="M12 5v14" />
      <path d="m19 12-7 7-7-7" />
    </svg>
  `,copy:l`
    <svg viewBox="0 0 24 24">
      <rect width="14" height="14" x="8" y="8" rx="2" ry="2" />
      <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
    </svg>
  `,search:l`
    <svg viewBox="0 0 24 24">
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  `,brain:l`
    <svg viewBox="0 0 24 24">
      <path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z" />
      <path d="M12 5a3 3 0 1 1 5.997.125 4 4 0 0 1 2.526 5.77 4 4 0 0 1-.556 6.588A4 4 0 1 1 12 18Z" />
      <path d="M15 13a4.5 4.5 0 0 1-3-4 4.5 4.5 0 0 1-3 4" />
      <path d="M17.599 6.5a3 3 0 0 0 .399-1.375" />
      <path d="M6.003 5.125A3 3 0 0 0 6.401 6.5" />
      <path d="M3.477 10.896a4 4 0 0 1 .585-.396" />
      <path d="M19.938 10.5a4 4 0 0 1 .585.396" />
      <path d="M6 18a4 4 0 0 1-1.967-.516" />
      <path d="M19.967 17.484A4 4 0 0 1 18 18" />
    </svg>
  `,book:l`
    <svg viewBox="0 0 24 24">
      <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20" />
    </svg>
  `,loader:l`
    <svg viewBox="0 0 24 24">
      <path d="M12 2v4" />
      <path d="m16.2 7.8 2.9-2.9" />
      <path d="M18 12h4" />
      <path d="m16.2 16.2 2.9 2.9" />
      <path d="M12 18v4" />
      <path d="m4.9 19.1 2.9-2.9" />
      <path d="M2 12h4" />
      <path d="m4.9 4.9 2.9 2.9" />
    </svg>
  `,wrench:l`
    <svg viewBox="0 0 24 24">
      <path
        d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"
      />
    </svg>
  `,fileCode:l`
    <svg viewBox="0 0 24 24">
      <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
      <polyline points="14 2 14 8 20 8" />
      <path d="m10 13-2 2 2 2" />
      <path d="m14 17 2-2-2-2" />
    </svg>
  `,edit:l`
    <svg viewBox="0 0 24 24">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </svg>
  `,penLine:l`
    <svg viewBox="0 0 24 24">
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
    </svg>
  `,paperclip:l`
    <svg viewBox="0 0 24 24">
      <path
        d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"
      />
    </svg>
  `,globe:l`
    <svg viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="10" />
      <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20" />
      <path d="M2 12h20" />
    </svg>
  `,image:l`
    <svg viewBox="0 0 24 24">
      <rect width="18" height="18" x="3" y="3" rx="2" ry="2" />
      <circle cx="9" cy="9" r="2" />
      <path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21" />
    </svg>
  `,smartphone:l`
    <svg viewBox="0 0 24 24">
      <rect width="14" height="20" x="5" y="2" rx="2" ry="2" />
      <path d="M12 18h.01" />
    </svg>
  `,plug:l`
    <svg viewBox="0 0 24 24">
      <path d="M12 22v-5" />
      <path d="M9 8V2" />
      <path d="M15 8V2" />
      <path d="M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8Z" />
    </svg>
  `,circle:l`
    <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" /></svg>
  `,puzzle:l`
    <svg viewBox="0 0 24 24">
      <path
        d="M19.439 7.85c-.049.322.059.648.289.878l1.568 1.568c.47.47.706 1.087.706 1.704s-.235 1.233-.706 1.704l-1.611 1.611a.98.98 0 0 1-.837.276c-.47-.07-.802-.48-.968-.925a2.501 2.501 0 1 0-3.214 3.214c.446.166.855.497.925.968a.979.979 0 0 1-.276.837l-1.61 1.61a2.404 2.404 0 0 1-1.705.707 2.402 2.402 0 0 1-1.704-.706l-1.568-1.568a1.026 1.026 0 0 0-.877-.29c-.493.074-.84.504-1.02.968a2.5 2.5 0 1 1-3.237-3.237c.464-.18.894-.527.967-1.02a1.026 1.026 0 0 0-.289-.877l-1.568-1.568A2.402 2.402 0 0 1 1.998 12c0-.617.236-1.234.706-1.704L4.23 8.77c.24-.24.581-.353.917-.303.515.076.874.54 1.02 1.02a2.5 2.5 0 1 0 3.237-3.237c-.48-.146-.944-.505-1.02-1.02a.98.98 0 0 1 .303-.917l1.526-1.526A2.402 2.402 0 0 1 11.998 2c.617 0 1.234.236 1.704.706l1.568 1.568c.23.23.556.338.877.29.493-.074.84-.504 1.02-.968a2.5 2.5 0 1 1 3.236 3.236c-.464.18-.894.527-.967 1.02Z"
      />
    </svg>
  `};function Yu(e,t){const n=vs(t,e.basePath);return l`
    <a
      href=${n}
      class="nav-item ${e.tab===t?"active":""}"
      @click=${i=>{i.defaultPrevented||i.button!==0||i.metaKey||i.ctrlKey||i.shiftKey||i.altKey||(i.preventDefault(),e.setTab(t))}}
      title=${Ii(t)}
    >
      <span class="nav-item__icon" aria-hidden="true">${Y[Cd(t)]}</span>
      <span class="nav-item__text">${Ii(t)}</span>
    </a>
  `}function Qu(e){const t=Ju(e.hello,e.sessionsResult),n=Zu(e.sessionKey,e.sessionsResult,t),i=e.onboarding,s=e.onboarding,a=e.onboarding?!1:e.settings.chatShowThinking,o=e.onboarding?!0:e.settings.chatFocusMode,r=l`
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      <path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"></path>
      <path d="M21 3v5h-5"></path>
    </svg>
  `,c=l`
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      <path d="M4 7V4h3"></path>
      <path d="M20 7V4h-3"></path>
      <path d="M4 17v3h3"></path>
      <path d="M20 17v3h-3"></path>
      <circle cx="12" cy="12" r="3"></circle>
    </svg>
  `;return l`
    <div class="chat-controls">
      <label class="field chat-controls__session">
        <select
          .value=${e.sessionKey}
          ?disabled=${!e.connected}
          @change=${u=>{const f=u.target.value;e.sessionKey=f,e.chatMessage="",e.chatStream=null,e.chatStreamStartedAt=null,e.chatRunId=null,e.resetToolStream(),e.resetChatScroll(),e.applySettings({...e.settings,sessionKey:f,lastActiveSessionKey:f}),e.loadAssistantIdentity(),Gd(f),Bt(e)}}
        >
          ${Tl(n,u=>u.key,u=>l`<option value=${u.key}>
                ${u.displayName??u.key}
              </option>`)}
        </select>
      </label>
      <button
        class="btn btn--sm btn--icon"
        ?disabled=${e.chatLoading||!e.connected}
        @click=${()=>{e.resetToolStream(),Sl(e)}}
        title="Refresh chat data"
      >
        ${r}
      </button>
      <span class="chat-controls__separator">|</span>
      <button
        class="btn btn--sm btn--icon ${a?"active":""}"
        ?disabled=${i}
        @click=${()=>{i||e.applySettings({...e.settings,chatShowThinking:!e.settings.chatShowThinking})}}
        aria-pressed=${a}
        title=${i?"Disabled during onboarding":"Toggle assistant thinking/working output"}
      >
        ${Y.brain}
      </button>
      <button
        class="btn btn--sm btn--icon ${o?"active":""}"
        ?disabled=${s}
        @click=${()=>{s||e.applySettings({...e.settings,chatFocusMode:!e.settings.chatFocusMode})}}
        aria-pressed=${o}
        title=${s?"Disabled during onboarding":"Toggle focus mode (hide sidebar + page header)"}
      >
        ${c}
      </button>
    </div>
  `}function Ju(e,t){const n=e?.snapshot,i=n?.sessionDefaults?.mainSessionKey?.trim();if(i)return i;const s=n?.sessionDefaults?.mainKey?.trim();return s||(t?.sessions?.some(a=>a.key==="main")?"main":null)}function pi(e,t){const n=t?.label?.trim();if(n)return`${n} (${e})`;const i=t?.displayName?.trim();return i||e}function Zu(e,t,n){const i=new Set,s=[],a=n&&t?.sessions?.find(r=>r.key===n),o=t?.sessions?.find(r=>r.key===e);if(n&&(i.add(n),s.push({key:n,displayName:pi(n,a||void 0)})),i.has(e)||(i.add(e),s.push({key:e,displayName:pi(e,o)})),t?.sessions)for(const r of t.sessions)i.has(r.key)||(i.add(r.key),s.push({key:r.key,displayName:pi(r.key,r)}));return s}const Xu=["system","light","dark"];function ef(e){const t=Math.max(0,Xu.indexOf(e.theme)),n=i=>s=>{const o={element:s.currentTarget};(s.clientX||s.clientY)&&(o.pointerClientX=s.clientX,o.pointerClientY=s.clientY),e.setTheme(i,o)};return l`
    <div class="theme-toggle" style="--theme-index: ${t};">
      <div class="theme-toggle__track" role="group" aria-label="Theme">
        <span class="theme-toggle__indicator"></span>
        <button
          class="theme-toggle__button ${e.theme==="system"?"active":""}"
          @click=${n("system")}
          aria-pressed=${e.theme==="system"}
          aria-label="System theme"
          title="System"
        >
          ${sf()}
        </button>
        <button
          class="theme-toggle__button ${e.theme==="light"?"active":""}"
          @click=${n("light")}
          aria-pressed=${e.theme==="light"}
          aria-label="Light theme"
          title="Light"
        >
          ${tf()}
        </button>
        <button
          class="theme-toggle__button ${e.theme==="dark"?"active":""}"
          @click=${n("dark")}
          aria-pressed=${e.theme==="dark"}
          aria-label="Dark theme"
          title="Dark"
        >
          ${nf()}
        </button>
      </div>
    </div>
  `}function tf(){return l`
    <svg class="theme-icon" viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="4"></circle>
      <path d="M12 2v2"></path>
      <path d="M12 20v2"></path>
      <path d="m4.93 4.93 1.41 1.41"></path>
      <path d="m17.66 17.66 1.41 1.41"></path>
      <path d="M2 12h2"></path>
      <path d="M20 12h2"></path>
      <path d="m6.34 17.66-1.41 1.41"></path>
      <path d="m19.07 4.93-1.41 1.41"></path>
    </svg>
  `}function nf(){return l`
    <svg class="theme-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M20.985 12.486a9 9 0 1 1-9.473-9.472c.405-.022.617.46.402.803a6 6 0 0 0 8.268 8.268c.344-.215.825-.004.803.401"
      ></path>
    </svg>
  `}function sf(){return l`
    <svg class="theme-icon" viewBox="0 0 24 24" aria-hidden="true">
      <rect width="20" height="14" x="2" y="3" rx="2"></rect>
      <line x1="8" x2="16" y1="21" y2="21"></line>
      <line x1="12" x2="12" y1="17" y2="21"></line>
    </svg>
  `}function Ll(e,t){if(!e)return e;const i=e.files.some(s=>s.name===t.name)?e.files.map(s=>s.name===t.name?t:s):[...e.files,t];return{...e,files:i}}async function gi(e,t){if(!(!e.client||!e.connected||e.agentFilesLoading)){e.agentFilesLoading=!0,e.agentFilesError=null;try{const n=await e.client.request("agents.files.list",{agentId:t});n&&(e.agentFilesList=n,e.agentFileActive&&!n.files.some(i=>i.name===e.agentFileActive)&&(e.agentFileActive=null))}catch(n){e.agentFilesError=String(n)}finally{e.agentFilesLoading=!1}}}async function Ba(e,t,n,i){if(!(!e.client||!e.connected||e.agentFilesLoading)&&!(!i?.force&&Object.hasOwn(e.agentFileContents,n))){e.agentFilesLoading=!0,e.agentFilesError=null;try{const s=await e.client.request("agents.files.get",{agentId:t,name:n});if(s?.file){const a=s.file.content??"",o=e.agentFileContents[n]??"",r=e.agentFileDrafts[n],c=i?.preserveDraft??!0;e.agentFilesList=Ll(e.agentFilesList,s.file),e.agentFileContents={...e.agentFileContents,[n]:a},(!c||!Object.hasOwn(e.agentFileDrafts,n)||r===o)&&(e.agentFileDrafts={...e.agentFileDrafts,[n]:a})}}catch(s){e.agentFilesError=String(s)}finally{e.agentFilesLoading=!1}}}async function af(e,t,n,i){if(!(!e.client||!e.connected||e.agentFileSaving)){e.agentFileSaving=!0,e.agentFilesError=null;try{const s=await e.client.request("agents.files.set",{agentId:t,name:n,content:i});s?.file&&(e.agentFilesList=Ll(e.agentFilesList,s.file),e.agentFileContents={...e.agentFileContents,[n]:i},e.agentFileDrafts={...e.agentFileDrafts,[n]:i})}catch(s){e.agentFilesError=String(s)}finally{e.agentFileSaving=!1}}}const of={"group:memory":["memory_search","memory_get"],"group:web":["web_search","web_fetch"],"group:fs":["read","write","edit","apply_patch"],"group:runtime":["exec","process"],"group:sessions":["sessions_list","sessions_history","sessions_send","sessions_spawn","session_status"],"group:ui":["browser","canvas"],"group:automation":["cron","gateway"],"group:messaging":["message"],"group:nodes":["nodes"],"group:openclaw":["browser","canvas","nodes","cron","message","gateway","agents_list","sessions_list","sessions_history","sessions_send","sessions_spawn","session_status","memory_search","memory_get","web_search","web_fetch","image"]},lf={bash:"exec","apply-patch":"apply_patch"};function _e(e){const t=e.trim().toLowerCase();return lf[t]??t}function rf(e){const t=e.host??"unknown",n=e.ip?`(${e.ip})`:"",i=e.mode??"",s=e.version??"";return`${t} ${n} ${i} ${s}`.trim()}function cf(e){const t=e.ts??null;return t?O(t):"n/a"}function As(e){return e?`${Nt(e)} (${O(e)})`:"n/a"}function df(e){if(e.totalTokens==null)return"n/a";const t=e.totalTokens??0,n=e.contextTokens??0;return n?`${t} / ${n}`:String(t)}function uf(e){if(e==null)return"";try{return JSON.stringify(e,null,2)}catch{return String(e)}}function Il(e){const t=e.state??{},n=t.nextRunAtMs?Nt(t.nextRunAtMs):"n/a",i=t.lastRunAtMs?Nt(t.lastRunAtMs):"n/a";return`${t.lastStatus??"n/a"} · next ${n} · last ${i}`}function Rl(e){const t=e.schedule;if(t.kind==="at"){const n=Date.parse(t.at);return Number.isFinite(n)?`At ${Nt(n)}`:`At ${t.at}`}return t.kind==="every"?`Every ${jo(t.everyMs)}`:`Cron ${t.expr}${t.tz?` (${t.tz})`:""}`}function Ml(e){const t=e.payload;if(t.kind==="systemEvent")return`System: ${t.text}`;const n=`Agent: ${t.message}`,i=e.delivery;if(i&&i.mode!=="none"){const s=i.channel||i.to?` (${i.channel??"last"}${i.to?` -> ${i.to}`:""})`:"";return`${n} · ${i.mode}${s}`}return n}function ff(e){const t=new Set;for(const n of e)if(n.startsWith("group:")){const i=of[n];i&&i.forEach(s=>t.add(s))}else t.add(n);return Array.from(t)}function pf(e){return{minimal:{allow:["session_status"]},coding:{allow:["group:fs","group:runtime","group:sessions","group:memory","image"]},messaging:{allow:["group:messaging","sessions_list","sessions_history","sessions_send","session_status"]},full:{}}[e]||{}}const Ua=[{id:"fs",label:"Files",tools:[{id:"read",label:"read",description:"Read file contents"},{id:"write",label:"write",description:"Create or overwrite files"},{id:"edit",label:"edit",description:"Make precise edits"},{id:"apply_patch",label:"apply_patch",description:"Patch files (OpenAI)"}]},{id:"runtime",label:"Runtime",tools:[{id:"exec",label:"exec",description:"Run shell commands"},{id:"process",label:"process",description:"Manage background processes"}]},{id:"web",label:"Web",tools:[{id:"web_search",label:"web_search",description:"Search the web"},{id:"web_fetch",label:"web_fetch",description:"Fetch web content"}]},{id:"memory",label:"Memory",tools:[{id:"memory_search",label:"memory_search",description:"Semantic search"},{id:"memory_get",label:"memory_get",description:"Read memory files"}]},{id:"sessions",label:"Sessions",tools:[{id:"sessions_list",label:"sessions_list",description:"List sessions"},{id:"sessions_history",label:"sessions_history",description:"Session history"},{id:"sessions_send",label:"sessions_send",description:"Send to session"},{id:"sessions_spawn",label:"sessions_spawn",description:"Spawn sub-agent"},{id:"session_status",label:"session_status",description:"Session status"}]},{id:"ui",label:"UI",tools:[{id:"browser",label:"browser",description:"Control web browser"},{id:"canvas",label:"canvas",description:"Control canvases"}]},{id:"messaging",label:"Messaging",tools:[{id:"message",label:"message",description:"Send messages"}]},{id:"automation",label:"Automation",tools:[{id:"cron",label:"cron",description:"Schedule tasks"},{id:"gateway",label:"gateway",description:"Gateway control"}]},{id:"nodes",label:"Nodes",tools:[{id:"nodes",label:"nodes",description:"Nodes + devices"}]},{id:"agents",label:"Agents",tools:[{id:"agents_list",label:"agents_list",description:"List agents"}]},{id:"media",label:"Media",tools:[{id:"image",label:"image",description:"Image understanding"}]}],gf=[{id:"minimal",label:"Minimal"},{id:"coding",label:"Coding"},{id:"messaging",label:"Messaging"},{id:"full",label:"Full"}];function Di(e){return e.name?.trim()||e.identity?.name?.trim()||e.id}function sn(e){const t=e.trim();if(!t||t.length>16)return!1;let n=!1;for(let i=0;i<t.length;i+=1)if(t.charCodeAt(i)>127){n=!0;break}return!(!n||t.includes("://")||t.includes("/")||t.includes("."))}function Dn(e,t){const n=t?.emoji?.trim();if(n&&sn(n))return n;const i=e.identity?.emoji?.trim();if(i&&sn(i))return i;const s=t?.avatar?.trim();if(s&&sn(s))return s;const a=e.identity?.avatar?.trim();return a&&sn(a)?a:""}function Pl(e,t){return t&&e===t?"default":null}function hf(e){if(e==null||!Number.isFinite(e))return"-";if(e<1024)return`${e} B`;const t=["KB","MB","GB","TB"];let n=e/1024,i=0;for(;n>=1024&&i<t.length-1;)n/=1024,i+=1;return`${n.toFixed(n<10?1:0)} ${t[i]}`}function On(e,t){const n=e;return{entry:(n?.agents?.list??[]).find(a=>a?.id===t),defaults:n?.agents?.defaults,globalTools:n?.tools}}function Fl(e,t,n,i,s){const a=On(t,e.id),r=(n&&n.agentId===e.id?n.workspace:null)||a.entry?.workspace||a.defaults?.workspace||"default",c=a.entry?.model?Tt(a.entry?.model):Tt(a.defaults?.model),u=s?.name?.trim()||e.identity?.name?.trim()||e.name?.trim()||a.entry?.name||e.id,f=Dn(e,s)||"-",p=Array.isArray(a.entry?.skills)?a.entry?.skills:null,m=p?.length??null;return{workspace:r,model:c,identityName:u,identityEmoji:f,skillsLabel:p?`${m} selected`:"all skills",isDefault:!!(i&&e.id===i)}}function Tt(e){if(!e)return"-";if(typeof e=="string")return e.trim()||"-";if(typeof e=="object"&&e){const t=e,n=t.primary?.trim();if(n){const i=Array.isArray(t.fallbacks)?t.fallbacks.length:0;return i>0?`${n} (+${i} fallback)`:n}}return"-"}function Ka(e){const t=e.match(/^(.+) \(\+\d+ fallback\)$/);return t?t[1]:e}function za(e){if(!e)return null;if(typeof e=="string")return e.trim()||null;if(typeof e=="object"&&e){const t=e;return(typeof t.primary=="string"?t.primary:typeof t.model=="string"?t.model:typeof t.id=="string"?t.id:typeof t.value=="string"?t.value:null)?.trim()||null}return null}function vf(e){if(!e||typeof e=="string")return null;if(typeof e=="object"&&e){const t=e,n=Array.isArray(t.fallbacks)?t.fallbacks:Array.isArray(t.fallback)?t.fallback:null;return n?n.filter(i=>typeof i=="string"):null}return null}function mf(e){return e.split(",").map(t=>t.trim()).filter(Boolean)}function yf(e){const n=e?.agents?.defaults?.models;if(!n||typeof n!="object")return[];const i=[];for(const[s,a]of Object.entries(n)){const o=s.trim();if(!o)continue;const r=a&&typeof a=="object"&&"alias"in a&&typeof a.alias=="string"?a.alias?.trim():void 0,c=r&&r!==o?`${r} (${o})`:o;i.push({value:o,label:c})}return i}function bf(e,t){const n=yf(e),i=t?n.some(s=>s.value===t):!1;return t&&!i&&n.unshift({value:t,label:`Current (${t})`}),n.length===0?l`
      <option value="" disabled>No configured models</option>
    `:n.map(s=>l`<option value=${s.value}>${s.label}</option>`)}function $f(e){const t=_e(e);if(!t)return{kind:"exact",value:""};if(t==="*")return{kind:"all"};if(!t.includes("*"))return{kind:"exact",value:t};const n=t.replace(/[.*+?^${}()|[\\]\\]/g,"\\$&");return{kind:"regex",value:new RegExp(`^${n.replaceAll("\\*",".*")}$`)}}function Oi(e){return Array.isArray(e)?ff(e).map($f).filter(t=>t.kind!=="exact"||t.value.length>0):[]}function Lt(e,t){for(const n of t)if(n.kind==="all"||n.kind==="exact"&&e===n.value||n.kind==="regex"&&n.value.test(e))return!0;return!1}function wf(e,t){if(!t)return!0;const n=_e(e),i=Oi(t.deny);if(Lt(n,i))return!1;const s=Oi(t.allow);return!!(s.length===0||Lt(n,s)||n==="apply_patch"&&Lt("exec",s))}function Ha(e,t){if(!Array.isArray(t)||t.length===0)return!1;const n=_e(e),i=Oi(t);return!!(Lt(n,i)||n==="apply_patch"&&Lt("exec",i))}function kf(e){const t=e.agentsList?.agents??[],n=e.agentsList?.defaultId??null,i=e.selectedAgentId??n??t[0]?.id??null,s=i?t.find(a=>a.id===i)??null:null;return l`
    <div class="agents-layout">
      <section class="card agents-sidebar">
        <div class="row" style="justify-content: space-between;">
          <div>
            <div class="card-title">Agents</div>
            <div class="card-sub">${t.length} configured.</div>
          </div>
          <button class="btn btn--sm" ?disabled=${e.loading} @click=${e.onRefresh}>
            ${e.loading?"Loading…":"Refresh"}
          </button>
        </div>
        ${e.error?l`<div class="callout danger" style="margin-top: 12px;">${e.error}</div>`:g}
        <div class="agent-list" style="margin-top: 12px;">
          ${t.length===0?l`
                  <div class="muted">No agents found.</div>
                `:t.map(a=>{const o=Pl(a.id,n),r=Dn(a,e.agentIdentityById[a.id]??null);return l`
                    <button
                      type="button"
                      class="agent-row ${i===a.id?"active":""}"
                      @click=${()=>e.onSelectAgent(a.id)}
                    >
                      <div class="agent-avatar">
                        ${r||Di(a).slice(0,1)}
                      </div>
                      <div class="agent-info">
                        <div class="agent-title">${Di(a)}</div>
                        <div class="agent-sub mono">${a.id}</div>
                      </div>
                      ${o?l`<span class="agent-pill">${o}</span>`:g}
                    </button>
                  `})}
        </div>
      </section>
      <section class="agents-main">
        ${s?l`
              ${Af(s,n,e.agentIdentityById[s.id]??null)}
              ${xf(e.activePanel,a=>e.onSelectPanel(a))}
              ${e.activePanel==="overview"?Sf({agent:s,defaultId:n,configForm:e.configForm,agentFilesList:e.agentFilesList,agentIdentity:e.agentIdentityById[s.id]??null,agentIdentityError:e.agentIdentityError,agentIdentityLoading:e.agentIdentityLoading,configLoading:e.configLoading,configSaving:e.configSaving,configDirty:e.configDirty,onConfigReload:e.onConfigReload,onConfigSave:e.onConfigSave,onModelChange:e.onModelChange,onModelFallbacksChange:e.onModelFallbacksChange}):g}
              ${e.activePanel==="files"?Ff({agentId:s.id,agentFilesList:e.agentFilesList,agentFilesLoading:e.agentFilesLoading,agentFilesError:e.agentFilesError,agentFileActive:e.agentFileActive,agentFileContents:e.agentFileContents,agentFileDrafts:e.agentFileDrafts,agentFileSaving:e.agentFileSaving,onLoadFiles:e.onLoadFiles,onSelectFile:e.onSelectFile,onFileDraftChange:e.onFileDraftChange,onFileReset:e.onFileReset,onFileSave:e.onFileSave}):g}
              ${e.activePanel==="tools"?Df({agentId:s.id,configForm:e.configForm,configLoading:e.configLoading,configSaving:e.configSaving,configDirty:e.configDirty,onProfileChange:e.onToolsProfileChange,onOverridesChange:e.onToolsOverridesChange,onConfigReload:e.onConfigReload,onConfigSave:e.onConfigSave}):g}
              ${e.activePanel==="skills"?Bf({agentId:s.id,report:e.agentSkillsReport,loading:e.agentSkillsLoading,error:e.agentSkillsError,activeAgentId:e.agentSkillsAgentId,configForm:e.configForm,configLoading:e.configLoading,configSaving:e.configSaving,configDirty:e.configDirty,filter:e.skillsFilter,onFilterChange:e.onSkillsFilterChange,onRefresh:e.onSkillsRefresh,onToggle:e.onAgentSkillToggle,onClear:e.onAgentSkillsClear,onDisableAll:e.onAgentSkillsDisableAll,onConfigReload:e.onConfigReload,onConfigSave:e.onConfigSave}):g}
              ${e.activePanel==="channels"?Mf({agent:s,defaultId:n,configForm:e.configForm,agentFilesList:e.agentFilesList,agentIdentity:e.agentIdentityById[s.id]??null,snapshot:e.channelsSnapshot,loading:e.channelsLoading,error:e.channelsError,lastSuccess:e.channelsLastSuccess,onRefresh:e.onChannelsRefresh}):g}
              ${e.activePanel==="cron"?Pf({agent:s,defaultId:n,configForm:e.configForm,agentFilesList:e.agentFilesList,agentIdentity:e.agentIdentityById[s.id]??null,jobs:e.cronJobs,status:e.cronStatus,loading:e.cronLoading,error:e.cronError,onRefresh:e.onCronRefresh}):g}
            `:l`
                <div class="card">
                  <div class="card-title">Select an agent</div>
                  <div class="card-sub">Pick an agent to inspect its workspace and tools.</div>
                </div>
              `}
      </section>
    </div>
  `}function Af(e,t,n){const i=Pl(e.id,t),s=Di(e),a=e.identity?.theme?.trim()||"Agent workspace and routing.",o=Dn(e,n);return l`
    <section class="card agent-header">
      <div class="agent-header-main">
        <div class="agent-avatar agent-avatar--lg">
          ${o||s.slice(0,1)}
        </div>
        <div>
          <div class="card-title">${s}</div>
          <div class="card-sub">${a}</div>
        </div>
      </div>
      <div class="agent-header-meta">
        <div class="mono">${e.id}</div>
        ${i?l`<span class="agent-pill">${i}</span>`:g}
      </div>
    </section>
  `}function xf(e,t){return l`
    <div class="agent-tabs">
      ${[{id:"overview",label:"Overview"},{id:"files",label:"Files"},{id:"tools",label:"Tools"},{id:"skills",label:"Skills"},{id:"channels",label:"Channels"},{id:"cron",label:"Cron Jobs"}].map(i=>l`
          <button
            class="agent-tab ${e===i.id?"active":""}"
            type="button"
            @click=${()=>t(i.id)}
          >
            ${i.label}
          </button>
        `)}
    </div>
  `}function Sf(e){const{agent:t,configForm:n,agentFilesList:i,agentIdentity:s,agentIdentityLoading:a,agentIdentityError:o,configLoading:r,configSaving:c,configDirty:u,onConfigReload:f,onConfigSave:p,onModelChange:m,onModelFallbacksChange:v}=e,b=On(n,t.id),y=(i&&i.agentId===t.id?i.workspace:null)||b.entry?.workspace||b.defaults?.workspace||"default",A=b.entry?.model?Tt(b.entry?.model):Tt(b.defaults?.model),x=Tt(b.defaults?.model),T=za(b.entry?.model)||(A!=="-"?Ka(A):null),S=za(b.defaults?.model)||(x!=="-"?Ka(x):null),E=T??S??null,C=vf(b.entry?.model),P=C?C.join(", "):"",ce=s?.name?.trim()||t.identity?.name?.trim()||t.name?.trim()||b.entry?.name||"-",Q=Dn(t,s)||"-",D=Array.isArray(b.entry?.skills)?b.entry?.skills:null,De=D?.length??null,ae=a?"Loading…":o?"Unavailable":"",Le=!!(e.defaultId&&t.id===e.defaultId);return l`
    <section class="card">
      <div class="card-title">Overview</div>
      <div class="card-sub">Workspace paths and identity metadata.</div>
      <div class="agents-overview-grid" style="margin-top: 16px;">
        <div class="agent-kv">
          <div class="label">Workspace</div>
          <div class="mono">${y}</div>
        </div>
        <div class="agent-kv">
          <div class="label">Primary Model</div>
          <div class="mono">${A}</div>
        </div>
        <div class="agent-kv">
          <div class="label">Identity Name</div>
          <div>${ce}</div>
          ${ae?l`<div class="agent-kv-sub muted">${ae}</div>`:g}
        </div>
        <div class="agent-kv">
          <div class="label">Default</div>
          <div>${Le?"yes":"no"}</div>
        </div>
        <div class="agent-kv">
          <div class="label">Identity Emoji</div>
          <div>${Q}</div>
        </div>
        <div class="agent-kv">
          <div class="label">Skills Filter</div>
          <div>${D?`${De} selected`:"all skills"}</div>
        </div>
      </div>

      <div class="agent-model-select" style="margin-top: 20px;">
        <div class="label">Model Selection</div>
        <div class="row" style="gap: 12px; flex-wrap: wrap;">
          <label class="field" style="min-width: 260px; flex: 1;">
            <span>Primary model${Le?" (default)":""}</span>
            <select
              .value=${E??""}
              ?disabled=${!n||r||c}
              @change=${he=>m(t.id,he.target.value||null)}
            >
              ${Le?g:l`
                      <option value="">
                        ${S?`Inherit default (${S})`:"Inherit default"}
                      </option>
                    `}
              ${bf(n,E??void 0)}
            </select>
          </label>
          <label class="field" style="min-width: 260px; flex: 1;">
            <span>Fallbacks (comma-separated)</span>
            <input
              .value=${P}
              ?disabled=${!n||r||c}
              placeholder="provider/model, provider/model"
              @input=${he=>v(t.id,mf(he.target.value))}
            />
          </label>
        </div>
        <div class="row" style="justify-content: flex-end; gap: 8px;">
          <button
            class="btn btn--sm"
            ?disabled=${r}
            @click=${f}
          >
            Reload Config
          </button>
          <button
            class="btn btn--sm primary"
            ?disabled=${c||!u}
            @click=${p}
          >
            ${c?"Saving…":"Save"}
          </button>
        </div>
      </div>
    </section>
  `}function Nl(e,t){return l`
    <section class="card">
      <div class="card-title">Agent Context</div>
      <div class="card-sub">${t}</div>
      <div class="agents-overview-grid" style="margin-top: 16px;">
        <div class="agent-kv">
          <div class="label">Workspace</div>
          <div class="mono">${e.workspace}</div>
        </div>
        <div class="agent-kv">
          <div class="label">Primary Model</div>
          <div class="mono">${e.model}</div>
        </div>
        <div class="agent-kv">
          <div class="label">Identity Name</div>
          <div>${e.identityName}</div>
        </div>
        <div class="agent-kv">
          <div class="label">Identity Emoji</div>
          <div>${e.identityEmoji}</div>
        </div>
        <div class="agent-kv">
          <div class="label">Skills Filter</div>
          <div>${e.skillsLabel}</div>
        </div>
        <div class="agent-kv">
          <div class="label">Default</div>
          <div>${e.isDefault?"yes":"no"}</div>
        </div>
      </div>
    </section>
  `}function _f(e,t){const n=e.channelMeta?.find(i=>i.id===t);return n?.label?n.label:e.channelLabels?.[t]??t}function Cf(e){if(!e)return[];const t=new Set;for(const s of e.channelOrder??[])t.add(s);for(const s of e.channelMeta??[])t.add(s.id);for(const s of Object.keys(e.channelAccounts??{}))t.add(s);const n=[],i=e.channelOrder?.length?e.channelOrder:Array.from(t);for(const s of i)t.has(s)&&(n.push(s),t.delete(s));for(const s of t)n.push(s);return n.map(s=>({id:s,label:_f(e,s),accounts:e.channelAccounts?.[s]??[]}))}const Ef=["groupPolicy","streamMode","dmPolicy"];function Tf(e,t){if(!e)return null;const i=(e.channels??{})[t];if(i&&typeof i=="object")return i;const s=e[t];return s&&typeof s=="object"?s:null}function Lf(e){if(e==null)return"n/a";if(typeof e=="string"||typeof e=="number"||typeof e=="boolean")return String(e);try{return JSON.stringify(e)}catch{return"n/a"}}function If(e,t){const n=Tf(e,t);return n?Ef.flatMap(i=>i in n?[{label:i,value:Lf(n[i])}]:[]):[]}function Rf(e){let t=0,n=0,i=0;for(const s of e){const a=s.probe&&typeof s.probe=="object"&&"ok"in s.probe?!!s.probe.ok:!1;(s.connected===!0||s.running===!0||a)&&(t+=1),s.configured&&(n+=1),s.enabled&&(i+=1)}return{total:e.length,connected:t,configured:n,enabled:i}}function Mf(e){const t=Fl(e.agent,e.configForm,e.agentFilesList,e.defaultId,e.agentIdentity),n=Cf(e.snapshot),i=e.lastSuccess?O(e.lastSuccess):"never";return l`
    <section class="grid grid-cols-2">
      ${Nl(t,"Workspace, identity, and model configuration.")}
      <section class="card">
        <div class="row" style="justify-content: space-between;">
          <div>
            <div class="card-title">Channels</div>
            <div class="card-sub">Gateway-wide channel status snapshot.</div>
          </div>
          <button class="btn btn--sm" ?disabled=${e.loading} @click=${e.onRefresh}>
            ${e.loading?"Refreshing…":"Refresh"}
          </button>
        </div>
        <div class="muted" style="margin-top: 8px;">
          Last refresh: ${i}
        </div>
        ${e.error?l`<div class="callout danger" style="margin-top: 12px;">${e.error}</div>`:g}
        ${e.snapshot?g:l`
                <div class="callout info" style="margin-top: 12px">Load channels to see live status.</div>
              `}
        ${n.length===0?l`
                <div class="muted" style="margin-top: 16px">No channels found.</div>
              `:l`
              <div class="list" style="margin-top: 16px;">
                ${n.map(s=>{const a=Rf(s.accounts),o=a.total?`${a.connected}/${a.total} connected`:"no accounts",r=a.configured?`${a.configured} configured`:"not configured",c=a.total?`${a.enabled} enabled`:"disabled",u=If(e.configForm,s.id);return l`
                    <div class="list-item">
                      <div class="list-main">
                        <div class="list-title">${s.label}</div>
                        <div class="list-sub mono">${s.id}</div>
                      </div>
                      <div class="list-meta">
                        <div>${o}</div>
                        <div>${r}</div>
                        <div>${c}</div>
                        ${u.length>0?u.map(f=>l`<div>${f.label}: ${f.value}</div>`):g}
                      </div>
                    </div>
                  `})}
              </div>
            `}
      </section>
    </section>
  `}function Pf(e){const t=Fl(e.agent,e.configForm,e.agentFilesList,e.defaultId,e.agentIdentity),n=e.jobs.filter(i=>i.agentId===e.agent.id);return l`
    <section class="grid grid-cols-2">
      ${Nl(t,"Workspace and scheduling targets.")}
      <section class="card">
        <div class="row" style="justify-content: space-between;">
          <div>
            <div class="card-title">Scheduler</div>
            <div class="card-sub">Gateway cron status.</div>
          </div>
          <button class="btn btn--sm" ?disabled=${e.loading} @click=${e.onRefresh}>
            ${e.loading?"Refreshing…":"Refresh"}
          </button>
        </div>
        <div class="stat-grid" style="margin-top: 16px;">
          <div class="stat">
            <div class="stat-label">Enabled</div>
            <div class="stat-value">
              ${e.status?e.status.enabled?"Yes":"No":"n/a"}
            </div>
          </div>
          <div class="stat">
            <div class="stat-label">Jobs</div>
            <div class="stat-value">${e.status?.jobs??"n/a"}</div>
          </div>
          <div class="stat">
            <div class="stat-label">Next wake</div>
            <div class="stat-value">${As(e.status?.nextWakeAtMs??null)}</div>
          </div>
        </div>
        ${e.error?l`<div class="callout danger" style="margin-top: 12px;">${e.error}</div>`:g}
      </section>
    </section>
    <section class="card">
      <div class="card-title">Agent Cron Jobs</div>
      <div class="card-sub">Scheduled jobs targeting this agent.</div>
      ${n.length===0?l`
              <div class="muted" style="margin-top: 16px">No jobs assigned.</div>
            `:l`
              <div class="list" style="margin-top: 16px;">
                ${n.map(i=>l`
                  <div class="list-item">
                    <div class="list-main">
                      <div class="list-title">${i.name}</div>
                      ${i.description?l`<div class="list-sub">${i.description}</div>`:g}
                      <div class="chip-row" style="margin-top: 6px;">
                        <span class="chip">${Rl(i)}</span>
                        <span class="chip ${i.enabled?"chip-ok":"chip-warn"}">
                          ${i.enabled?"enabled":"disabled"}
                        </span>
                        <span class="chip">${i.sessionTarget}</span>
                      </div>
                    </div>
                    <div class="list-meta">
                      <div class="mono">${Il(i)}</div>
                      <div class="muted">${Ml(i)}</div>
                    </div>
                  </div>
                `)}
              </div>
            `}
    </section>
  `}function Ff(e){const t=e.agentFilesList?.agentId===e.agentId?e.agentFilesList:null,n=t?.files??[],i=e.agentFileActive??null,s=i?n.find(c=>c.name===i)??null:null,a=i?e.agentFileContents[i]??"":"",o=i?e.agentFileDrafts[i]??a:"",r=i?o!==a:!1;return l`
    <section class="card">
      <div class="row" style="justify-content: space-between;">
        <div>
          <div class="card-title">Core Files</div>
          <div class="card-sub">Bootstrap persona, identity, and tool guidance.</div>
        </div>
        <button
          class="btn btn--sm"
          ?disabled=${e.agentFilesLoading}
          @click=${()=>e.onLoadFiles(e.agentId)}
        >
          ${e.agentFilesLoading?"Loading…":"Refresh"}
        </button>
      </div>
      ${t?l`<div class="muted mono" style="margin-top: 8px;">Workspace: ${t.workspace}</div>`:g}
      ${e.agentFilesError?l`<div class="callout danger" style="margin-top: 12px;">${e.agentFilesError}</div>`:g}
      ${t?l`
              <div class="agent-files-grid" style="margin-top: 16px;">
                <div class="agent-files-list">
                  ${n.length===0?l`
                          <div class="muted">No files found.</div>
                        `:n.map(c=>Nf(c,i,()=>e.onSelectFile(c.name)))}
                </div>
                <div class="agent-files-editor">
                  ${s?l`
                          <div class="agent-file-header">
                            <div>
                              <div class="agent-file-title mono">${s.name}</div>
                              <div class="agent-file-sub mono">${s.path}</div>
                            </div>
                            <div class="agent-file-actions">
                              <button
                                class="btn btn--sm"
                                ?disabled=${!r}
                                @click=${()=>e.onFileReset(s.name)}
                              >
                                Reset
                              </button>
                              <button
                                class="btn btn--sm primary"
                                ?disabled=${e.agentFileSaving||!r}
                                @click=${()=>e.onFileSave(s.name)}
                              >
                                ${e.agentFileSaving?"Saving…":"Save"}
                              </button>
                            </div>
                          </div>
                          ${s.missing?l`
                                  <div class="callout info" style="margin-top: 10px">
                                    This file is missing. Saving will create it in the agent workspace.
                                  </div>
                                `:g}
                          <label class="field" style="margin-top: 12px;">
                            <span>Content</span>
                            <textarea
                              .value=${o}
                              @input=${c=>e.onFileDraftChange(s.name,c.target.value)}
                            ></textarea>
                          </label>
                        `:l`
                          <div class="muted">Select a file to edit.</div>
                        `}
                </div>
              </div>
            `:l`
              <div class="callout info" style="margin-top: 12px">
                Load the agent workspace files to edit core instructions.
              </div>
            `}
    </section>
  `}function Nf(e,t,n){const i=e.missing?"Missing":`${hf(e.size)} · ${O(e.updatedAtMs??null)}`;return l`
    <button
      type="button"
      class="agent-file-row ${t===e.name?"active":""}"
      @click=${n}
    >
      <div>
        <div class="agent-file-name mono">${e.name}</div>
        <div class="agent-file-meta">${i}</div>
      </div>
      ${e.missing?l`
              <span class="agent-pill warn">missing</span>
            `:g}
    </button>
  `}function Df(e){const t=On(e.configForm,e.agentId),n=t.entry?.tools??{},i=t.globalTools??{},s=n.profile??i.profile??"full",a=n.profile?"agent override":i.profile?"global default":"default",o=Array.isArray(n.allow)&&n.allow.length>0,r=Array.isArray(i.allow)&&i.allow.length>0,c=!!e.configForm&&!e.configLoading&&!e.configSaving&&!o,u=o?[]:Array.isArray(n.alsoAllow)?n.alsoAllow:[],f=o?[]:Array.isArray(n.deny)?n.deny:[],p=o?{allow:n.allow??[],deny:n.deny??[]}:pf(s)??void 0,m=Ua.flatMap(A=>A.tools.map(x=>x.id)),v=A=>{const x=wf(A,p),T=Ha(A,u),S=Ha(A,f);return{allowed:(x||T)&&!S,baseAllowed:x,denied:S}},b=m.filter(A=>v(A).allowed).length,d=(A,x)=>{const T=new Set(u.map(P=>_e(P)).filter(P=>P.length>0)),S=new Set(f.map(P=>_e(P)).filter(P=>P.length>0)),E=v(A).baseAllowed,C=_e(A);x?(S.delete(C),E||T.add(C)):(T.delete(C),S.add(C)),e.onOverridesChange(e.agentId,[...T],[...S])},y=A=>{const x=new Set(u.map(S=>_e(S)).filter(S=>S.length>0)),T=new Set(f.map(S=>_e(S)).filter(S=>S.length>0));for(const S of m){const E=v(S).baseAllowed,C=_e(S);A?(T.delete(C),E||x.add(C)):(x.delete(C),T.add(C))}e.onOverridesChange(e.agentId,[...x],[...T])};return l`
    <section class="card">
      <div class="row" style="justify-content: space-between;">
        <div>
          <div class="card-title">Tool Access</div>
          <div class="card-sub">
            Profile + per-tool overrides for this agent.
            <span class="mono">${b}/${m.length}</span> enabled.
          </div>
        </div>
        <div class="row" style="gap: 8px;">
          <button
            class="btn btn--sm"
            ?disabled=${!c}
            @click=${()=>y(!0)}
          >
            Enable All
          </button>
          <button
            class="btn btn--sm"
            ?disabled=${!c}
            @click=${()=>y(!1)}
          >
            Disable All
          </button>
          <button
            class="btn btn--sm"
            ?disabled=${e.configLoading}
            @click=${e.onConfigReload}
          >
            Reload Config
          </button>
          <button
            class="btn btn--sm primary"
            ?disabled=${e.configSaving||!e.configDirty}
            @click=${e.onConfigSave}
          >
            ${e.configSaving?"Saving…":"Save"}
          </button>
        </div>
      </div>

      ${e.configForm?g:l`
              <div class="callout info" style="margin-top: 12px">
                Load the gateway config to adjust tool profiles.
              </div>
            `}
      ${o?l`
              <div class="callout info" style="margin-top: 12px">
                This agent is using an explicit allowlist in config. Tool overrides are managed in the Config tab.
              </div>
            `:g}
      ${r?l`
              <div class="callout info" style="margin-top: 12px">
                Global tools.allow is set. Agent overrides cannot enable tools that are globally blocked.
              </div>
            `:g}

      <div class="agent-tools-meta" style="margin-top: 16px;">
        <div class="agent-kv">
          <div class="label">Profile</div>
          <div class="mono">${s}</div>
        </div>
        <div class="agent-kv">
          <div class="label">Source</div>
          <div>${a}</div>
        </div>
        ${e.configDirty?l`
                <div class="agent-kv">
                  <div class="label">Status</div>
                  <div class="mono">unsaved</div>
                </div>
              `:g}
      </div>

      <div class="agent-tools-presets" style="margin-top: 16px;">
        <div class="label">Quick Presets</div>
        <div class="agent-tools-buttons">
          ${gf.map(A=>l`
              <button
                class="btn btn--sm ${s===A.id?"active":""}"
                ?disabled=${!c}
                @click=${()=>e.onProfileChange(e.agentId,A.id,!0)}
              >
                ${A.label}
              </button>
            `)}
          <button
            class="btn btn--sm"
            ?disabled=${!c}
            @click=${()=>e.onProfileChange(e.agentId,null,!1)}
          >
            Inherit
          </button>
        </div>
      </div>

      <div class="agent-tools-grid" style="margin-top: 20px;">
        ${Ua.map(A=>l`
            <div class="agent-tools-section">
              <div class="agent-tools-header">${A.label}</div>
              <div class="agent-tools-list">
                ${A.tools.map(x=>{const{allowed:T}=v(x.id);return l`
                    <div class="agent-tool-row">
                      <div>
                        <div class="agent-tool-title mono">${x.label}</div>
                        <div class="agent-tool-sub">${x.description}</div>
                      </div>
                      <label class="cfg-toggle">
                        <input
                          type="checkbox"
                          .checked=${T}
                          ?disabled=${!c}
                          @change=${S=>d(x.id,S.target.checked)}
                        />
                        <span class="cfg-toggle__track"></span>
                      </label>
                    </div>
                  `})}
              </div>
            </div>
          `)}
      </div>
    </section>
  `}const an=[{id:"workspace",label:"Workspace Skills",sources:["openclaw-workspace"]},{id:"built-in",label:"Built-in Skills",sources:["openclaw-bundled"]},{id:"installed",label:"Installed Skills",sources:["openclaw-managed"]},{id:"extra",label:"Extra Skills",sources:["openclaw-extra"]}];function Of(e){const t=new Map;for(const a of an)t.set(a.id,{id:a.id,label:a.label,skills:[]});const n=an.find(a=>a.id==="built-in"),i={id:"other",label:"Other Skills",skills:[]};for(const a of e){const o=a.bundled?n:an.find(r=>r.sources.includes(a.source));o?t.get(o.id)?.skills.push(a):i.skills.push(a)}const s=an.map(a=>t.get(a.id)).filter(a=>!!(a&&a.skills.length>0));return i.skills.length>0&&s.push(i),s}function Bf(e){const t=!!e.configForm&&!e.configLoading&&!e.configSaving,n=On(e.configForm,e.agentId),i=Array.isArray(n.entry?.skills)?n.entry?.skills:void 0,s=new Set((i??[]).map(v=>v.trim()).filter(Boolean)),a=i!==void 0,o=!!(e.report&&e.activeAgentId===e.agentId),r=o?e.report?.skills??[]:[],c=e.filter.trim().toLowerCase(),u=c?r.filter(v=>[v.name,v.description,v.source].join(" ").toLowerCase().includes(c)):r,f=Of(u),p=a?r.filter(v=>s.has(v.name)).length:r.length,m=r.length;return l`
    <section class="card">
      <div class="row" style="justify-content: space-between;">
        <div>
          <div class="card-title">Skills</div>
          <div class="card-sub">
            Per-agent skill allowlist and workspace skills.
            ${m>0?l`<span class="mono">${p}/${m}</span>`:g}
          </div>
        </div>
        <div class="row" style="gap: 8px;">
          <button class="btn btn--sm" ?disabled=${!t} @click=${()=>e.onClear(e.agentId)}>
            Use All
          </button>
          <button class="btn btn--sm" ?disabled=${!t} @click=${()=>e.onDisableAll(e.agentId)}>
            Disable All
          </button>
          <button
            class="btn btn--sm"
            ?disabled=${e.configLoading}
            @click=${e.onConfigReload}
          >
            Reload Config
          </button>
          <button class="btn btn--sm" ?disabled=${e.loading} @click=${e.onRefresh}>
            ${e.loading?"Loading…":"Refresh"}
          </button>
          <button
            class="btn btn--sm primary"
            ?disabled=${e.configSaving||!e.configDirty}
            @click=${e.onConfigSave}
          >
            ${e.configSaving?"Saving…":"Save"}
          </button>
        </div>
      </div>

      ${e.configForm?g:l`
              <div class="callout info" style="margin-top: 12px">
                Load the gateway config to set per-agent skills.
              </div>
            `}
      ${a?l`
              <div class="callout info" style="margin-top: 12px">This agent uses a custom skill allowlist.</div>
            `:l`
              <div class="callout info" style="margin-top: 12px">
                All skills are enabled. Disabling any skill will create a per-agent allowlist.
              </div>
            `}
      ${!o&&!e.loading?l`
              <div class="callout info" style="margin-top: 12px">
                Load skills for this agent to view workspace-specific entries.
              </div>
            `:g}
      ${e.error?l`<div class="callout danger" style="margin-top: 12px;">${e.error}</div>`:g}

      <div class="filters" style="margin-top: 14px;">
        <label class="field" style="flex: 1;">
          <span>Filter</span>
          <input
            .value=${e.filter}
            @input=${v=>e.onFilterChange(v.target.value)}
            placeholder="Search skills"
          />
        </label>
        <div class="muted">${u.length} shown</div>
      </div>

      ${u.length===0?l`
              <div class="muted" style="margin-top: 16px">No skills found.</div>
            `:l`
              <div class="agent-skills-groups" style="margin-top: 16px;">
                ${f.map(v=>Uf(v,{agentId:e.agentId,allowSet:s,usingAllowlist:a,editable:t,onToggle:e.onToggle}))}
              </div>
            `}
    </section>
  `}function Uf(e,t){const n=e.id==="workspace"||e.id==="built-in";return l`
    <details class="agent-skills-group" ?open=${!n}>
      <summary class="agent-skills-header">
        <span>${e.label}</span>
        <span class="muted">${e.skills.length}</span>
      </summary>
      <div class="list skills-grid">
        ${e.skills.map(i=>Kf(i,{agentId:t.agentId,allowSet:t.allowSet,usingAllowlist:t.usingAllowlist,editable:t.editable,onToggle:t.onToggle}))}
      </div>
    </details>
  `}function Kf(e,t){const n=t.usingAllowlist?t.allowSet.has(e.name):!0,i=[...e.missing.bins.map(a=>`bin:${a}`),...e.missing.env.map(a=>`env:${a}`),...e.missing.config.map(a=>`config:${a}`),...e.missing.os.map(a=>`os:${a}`)],s=[];return e.disabled&&s.push("disabled"),e.blockedByAllowlist&&s.push("blocked by allowlist"),l`
    <div class="list-item agent-skill-row">
      <div class="list-main">
        <div class="list-title">
          ${e.emoji?`${e.emoji} `:""}${e.name}
        </div>
        <div class="list-sub">${e.description}</div>
        <div class="chip-row" style="margin-top: 6px;">
          <span class="chip">${e.source}</span>
          <span class="chip ${e.eligible?"chip-ok":"chip-warn"}">
            ${e.eligible?"eligible":"blocked"}
          </span>
          ${e.disabled?l`
                  <span class="chip chip-warn">disabled</span>
                `:g}
        </div>
        ${i.length>0?l`<div class="muted" style="margin-top: 6px;">Missing: ${i.join(", ")}</div>`:g}
        ${s.length>0?l`<div class="muted" style="margin-top: 6px;">Reason: ${s.join(", ")}</div>`:g}
      </div>
      <div class="list-meta">
        <label class="cfg-toggle">
          <input
            type="checkbox"
            .checked=${n}
            ?disabled=${!t.editable}
            @change=${a=>t.onToggle(t.agentId,e.name,a.target.checked)}
          />
          <span class="cfg-toggle__track"></span>
        </label>
      </div>
    </div>
  `}function $e(e){if(e)return Array.isArray(e.type)?e.type.filter(n=>n!=="null")[0]??e.type[0]:e.type}function Dl(e){if(!e)return"";if(e.default!==void 0)return e.default;switch($e(e)){case"object":return{};case"array":return[];case"boolean":return!1;case"number":case"integer":return 0;case"string":return"";default:return""}}function Bn(e){return e.filter(t=>typeof t=="string").join(".")}function le(e,t){const n=Bn(e),i=t[n];if(i)return i;const s=n.split(".");for(const[a,o]of Object.entries(t)){if(!a.includes("*"))continue;const r=a.split(".");if(r.length!==s.length)continue;let c=!0;for(let u=0;u<s.length;u+=1)if(r[u]!=="*"&&r[u]!==s[u]){c=!1;break}if(c)return o}}function Ee(e){return e.replace(/_/g," ").replace(/([a-z0-9])([A-Z])/g,"$1 $2").replace(/\s+/g," ").replace(/^./,t=>t.toUpperCase())}function zf(e){const t=Bn(e).toLowerCase();return t.includes("token")||t.includes("password")||t.includes("secret")||t.includes("apikey")||t.endsWith("key")}const Hf=new Set(["title","description","default","nullable"]);function jf(e){return Object.keys(e??{}).filter(n=>!Hf.has(n)).length===0}function Gf(e){if(e===void 0)return"";try{return JSON.stringify(e,null,2)??""}catch{return""}}const Ut={chevronDown:l`
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      <polyline points="6 9 12 15 18 9"></polyline>
    </svg>
  `,plus:l`
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      <line x1="12" y1="5" x2="12" y2="19"></line>
      <line x1="5" y1="12" x2="19" y2="12"></line>
    </svg>
  `,minus:l`
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      <line x1="5" y1="12" x2="19" y2="12"></line>
    </svg>
  `,trash:l`
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      <polyline points="3 6 5 6 21 6"></polyline>
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
    </svg>
  `,edit:l`
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
    </svg>
  `};function Ce(e){const{schema:t,value:n,path:i,hints:s,unsupported:a,disabled:o,onPatch:r}=e,c=e.showLabel??!0,u=$e(t),f=le(i,s),p=f?.label??t.title??Ee(String(i.at(-1))),m=f?.help??t.description,v=Bn(i);if(a.has(v))return l`<div class="cfg-field cfg-field--error">
      <div class="cfg-field__label">${p}</div>
      <div class="cfg-field__error">Unsupported schema node. Use Raw mode.</div>
    </div>`;if(t.anyOf||t.oneOf){const d=(t.anyOf??t.oneOf??[]).filter(E=>!(E.type==="null"||Array.isArray(E.type)&&E.type.includes("null")));if(d.length===1)return Ce({...e,schema:d[0]});const y=E=>{if(E.const!==void 0)return E.const;if(E.enum&&E.enum.length===1)return E.enum[0]},A=d.map(y),x=A.every(E=>E!==void 0);if(x&&A.length>0&&A.length<=5){const E=n??t.default;return l`
        <div class="cfg-field">
          ${c?l`<label class="cfg-field__label">${p}</label>`:g}
          ${m?l`<div class="cfg-field__help">${m}</div>`:g}
          <div class="cfg-segmented">
            ${A.map(C=>l`
              <button
                type="button"
                class="cfg-segmented__btn ${C===E||String(C)===String(E)?"active":""}"
                ?disabled=${o}
                @click=${()=>r(i,C)}
              >
                ${String(C)}
              </button>
            `)}
          </div>
        </div>
      `}if(x&&A.length>5)return Ga({...e,options:A,value:n??t.default});const T=new Set(d.map(E=>$e(E)).filter(Boolean)),S=new Set([...T].map(E=>E==="integer"?"number":E));if([...S].every(E=>["string","number","boolean"].includes(E))){const E=S.has("string"),C=S.has("number");if(S.has("boolean")&&S.size===1)return Ce({...e,schema:{...t,type:"boolean",anyOf:void 0,oneOf:void 0}});if(E||C)return ja({...e,inputType:C&&!E?"number":"text"})}}if(t.enum){const b=t.enum;if(b.length<=5){const d=n??t.default;return l`
        <div class="cfg-field">
          ${c?l`<label class="cfg-field__label">${p}</label>`:g}
          ${m?l`<div class="cfg-field__help">${m}</div>`:g}
          <div class="cfg-segmented">
            ${b.map(y=>l`
              <button
                type="button"
                class="cfg-segmented__btn ${y===d||String(y)===String(d)?"active":""}"
                ?disabled=${o}
                @click=${()=>r(i,y)}
              >
                ${String(y)}
              </button>
            `)}
          </div>
        </div>
      `}return Ga({...e,options:b,value:n??t.default})}if(u==="object")return Wf(e);if(u==="array")return Vf(e);if(u==="boolean"){const b=typeof n=="boolean"?n:typeof t.default=="boolean"?t.default:!1;return l`
      <label class="cfg-toggle-row ${o?"disabled":""}">
        <div class="cfg-toggle-row__content">
          <span class="cfg-toggle-row__label">${p}</span>
          ${m?l`<span class="cfg-toggle-row__help">${m}</span>`:g}
        </div>
        <div class="cfg-toggle">
          <input
            type="checkbox"
            .checked=${b}
            ?disabled=${o}
            @change=${d=>r(i,d.target.checked)}
          />
          <span class="cfg-toggle__track"></span>
        </div>
      </label>
    `}return u==="number"||u==="integer"?qf(e):u==="string"?ja({...e,inputType:"text"}):l`
    <div class="cfg-field cfg-field--error">
      <div class="cfg-field__label">${p}</div>
      <div class="cfg-field__error">Unsupported type: ${u}. Use Raw mode.</div>
    </div>
  `}function ja(e){const{schema:t,value:n,path:i,hints:s,disabled:a,onPatch:o,inputType:r}=e,c=e.showLabel??!0,u=le(i,s),f=u?.label??t.title??Ee(String(i.at(-1))),p=u?.help??t.description,m=u?.sensitive??zf(i),v=u?.placeholder??(m?"••••":t.default!==void 0?`Default: ${String(t.default)}`:""),b=n??"";return l`
    <div class="cfg-field">
      ${c?l`<label class="cfg-field__label">${f}</label>`:g}
      ${p?l`<div class="cfg-field__help">${p}</div>`:g}
      <div class="cfg-input-wrap">
        <input
          type=${m?"password":r}
          class="cfg-input"
          placeholder=${v}
          .value=${b==null?"":String(b)}
          ?disabled=${a}
          @input=${d=>{const y=d.target.value;if(r==="number"){if(y.trim()===""){o(i,void 0);return}const A=Number(y);o(i,Number.isNaN(A)?y:A);return}o(i,y)}}
          @change=${d=>{if(r==="number")return;const y=d.target.value;o(i,y.trim())}}
        />
        ${t.default!==void 0?l`
          <button
            type="button"
            class="cfg-input__reset"
            title="Reset to default"
            ?disabled=${a}
            @click=${()=>o(i,t.default)}
          >↺</button>
        `:g}
      </div>
    </div>
  `}function qf(e){const{schema:t,value:n,path:i,hints:s,disabled:a,onPatch:o}=e,r=e.showLabel??!0,c=le(i,s),u=c?.label??t.title??Ee(String(i.at(-1))),f=c?.help??t.description,p=n??t.default??"",m=typeof p=="number"?p:0;return l`
    <div class="cfg-field">
      ${r?l`<label class="cfg-field__label">${u}</label>`:g}
      ${f?l`<div class="cfg-field__help">${f}</div>`:g}
      <div class="cfg-number">
        <button
          type="button"
          class="cfg-number__btn"
          ?disabled=${a}
          @click=${()=>o(i,m-1)}
        >−</button>
        <input
          type="number"
          class="cfg-number__input"
          .value=${p==null?"":String(p)}
          ?disabled=${a}
          @input=${v=>{const b=v.target.value,d=b===""?void 0:Number(b);o(i,d)}}
        />
        <button
          type="button"
          class="cfg-number__btn"
          ?disabled=${a}
          @click=${()=>o(i,m+1)}
        >+</button>
      </div>
    </div>
  `}function Ga(e){const{schema:t,value:n,path:i,hints:s,disabled:a,options:o,onPatch:r}=e,c=e.showLabel??!0,u=le(i,s),f=u?.label??t.title??Ee(String(i.at(-1))),p=u?.help??t.description,m=n??t.default,v=o.findIndex(d=>d===m||String(d)===String(m)),b="__unset__";return l`
    <div class="cfg-field">
      ${c?l`<label class="cfg-field__label">${f}</label>`:g}
      ${p?l`<div class="cfg-field__help">${p}</div>`:g}
      <select
        class="cfg-select"
        ?disabled=${a}
        .value=${v>=0?String(v):b}
        @change=${d=>{const y=d.target.value;r(i,y===b?void 0:o[Number(y)])}}
      >
        <option value=${b}>Select...</option>
        ${o.map((d,y)=>l`
          <option value=${String(y)}>${String(d)}</option>
        `)}
      </select>
    </div>
  `}function Wf(e){const{schema:t,value:n,path:i,hints:s,unsupported:a,disabled:o,onPatch:r}=e,c=le(i,s),u=c?.label??t.title??Ee(String(i.at(-1))),f=c?.help??t.description,p=n??t.default,m=p&&typeof p=="object"&&!Array.isArray(p)?p:{},v=t.properties??{},d=Object.entries(v).toSorted((T,S)=>{const E=le([...i,T[0]],s)?.order??0,C=le([...i,S[0]],s)?.order??0;return E!==C?E-C:T[0].localeCompare(S[0])}),y=new Set(Object.keys(v)),A=t.additionalProperties,x=!!A&&typeof A=="object";return i.length===1?l`
      <div class="cfg-fields">
        ${d.map(([T,S])=>Ce({schema:S,value:m[T],path:[...i,T],hints:s,unsupported:a,disabled:o,onPatch:r}))}
        ${x?qa({schema:A,value:m,path:i,hints:s,unsupported:a,disabled:o,reservedKeys:y,onPatch:r}):g}
      </div>
    `:l`
    <details class="cfg-object" open>
      <summary class="cfg-object__header">
        <span class="cfg-object__title">${u}</span>
        <span class="cfg-object__chevron">${Ut.chevronDown}</span>
      </summary>
      ${f?l`<div class="cfg-object__help">${f}</div>`:g}
      <div class="cfg-object__content">
        ${d.map(([T,S])=>Ce({schema:S,value:m[T],path:[...i,T],hints:s,unsupported:a,disabled:o,onPatch:r}))}
        ${x?qa({schema:A,value:m,path:i,hints:s,unsupported:a,disabled:o,reservedKeys:y,onPatch:r}):g}
      </div>
    </details>
  `}function Vf(e){const{schema:t,value:n,path:i,hints:s,unsupported:a,disabled:o,onPatch:r}=e,c=e.showLabel??!0,u=le(i,s),f=u?.label??t.title??Ee(String(i.at(-1))),p=u?.help??t.description,m=Array.isArray(t.items)?t.items[0]:t.items;if(!m)return l`
      <div class="cfg-field cfg-field--error">
        <div class="cfg-field__label">${f}</div>
        <div class="cfg-field__error">Unsupported array schema. Use Raw mode.</div>
      </div>
    `;const v=Array.isArray(n)?n:Array.isArray(t.default)?t.default:[];return l`
    <div class="cfg-array">
      <div class="cfg-array__header">
        ${c?l`<span class="cfg-array__label">${f}</span>`:g}
        <span class="cfg-array__count">${v.length} item${v.length!==1?"s":""}</span>
        <button
          type="button"
          class="cfg-array__add"
          ?disabled=${o}
          @click=${()=>{const b=[...v,Dl(m)];r(i,b)}}
        >
          <span class="cfg-array__add-icon">${Ut.plus}</span>
          Add
        </button>
      </div>
      ${p?l`<div class="cfg-array__help">${p}</div>`:g}

      ${v.length===0?l`
              <div class="cfg-array__empty">No items yet. Click "Add" to create one.</div>
            `:l`
        <div class="cfg-array__items">
          ${v.map((b,d)=>l`
            <div class="cfg-array__item">
              <div class="cfg-array__item-header">
                <span class="cfg-array__item-index">#${d+1}</span>
                <button
                  type="button"
                  class="cfg-array__item-remove"
                  title="Remove item"
                  ?disabled=${o}
                  @click=${()=>{const y=[...v];y.splice(d,1),r(i,y)}}
                >
                  ${Ut.trash}
                </button>
              </div>
              <div class="cfg-array__item-content">
                ${Ce({schema:m,value:b,path:[...i,d],hints:s,unsupported:a,disabled:o,showLabel:!1,onPatch:r})}
              </div>
            </div>
          `)}
        </div>
      `}
    </div>
  `}function qa(e){const{schema:t,value:n,path:i,hints:s,unsupported:a,disabled:o,reservedKeys:r,onPatch:c}=e,u=jf(t),f=Object.entries(n??{}).filter(([p])=>!r.has(p));return l`
    <div class="cfg-map">
      <div class="cfg-map__header">
        <span class="cfg-map__label">Custom entries</span>
        <button
          type="button"
          class="cfg-map__add"
          ?disabled=${o}
          @click=${()=>{const p={...n};let m=1,v=`custom-${m}`;for(;v in p;)m+=1,v=`custom-${m}`;p[v]=u?{}:Dl(t),c(i,p)}}
        >
          <span class="cfg-map__add-icon">${Ut.plus}</span>
          Add Entry
        </button>
      </div>

      ${f.length===0?l`
              <div class="cfg-map__empty">No custom entries.</div>
            `:l`
        <div class="cfg-map__items">
          ${f.map(([p,m])=>{const v=[...i,p],b=Gf(m);return l`
              <div class="cfg-map__item">
                <div class="cfg-map__item-key">
                  <input
                    type="text"
                    class="cfg-input cfg-input--sm"
                    placeholder="Key"
                    .value=${p}
                    ?disabled=${o}
                    @change=${d=>{const y=d.target.value.trim();if(!y||y===p)return;const A={...n};y in A||(A[y]=A[p],delete A[p],c(i,A))}}
                  />
                </div>
                <div class="cfg-map__item-value">
                  ${u?l`
                        <textarea
                          class="cfg-textarea cfg-textarea--sm"
                          placeholder="JSON value"
                          rows="2"
                          .value=${b}
                          ?disabled=${o}
                          @change=${d=>{const y=d.target,A=y.value.trim();if(!A){c(v,void 0);return}try{c(v,JSON.parse(A))}catch{y.value=b}}}
                        ></textarea>
                      `:Ce({schema:t,value:m,path:v,hints:s,unsupported:a,disabled:o,showLabel:!1,onPatch:c})}
                </div>
                <button
                  type="button"
                  class="cfg-map__item-remove"
                  title="Remove entry"
                  ?disabled=${o}
                  @click=${()=>{const d={...n};delete d[p],c(i,d)}}
                >
                  ${Ut.trash}
                </button>
              </div>
            `})}
        </div>
      `}
    </div>
  `}const Wa={env:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <circle cx="12" cy="12" r="3"></circle>
      <path
        d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"
      ></path>
    </svg>
  `,update:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
      <polyline points="7 10 12 15 17 10"></polyline>
      <line x1="12" y1="15" x2="12" y2="3"></line>
    </svg>
  `,agents:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <path
        d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7h1a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1h-1v1a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-1H2a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1h1a7 7 0 0 1 7-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 0 1 2-2z"
      ></path>
      <circle cx="8" cy="14" r="1"></circle>
      <circle cx="16" cy="14" r="1"></circle>
    </svg>
  `,auth:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
      <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
    </svg>
  `,channels:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
    </svg>
  `,messages:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>
      <polyline points="22,6 12,13 2,6"></polyline>
    </svg>
  `,commands:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <polyline points="4 17 10 11 4 5"></polyline>
      <line x1="12" y1="19" x2="20" y2="19"></line>
    </svg>
  `,hooks:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
      <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
    </svg>
  `,skills:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <polygon
        points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"
      ></polygon>
    </svg>
  `,tools:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <path
        d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"
      ></path>
    </svg>
  `,gateway:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <circle cx="12" cy="12" r="10"></circle>
      <line x1="2" y1="12" x2="22" y2="12"></line>
      <path
        d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"
      ></path>
    </svg>
  `,wizard:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <path d="M15 4V2"></path>
      <path d="M15 16v-2"></path>
      <path d="M8 9h2"></path>
      <path d="M20 9h2"></path>
      <path d="M17.8 11.8 19 13"></path>
      <path d="M15 9h0"></path>
      <path d="M17.8 6.2 19 5"></path>
      <path d="m3 21 9-9"></path>
      <path d="M12.2 6.2 11 5"></path>
    </svg>
  `,meta:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <path d="M12 20h9"></path>
      <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"></path>
    </svg>
  `,logging:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
      <polyline points="14 2 14 8 20 8"></polyline>
      <line x1="16" y1="13" x2="8" y2="13"></line>
      <line x1="16" y1="17" x2="8" y2="17"></line>
      <polyline points="10 9 9 9 8 9"></polyline>
    </svg>
  `,browser:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <circle cx="12" cy="12" r="10"></circle>
      <circle cx="12" cy="12" r="4"></circle>
      <line x1="21.17" y1="8" x2="12" y2="8"></line>
      <line x1="3.95" y1="6.06" x2="8.54" y2="14"></line>
      <line x1="10.88" y1="21.94" x2="15.46" y2="14"></line>
    </svg>
  `,ui:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
      <line x1="3" y1="9" x2="21" y2="9"></line>
      <line x1="9" y1="21" x2="9" y2="9"></line>
    </svg>
  `,models:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <path
        d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"
      ></path>
      <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
      <line x1="12" y1="22.08" x2="12" y2="12"></line>
    </svg>
  `,bindings:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <rect x="2" y="2" width="20" height="8" rx="2" ry="2"></rect>
      <rect x="2" y="14" width="20" height="8" rx="2" ry="2"></rect>
      <line x1="6" y1="6" x2="6.01" y2="6"></line>
      <line x1="6" y1="18" x2="6.01" y2="18"></line>
    </svg>
  `,broadcast:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <path d="M4.9 19.1C1 15.2 1 8.8 4.9 4.9"></path>
      <path d="M7.8 16.2c-2.3-2.3-2.3-6.1 0-8.5"></path>
      <circle cx="12" cy="12" r="2"></circle>
      <path d="M16.2 7.8c2.3 2.3 2.3 6.1 0 8.5"></path>
      <path d="M19.1 4.9C23 8.8 23 15.1 19.1 19"></path>
    </svg>
  `,audio:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <path d="M9 18V5l12-2v13"></path>
      <circle cx="6" cy="18" r="3"></circle>
      <circle cx="18" cy="16" r="3"></circle>
    </svg>
  `,session:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
      <circle cx="9" cy="7" r="4"></circle>
      <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
      <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
    </svg>
  `,cron:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <circle cx="12" cy="12" r="10"></circle>
      <polyline points="12 6 12 12 16 14"></polyline>
    </svg>
  `,web:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <circle cx="12" cy="12" r="10"></circle>
      <line x1="2" y1="12" x2="22" y2="12"></line>
      <path
        d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"
      ></path>
    </svg>
  `,discovery:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <circle cx="11" cy="11" r="8"></circle>
      <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
    </svg>
  `,canvasHost:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
      <circle cx="8.5" cy="8.5" r="1.5"></circle>
      <polyline points="21 15 16 10 5 21"></polyline>
    </svg>
  `,talk:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
      <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
      <line x1="12" y1="19" x2="12" y2="23"></line>
      <line x1="8" y1="23" x2="16" y2="23"></line>
    </svg>
  `,plugins:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <path d="M12 2v6"></path>
      <path d="m4.93 10.93 4.24 4.24"></path>
      <path d="M2 12h6"></path>
      <path d="m4.93 13.07 4.24-4.24"></path>
      <path d="M12 22v-6"></path>
      <path d="m19.07 13.07-4.24-4.24"></path>
      <path d="M22 12h-6"></path>
      <path d="m19.07 10.93-4.24 4.24"></path>
    </svg>
  `,default:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
      <polyline points="14 2 14 8 20 8"></polyline>
    </svg>
  `},xs={env:{label:"Environment Variables",description:"Environment variables passed to the gateway process"},update:{label:"Updates",description:"Auto-update settings and release channel"},agents:{label:"Agents",description:"Agent configurations, models, and identities"},auth:{label:"Authentication",description:"API keys and authentication profiles"},channels:{label:"Channels",description:"Messaging channels (Telegram, Discord, Slack, etc.)"},messages:{label:"Messages",description:"Message handling and routing settings"},commands:{label:"Commands",description:"Custom slash commands"},hooks:{label:"Hooks",description:"Webhooks and event hooks"},skills:{label:"Skills",description:"Skill packs and capabilities"},tools:{label:"Tools",description:"Tool configurations (browser, search, etc.)"},gateway:{label:"Gateway",description:"Gateway server settings (port, auth, binding)"},wizard:{label:"Setup Wizard",description:"Setup wizard state and history"},meta:{label:"Metadata",description:"Gateway metadata and version information"},logging:{label:"Logging",description:"Log levels and output configuration"},browser:{label:"Browser",description:"Browser automation settings"},ui:{label:"UI",description:"User interface preferences"},models:{label:"Models",description:"AI model configurations and providers"},bindings:{label:"Bindings",description:"Key bindings and shortcuts"},broadcast:{label:"Broadcast",description:"Broadcast and notification settings"},audio:{label:"Audio",description:"Audio input/output settings"},session:{label:"Session",description:"Session management and persistence"},cron:{label:"Cron",description:"Scheduled tasks and automation"},web:{label:"Web",description:"Web server and API settings"},discovery:{label:"Discovery",description:"Service discovery and networking"},canvasHost:{label:"Canvas Host",description:"Canvas rendering and display"},talk:{label:"Talk",description:"Voice and speech settings"},plugins:{label:"Plugins",description:"Plugin management and extensions"}};function Va(e){return Wa[e]??Wa.default}function Yf(e,t,n){if(!n)return!0;const i=n.toLowerCase(),s=xs[e];return e.toLowerCase().includes(i)||s&&(s.label.toLowerCase().includes(i)||s.description.toLowerCase().includes(i))?!0:_t(t,i)}function _t(e,t){if(e.title?.toLowerCase().includes(t)||e.description?.toLowerCase().includes(t)||e.enum?.some(i=>String(i).toLowerCase().includes(t)))return!0;if(e.properties){for(const[i,s]of Object.entries(e.properties))if(i.toLowerCase().includes(t)||_t(s,t))return!0}if(e.items){const i=Array.isArray(e.items)?e.items:[e.items];for(const s of i)if(s&&_t(s,t))return!0}if(e.additionalProperties&&typeof e.additionalProperties=="object"&&_t(e.additionalProperties,t))return!0;const n=e.anyOf??e.oneOf??e.allOf;if(n){for(const i of n)if(i&&_t(i,t))return!0}return!1}function Qf(e){if(!e.schema)return l`
      <div class="muted">Schema unavailable.</div>
    `;const t=e.schema,n=e.value??{};if($e(t)!=="object"||!t.properties)return l`
      <div class="callout danger">Unsupported schema. Use Raw.</div>
    `;const i=new Set(e.unsupportedPaths??[]),s=t.properties,a=e.searchQuery??"",o=e.activeSection,r=e.activeSubsection??null,u=Object.entries(s).toSorted((p,m)=>{const v=le([p[0]],e.uiHints)?.order??50,b=le([m[0]],e.uiHints)?.order??50;return v!==b?v-b:p[0].localeCompare(m[0])}).filter(([p,m])=>!(o&&p!==o||a&&!Yf(p,m,a)));let f=null;if(o&&r&&u.length===1){const p=u[0]?.[1];p&&$e(p)==="object"&&p.properties&&p.properties[r]&&(f={sectionKey:o,subsectionKey:r,schema:p.properties[r]})}return u.length===0?l`
      <div class="config-empty">
        <div class="config-empty__icon">${Y.search}</div>
        <div class="config-empty__text">
          ${a?`No settings match "${a}"`:"No settings in this section"}
        </div>
      </div>
    `:l`
    <div class="config-form config-form--modern">
      ${f?(()=>{const{sectionKey:p,subsectionKey:m,schema:v}=f,b=le([p,m],e.uiHints),d=b?.label??v.title??Ee(m),y=b?.help??v.description??"",A=n[p],x=A&&typeof A=="object"?A[m]:void 0,T=`config-section-${p}-${m}`;return l`
              <section class="config-section-card" id=${T}>
                <div class="config-section-card__header">
                  <span class="config-section-card__icon">${Va(p)}</span>
                  <div class="config-section-card__titles">
                    <h3 class="config-section-card__title">${d}</h3>
                    ${y?l`<p class="config-section-card__desc">${y}</p>`:g}
                  </div>
                </div>
                <div class="config-section-card__content">
                  ${Ce({schema:v,value:x,path:[p,m],hints:e.uiHints,unsupported:i,disabled:e.disabled??!1,showLabel:!1,onPatch:e.onPatch})}
                </div>
              </section>
            `})():u.map(([p,m])=>{const v=xs[p]??{label:p.charAt(0).toUpperCase()+p.slice(1),description:m.description??""};return l`
              <section class="config-section-card" id="config-section-${p}">
                <div class="config-section-card__header">
                  <span class="config-section-card__icon">${Va(p)}</span>
                  <div class="config-section-card__titles">
                    <h3 class="config-section-card__title">${v.label}</h3>
                    ${v.description?l`<p class="config-section-card__desc">${v.description}</p>`:g}
                  </div>
                </div>
                <div class="config-section-card__content">
                  ${Ce({schema:m,value:n[p],path:[p],hints:e.uiHints,unsupported:i,disabled:e.disabled??!1,showLabel:!1,onPatch:e.onPatch})}
                </div>
              </section>
            `})}
    </div>
  `}const Jf=new Set(["title","description","default","nullable"]);function Zf(e){return Object.keys(e??{}).filter(n=>!Jf.has(n)).length===0}function Ol(e){const t=e.filter(s=>s!=null),n=t.length!==e.length,i=[];for(const s of t)i.some(a=>Object.is(a,s))||i.push(s);return{enumValues:i,nullable:n}}function Bl(e){return!e||typeof e!="object"?{schema:null,unsupportedPaths:["<root>"]}:It(e,[])}function It(e,t){const n=new Set,i={...e},s=Bn(t)||"<root>";if(e.anyOf||e.oneOf||e.allOf){const r=Xf(e,t);return r||{schema:e,unsupportedPaths:[s]}}const a=Array.isArray(e.type)&&e.type.includes("null"),o=$e(e)??(e.properties||e.additionalProperties?"object":void 0);if(i.type=o??e.type,i.nullable=a||e.nullable,i.enum){const{enumValues:r,nullable:c}=Ol(i.enum);i.enum=r,c&&(i.nullable=!0),r.length===0&&n.add(s)}if(o==="object"){const r=e.properties??{},c={};for(const[u,f]of Object.entries(r)){const p=It(f,[...t,u]);p.schema&&(c[u]=p.schema);for(const m of p.unsupportedPaths)n.add(m)}if(i.properties=c,e.additionalProperties===!0)n.add(s);else if(e.additionalProperties===!1)i.additionalProperties=!1;else if(e.additionalProperties&&typeof e.additionalProperties=="object"&&!Zf(e.additionalProperties)){const u=It(e.additionalProperties,[...t,"*"]);i.additionalProperties=u.schema??e.additionalProperties,u.unsupportedPaths.length>0&&n.add(s)}}else if(o==="array"){const r=Array.isArray(e.items)?e.items[0]:e.items;if(!r)n.add(s);else{const c=It(r,[...t,"*"]);i.items=c.schema??r,c.unsupportedPaths.length>0&&n.add(s)}}else o!=="string"&&o!=="number"&&o!=="integer"&&o!=="boolean"&&!i.enum&&n.add(s);return{schema:i,unsupportedPaths:Array.from(n)}}function Xf(e,t){if(e.allOf)return null;const n=e.anyOf??e.oneOf;if(!n)return null;const i=[],s=[];let a=!1;for(const r of n){if(!r||typeof r!="object")return null;if(Array.isArray(r.enum)){const{enumValues:c,nullable:u}=Ol(r.enum);i.push(...c),u&&(a=!0);continue}if("const"in r){if(r.const==null){a=!0;continue}i.push(r.const);continue}if($e(r)==="null"){a=!0;continue}s.push(r)}if(i.length>0&&s.length===0){const r=[];for(const c of i)r.some(u=>Object.is(u,c))||r.push(c);return{schema:{...e,enum:r,nullable:a,anyOf:void 0,oneOf:void 0,allOf:void 0},unsupportedPaths:[]}}if(s.length===1){const r=It(s[0],t);return r.schema&&(r.schema.nullable=a||r.schema.nullable),r}const o=new Set(["string","number","integer","boolean"]);return s.length>0&&i.length===0&&s.every(r=>r.type&&o.has(String(r.type)))?{schema:{...e,nullable:a},unsupportedPaths:[]}:null}function ep(e,t){let n=e;for(const i of t){if(!n)return null;const s=$e(n);if(s==="object"){const a=n.properties??{};if(typeof i=="string"&&a[i]){n=a[i];continue}const o=n.additionalProperties;if(typeof i=="string"&&o&&typeof o=="object"){n=o;continue}return null}if(s==="array"){if(typeof i!="number")return null;n=(Array.isArray(n.items)?n.items[0]:n.items)??null;continue}return null}return n}function tp(e,t){const i=(e.channels??{})[t],s=e[t];return(i&&typeof i=="object"?i:null)??(s&&typeof s=="object"?s:null)??{}}const np=["groupPolicy","streamMode","dmPolicy"];function ip(e){if(e==null)return"n/a";if(typeof e=="string"||typeof e=="number"||typeof e=="boolean")return String(e);try{return JSON.stringify(e)}catch{return"n/a"}}function sp(e){const t=np.flatMap(n=>n in e?[[n,e[n]]]:[]);return t.length===0?null:l`
    <div class="status-list" style="margin-top: 12px;">
      ${t.map(([n,i])=>l`
          <div>
            <span class="label">${n}</span>
            <span>${ip(i)}</span>
          </div>
        `)}
    </div>
  `}function ap(e){const t=Bl(e.schema),n=t.schema;if(!n)return l`
      <div class="callout danger">Schema unavailable. Use Raw.</div>
    `;const i=ep(n,["channels",e.channelId]);if(!i)return l`
      <div class="callout danger">Channel config schema unavailable.</div>
    `;const s=e.configValue??{},a=tp(s,e.channelId);return l`
    <div class="config-form">
      ${Ce({schema:i,value:a,path:["channels",e.channelId],hints:e.uiHints,unsupported:new Set(t.unsupportedPaths),disabled:e.disabled,showLabel:!1,onPatch:e.onPatch})}
    </div>
    ${sp(a)}
  `}function Te(e){const{channelId:t,props:n}=e,i=n.configSaving||n.configSchemaLoading;return l`
    <div style="margin-top: 16px;">
      ${n.configSchemaLoading?l`
              <div class="muted">Loading config schema…</div>
            `:ap({channelId:t,configValue:n.configForm,schema:n.configSchema,uiHints:n.configUiHints,disabled:i,onPatch:n.onConfigPatch})}
      <div class="row" style="margin-top: 12px;">
        <button
          class="btn primary"
          ?disabled=${i||!n.configFormDirty}
          @click=${()=>n.onConfigSave()}
        >
          ${n.configSaving?"Saving…":"Save"}
        </button>
        <button
          class="btn"
          ?disabled=${i}
          @click=${()=>n.onConfigReload()}
        >
          Reload
        </button>
      </div>
    </div>
  `}function op(e){const{props:t,discord:n,accountCountLabel:i}=e;return l`
    <div class="card">
      <div class="card-title">Discord</div>
      <div class="card-sub">Bot status and channel configuration.</div>
      ${i}

      <div class="status-list" style="margin-top: 16px;">
        <div>
          <span class="label">Configured</span>
          <span>${n?.configured?"Yes":"No"}</span>
        </div>
        <div>
          <span class="label">Running</span>
          <span>${n?.running?"Yes":"No"}</span>
        </div>
        <div>
          <span class="label">Last start</span>
          <span>${n?.lastStartAt?O(n.lastStartAt):"n/a"}</span>
        </div>
        <div>
          <span class="label">Last probe</span>
          <span>${n?.lastProbeAt?O(n.lastProbeAt):"n/a"}</span>
        </div>
      </div>

      ${n?.lastError?l`<div class="callout danger" style="margin-top: 12px;">
            ${n.lastError}
          </div>`:g}

      ${n?.probe?l`<div class="callout" style="margin-top: 12px;">
            Probe ${n.probe.ok?"ok":"failed"} ·
            ${n.probe.status??""} ${n.probe.error??""}
          </div>`:g}

      ${Te({channelId:"discord",props:t})}

      <div class="row" style="margin-top: 12px;">
        <button class="btn" @click=${()=>t.onRefresh(!0)}>
          Probe
        </button>
      </div>
    </div>
  `}function lp(e){const{props:t,googleChat:n,accountCountLabel:i}=e;return l`
    <div class="card">
      <div class="card-title">Google Chat</div>
      <div class="card-sub">Chat API webhook status and channel configuration.</div>
      ${i}

      <div class="status-list" style="margin-top: 16px;">
        <div>
          <span class="label">Configured</span>
          <span>${n?n.configured?"Yes":"No":"n/a"}</span>
        </div>
        <div>
          <span class="label">Running</span>
          <span>${n?n.running?"Yes":"No":"n/a"}</span>
        </div>
        <div>
          <span class="label">Credential</span>
          <span>${n?.credentialSource??"n/a"}</span>
        </div>
        <div>
          <span class="label">Audience</span>
          <span>
            ${n?.audienceType?`${n.audienceType}${n.audience?` · ${n.audience}`:""}`:"n/a"}
          </span>
        </div>
        <div>
          <span class="label">Last start</span>
          <span>${n?.lastStartAt?O(n.lastStartAt):"n/a"}</span>
        </div>
        <div>
          <span class="label">Last probe</span>
          <span>${n?.lastProbeAt?O(n.lastProbeAt):"n/a"}</span>
        </div>
      </div>

      ${n?.lastError?l`<div class="callout danger" style="margin-top: 12px;">
            ${n.lastError}
          </div>`:g}

      ${n?.probe?l`<div class="callout" style="margin-top: 12px;">
            Probe ${n.probe.ok?"ok":"failed"} ·
            ${n.probe.status??""} ${n.probe.error??""}
          </div>`:g}

      ${Te({channelId:"googlechat",props:t})}

      <div class="row" style="margin-top: 12px;">
        <button class="btn" @click=${()=>t.onRefresh(!0)}>
          Probe
        </button>
      </div>
    </div>
  `}function rp(e){const{props:t,imessage:n,accountCountLabel:i}=e;return l`
    <div class="card">
      <div class="card-title">iMessage</div>
      <div class="card-sub">macOS bridge status and channel configuration.</div>
      ${i}

      <div class="status-list" style="margin-top: 16px;">
        <div>
          <span class="label">Configured</span>
          <span>${n?.configured?"Yes":"No"}</span>
        </div>
        <div>
          <span class="label">Running</span>
          <span>${n?.running?"Yes":"No"}</span>
        </div>
        <div>
          <span class="label">Last start</span>
          <span>${n?.lastStartAt?O(n.lastStartAt):"n/a"}</span>
        </div>
        <div>
          <span class="label">Last probe</span>
          <span>${n?.lastProbeAt?O(n.lastProbeAt):"n/a"}</span>
        </div>
      </div>

      ${n?.lastError?l`<div class="callout danger" style="margin-top: 12px;">
            ${n.lastError}
          </div>`:g}

      ${n?.probe?l`<div class="callout" style="margin-top: 12px;">
            Probe ${n.probe.ok?"ok":"failed"} ·
            ${n.probe.error??""}
          </div>`:g}

      ${Te({channelId:"imessage",props:t})}

      <div class="row" style="margin-top: 12px;">
        <button class="btn" @click=${()=>t.onRefresh(!0)}>
          Probe
        </button>
      </div>
    </div>
  `}function Ya(e){return e?e.length<=20?e:`${e.slice(0,8)}...${e.slice(-8)}`:"n/a"}function cp(e){const{props:t,nostr:n,nostrAccounts:i,accountCountLabel:s,profileFormState:a,profileFormCallbacks:o,onEditProfile:r}=e,c=i[0],u=n?.configured??c?.configured??!1,f=n?.running??c?.running??!1,p=n?.publicKey??c?.publicKey,m=n?.lastStartAt??c?.lastStartAt??null,v=n?.lastError??c?.lastError??null,b=i.length>1,d=a!=null,y=x=>{const T=x.publicKey,S=x.profile,E=S?.displayName??S?.name??x.name??x.accountId;return l`
      <div class="account-card">
        <div class="account-card-header">
          <div class="account-card-title">${E}</div>
          <div class="account-card-id">${x.accountId}</div>
        </div>
        <div class="status-list account-card-status">
          <div>
            <span class="label">Running</span>
            <span>${x.running?"Yes":"No"}</span>
          </div>
          <div>
            <span class="label">Configured</span>
            <span>${x.configured?"Yes":"No"}</span>
          </div>
          <div>
            <span class="label">Public Key</span>
            <span class="monospace" title="${T??""}">${Ya(T)}</span>
          </div>
          <div>
            <span class="label">Last inbound</span>
            <span>${x.lastInboundAt?O(x.lastInboundAt):"n/a"}</span>
          </div>
          ${x.lastError?l`
                <div class="account-card-error">${x.lastError}</div>
              `:g}
        </div>
      </div>
    `},A=()=>{if(d&&o)return tc({state:a,callbacks:o,accountId:i[0]?.accountId??"default"});const x=c?.profile??n?.profile,{name:T,displayName:S,about:E,picture:C,nip05:P}=x??{},ce=T||S||E||C||P;return l`
      <div style="margin-top: 16px; padding: 12px; background: var(--bg-secondary); border-radius: 8px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <div style="font-weight: 500;">Profile</div>
          ${u?l`
                <button
                  class="btn btn-sm"
                  @click=${r}
                  style="font-size: 12px; padding: 4px 8px;"
                >
                  Edit Profile
                </button>
              `:g}
        </div>
        ${ce?l`
              <div class="status-list">
                ${C?l`
                      <div style="margin-bottom: 8px;">
                        <img
                          src=${C}
                          alt="Profile picture"
                          style="width: 48px; height: 48px; border-radius: 50%; object-fit: cover; border: 2px solid var(--border-color);"
                          @error=${H=>{H.target.style.display="none"}}
                        />
                      </div>
                    `:g}
                ${T?l`<div><span class="label">Name</span><span>${T}</span></div>`:g}
                ${S?l`<div><span class="label">Display Name</span><span>${S}</span></div>`:g}
                ${E?l`<div><span class="label">About</span><span style="max-width: 300px; overflow: hidden; text-overflow: ellipsis;">${E}</span></div>`:g}
                ${P?l`<div><span class="label">NIP-05</span><span>${P}</span></div>`:g}
              </div>
            `:l`
                <div style="color: var(--text-muted); font-size: 13px">
                  No profile set. Click "Edit Profile" to add your name, bio, and avatar.
                </div>
              `}
      </div>
    `};return l`
    <div class="card">
      <div class="card-title">Nostr</div>
      <div class="card-sub">Decentralized DMs via Nostr relays (NIP-04).</div>
      ${s}

      ${b?l`
            <div class="account-card-list">
              ${i.map(x=>y(x))}
            </div>
          `:l`
            <div class="status-list" style="margin-top: 16px;">
              <div>
                <span class="label">Configured</span>
                <span>${u?"Yes":"No"}</span>
              </div>
              <div>
                <span class="label">Running</span>
                <span>${f?"Yes":"No"}</span>
              </div>
              <div>
                <span class="label">Public Key</span>
                <span class="monospace" title="${p??""}"
                  >${Ya(p)}</span
                >
              </div>
              <div>
                <span class="label">Last start</span>
                <span>${m?O(m):"n/a"}</span>
              </div>
            </div>
          `}

      ${v?l`<div class="callout danger" style="margin-top: 12px;">${v}</div>`:g}

      ${A()}

      ${Te({channelId:"nostr",props:t})}

      <div class="row" style="margin-top: 12px;">
        <button class="btn" @click=${()=>t.onRefresh(!1)}>Refresh</button>
      </div>
    </div>
  `}function dp(e){if(!e&&e!==0)return"n/a";const t=Math.round(e/1e3);if(t<60)return`${t}s`;const n=Math.round(t/60);return n<60?`${n}m`:`${Math.round(n/60)}h`}function up(e,t){const n=t.snapshot,i=n?.channels;if(!n||!i)return!1;const s=i[e],a=typeof s?.configured=="boolean"&&s.configured,o=typeof s?.running=="boolean"&&s.running,r=typeof s?.connected=="boolean"&&s.connected,u=(n.channelAccounts?.[e]??[]).some(f=>f.configured||f.running||f.connected);return a||o||r||u}function fp(e,t){return t?.[e]?.length??0}function Ul(e,t){const n=fp(e,t);return n<2?g:l`<div class="account-count">Accounts (${n})</div>`}function pp(e){const{props:t,signal:n,accountCountLabel:i}=e;return l`
    <div class="card">
      <div class="card-title">Signal</div>
      <div class="card-sub">signal-cli status and channel configuration.</div>
      ${i}

      <div class="status-list" style="margin-top: 16px;">
        <div>
          <span class="label">Configured</span>
          <span>${n?.configured?"Yes":"No"}</span>
        </div>
        <div>
          <span class="label">Running</span>
          <span>${n?.running?"Yes":"No"}</span>
        </div>
        <div>
          <span class="label">Base URL</span>
          <span>${n?.baseUrl??"n/a"}</span>
        </div>
        <div>
          <span class="label">Last start</span>
          <span>${n?.lastStartAt?O(n.lastStartAt):"n/a"}</span>
        </div>
        <div>
          <span class="label">Last probe</span>
          <span>${n?.lastProbeAt?O(n.lastProbeAt):"n/a"}</span>
        </div>
      </div>

      ${n?.lastError?l`<div class="callout danger" style="margin-top: 12px;">
            ${n.lastError}
          </div>`:g}

      ${n?.probe?l`<div class="callout" style="margin-top: 12px;">
            Probe ${n.probe.ok?"ok":"failed"} ·
            ${n.probe.status??""} ${n.probe.error??""}
          </div>`:g}

      ${Te({channelId:"signal",props:t})}

      <div class="row" style="margin-top: 12px;">
        <button class="btn" @click=${()=>t.onRefresh(!0)}>
          Probe
        </button>
      </div>
    </div>
  `}function gp(e){const{props:t,slack:n,accountCountLabel:i}=e;return l`
    <div class="card">
      <div class="card-title">Slack</div>
      <div class="card-sub">Socket mode status and channel configuration.</div>
      ${i}

      <div class="status-list" style="margin-top: 16px;">
        <div>
          <span class="label">Configured</span>
          <span>${n?.configured?"Yes":"No"}</span>
        </div>
        <div>
          <span class="label">Running</span>
          <span>${n?.running?"Yes":"No"}</span>
        </div>
        <div>
          <span class="label">Last start</span>
          <span>${n?.lastStartAt?O(n.lastStartAt):"n/a"}</span>
        </div>
        <div>
          <span class="label">Last probe</span>
          <span>${n?.lastProbeAt?O(n.lastProbeAt):"n/a"}</span>
        </div>
      </div>

      ${n?.lastError?l`<div class="callout danger" style="margin-top: 12px;">
            ${n.lastError}
          </div>`:g}

      ${n?.probe?l`<div class="callout" style="margin-top: 12px;">
            Probe ${n.probe.ok?"ok":"failed"} ·
            ${n.probe.status??""} ${n.probe.error??""}
          </div>`:g}

      ${Te({channelId:"slack",props:t})}

      <div class="row" style="margin-top: 12px;">
        <button class="btn" @click=${()=>t.onRefresh(!0)}>
          Probe
        </button>
      </div>
    </div>
  `}function hp(e){const{props:t,telegram:n,telegramAccounts:i,accountCountLabel:s}=e,a=i.length>1,o=r=>{const u=r.probe?.bot?.username,f=r.name||r.accountId;return l`
      <div class="account-card">
        <div class="account-card-header">
          <div class="account-card-title">
            ${u?`@${u}`:f}
          </div>
          <div class="account-card-id">${r.accountId}</div>
        </div>
        <div class="status-list account-card-status">
          <div>
            <span class="label">Running</span>
            <span>${r.running?"Yes":"No"}</span>
          </div>
          <div>
            <span class="label">Configured</span>
            <span>${r.configured?"Yes":"No"}</span>
          </div>
          <div>
            <span class="label">Last inbound</span>
            <span>${r.lastInboundAt?O(r.lastInboundAt):"n/a"}</span>
          </div>
          ${r.lastError?l`
                <div class="account-card-error">
                  ${r.lastError}
                </div>
              `:g}
        </div>
      </div>
    `};return l`
    <div class="card">
      <div class="card-title">Telegram</div>
      <div class="card-sub">Bot status and channel configuration.</div>
      ${s}

      ${a?l`
            <div class="account-card-list">
              ${i.map(r=>o(r))}
            </div>
          `:l`
            <div class="status-list" style="margin-top: 16px;">
              <div>
                <span class="label">Configured</span>
                <span>${n?.configured?"Yes":"No"}</span>
              </div>
              <div>
                <span class="label">Running</span>
                <span>${n?.running?"Yes":"No"}</span>
              </div>
              <div>
                <span class="label">Mode</span>
                <span>${n?.mode??"n/a"}</span>
              </div>
              <div>
                <span class="label">Last start</span>
                <span>${n?.lastStartAt?O(n.lastStartAt):"n/a"}</span>
              </div>
              <div>
                <span class="label">Last probe</span>
                <span>${n?.lastProbeAt?O(n.lastProbeAt):"n/a"}</span>
              </div>
            </div>
          `}

      ${n?.lastError?l`<div class="callout danger" style="margin-top: 12px;">
            ${n.lastError}
          </div>`:g}

      ${n?.probe?l`<div class="callout" style="margin-top: 12px;">
            Probe ${n.probe.ok?"ok":"failed"} ·
            ${n.probe.status??""} ${n.probe.error??""}
          </div>`:g}

      ${Te({channelId:"telegram",props:t})}

      <div class="row" style="margin-top: 12px;">
        <button class="btn" @click=${()=>t.onRefresh(!0)}>
          Probe
        </button>
      </div>
    </div>
  `}function vp(e){const{props:t,whatsapp:n,accountCountLabel:i}=e;return l`
    <div class="card">
      <div class="card-title">WhatsApp</div>
      <div class="card-sub">Link WhatsApp Web and monitor connection health.</div>
      ${i}

      <div class="status-list" style="margin-top: 16px;">
        <div>
          <span class="label">Configured</span>
          <span>${n?.configured?"Yes":"No"}</span>
        </div>
        <div>
          <span class="label">Linked</span>
          <span>${n?.linked?"Yes":"No"}</span>
        </div>
        <div>
          <span class="label">Running</span>
          <span>${n?.running?"Yes":"No"}</span>
        </div>
        <div>
          <span class="label">Connected</span>
          <span>${n?.connected?"Yes":"No"}</span>
        </div>
        <div>
          <span class="label">Last connect</span>
          <span>
            ${n?.lastConnectedAt?O(n.lastConnectedAt):"n/a"}
          </span>
        </div>
        <div>
          <span class="label">Last message</span>
          <span>
            ${n?.lastMessageAt?O(n.lastMessageAt):"n/a"}
          </span>
        </div>
        <div>
          <span class="label">Auth age</span>
          <span>
            ${n?.authAgeMs!=null?dp(n.authAgeMs):"n/a"}
          </span>
        </div>
      </div>

      ${n?.lastError?l`<div class="callout danger" style="margin-top: 12px;">
            ${n.lastError}
          </div>`:g}

      ${t.whatsappMessage?l`<div class="callout" style="margin-top: 12px;">
            ${t.whatsappMessage}
          </div>`:g}

      ${t.whatsappQrDataUrl?l`<div class="qr-wrap">
            <img src=${t.whatsappQrDataUrl} alt="WhatsApp QR" />
          </div>`:g}

      <div class="row" style="margin-top: 14px; flex-wrap: wrap;">
        <button
          class="btn primary"
          ?disabled=${t.whatsappBusy}
          @click=${()=>t.onWhatsAppStart(!1)}
        >
          ${t.whatsappBusy?"Working…":"Show QR"}
        </button>
        <button
          class="btn"
          ?disabled=${t.whatsappBusy}
          @click=${()=>t.onWhatsAppStart(!0)}
        >
          Relink
        </button>
        <button
          class="btn"
          ?disabled=${t.whatsappBusy}
          @click=${()=>t.onWhatsAppWait()}
        >
          Wait for scan
        </button>
        <button
          class="btn danger"
          ?disabled=${t.whatsappBusy}
          @click=${()=>t.onWhatsAppLogout()}
        >
          Logout
        </button>
        <button class="btn" @click=${()=>t.onRefresh(!0)}>
          Refresh
        </button>
      </div>

      ${Te({channelId:"whatsapp",props:t})}
    </div>
  `}function mp(e){const t=e.snapshot?.channels,n=t?.whatsapp??void 0,i=t?.telegram??void 0,s=t?.discord??null,a=t?.googlechat??null,o=t?.slack??null,r=t?.signal??null,c=t?.imessage??null,u=t?.nostr??null,p=yp(e.snapshot).map((m,v)=>({key:m,enabled:up(m,e),order:v})).toSorted((m,v)=>m.enabled!==v.enabled?m.enabled?-1:1:m.order-v.order);return l`
    <section class="grid grid-cols-2">
      ${p.map(m=>bp(m.key,e,{whatsapp:n,telegram:i,discord:s,googlechat:a,slack:o,signal:r,imessage:c,nostr:u,channelAccounts:e.snapshot?.channelAccounts??null}))}
    </section>

    <section class="card" style="margin-top: 18px;">
      <div class="row" style="justify-content: space-between;">
        <div>
          <div class="card-title">Channel health</div>
          <div class="card-sub">Channel status snapshots from the gateway.</div>
        </div>
        <div class="muted">${e.lastSuccessAt?O(e.lastSuccessAt):"n/a"}</div>
      </div>
      ${e.lastError?l`<div class="callout danger" style="margin-top: 12px;">
            ${e.lastError}
          </div>`:g}
      <pre class="code-block" style="margin-top: 12px;">
${e.snapshot?JSON.stringify(e.snapshot,null,2):"No snapshot yet."}
      </pre>
    </section>
  `}function yp(e){return e?.channelMeta?.length?e.channelMeta.map(t=>t.id):e?.channelOrder?.length?e.channelOrder:["whatsapp","telegram","discord","googlechat","slack","signal","imessage","nostr"]}function bp(e,t,n){const i=Ul(e,n.channelAccounts);switch(e){case"whatsapp":return vp({props:t,whatsapp:n.whatsapp,accountCountLabel:i});case"telegram":return hp({props:t,telegram:n.telegram,telegramAccounts:n.channelAccounts?.telegram??[],accountCountLabel:i});case"discord":return op({props:t,discord:n.discord,accountCountLabel:i});case"googlechat":return lp({props:t,googleChat:n.googlechat,accountCountLabel:i});case"slack":return gp({props:t,slack:n.slack,accountCountLabel:i});case"signal":return pp({props:t,signal:n.signal,accountCountLabel:i});case"imessage":return rp({props:t,imessage:n.imessage,accountCountLabel:i});case"nostr":{const s=n.channelAccounts?.nostr??[],a=s[0],o=a?.accountId??"default",r=a?.profile??null,c=t.nostrProfileAccountId===o?t.nostrProfileFormState:null,u=c?{onFieldChange:t.onNostrProfileFieldChange,onSave:t.onNostrProfileSave,onImport:t.onNostrProfileImport,onCancel:t.onNostrProfileCancel,onToggleAdvanced:t.onNostrProfileToggleAdvanced}:null;return cp({props:t,nostr:n.nostr,nostrAccounts:s,accountCountLabel:i,profileFormState:c,profileFormCallbacks:u,onEditProfile:()=>t.onNostrProfileEdit(o,r)})}default:return $p(e,t,n.channelAccounts??{})}}function $p(e,t,n){const i=kp(t.snapshot,e),s=t.snapshot?.channels?.[e],a=typeof s?.configured=="boolean"?s.configured:void 0,o=typeof s?.running=="boolean"?s.running:void 0,r=typeof s?.connected=="boolean"?s.connected:void 0,c=typeof s?.lastError=="string"?s.lastError:void 0,u=n[e]??[],f=Ul(e,n);return l`
    <div class="card">
      <div class="card-title">${i}</div>
      <div class="card-sub">Channel status and configuration.</div>
      ${f}

      ${u.length>0?l`
            <div class="account-card-list">
              ${u.map(p=>_p(p))}
            </div>
          `:l`
            <div class="status-list" style="margin-top: 16px;">
              <div>
                <span class="label">Configured</span>
                <span>${a==null?"n/a":a?"Yes":"No"}</span>
              </div>
              <div>
                <span class="label">Running</span>
                <span>${o==null?"n/a":o?"Yes":"No"}</span>
              </div>
              <div>
                <span class="label">Connected</span>
                <span>${r==null?"n/a":r?"Yes":"No"}</span>
              </div>
            </div>
          `}

      ${c?l`<div class="callout danger" style="margin-top: 12px;">
            ${c}
          </div>`:g}

      ${Te({channelId:e,props:t})}
    </div>
  `}function wp(e){return e?.channelMeta?.length?Object.fromEntries(e.channelMeta.map(t=>[t.id,t])):{}}function kp(e,t){return wp(e)[t]?.label??e?.channelLabels?.[t]??t}const Ap=600*1e3;function Kl(e){return e.lastInboundAt?Date.now()-e.lastInboundAt<Ap:!1}function xp(e){return e.running?"Yes":Kl(e)?"Active":"No"}function Sp(e){return e.connected===!0?"Yes":e.connected===!1?"No":Kl(e)?"Active":"n/a"}function _p(e){const t=xp(e),n=Sp(e);return l`
    <div class="account-card">
      <div class="account-card-header">
        <div class="account-card-title">${e.name||e.accountId}</div>
        <div class="account-card-id">${e.accountId}</div>
      </div>
      <div class="status-list account-card-status">
        <div>
          <span class="label">Running</span>
          <span>${t}</span>
        </div>
        <div>
          <span class="label">Configured</span>
          <span>${e.configured?"Yes":"No"}</span>
        </div>
        <div>
          <span class="label">Connected</span>
          <span>${n}</span>
        </div>
        <div>
          <span class="label">Last inbound</span>
          <span>${e.lastInboundAt?O(e.lastInboundAt):"n/a"}</span>
        </div>
        ${e.lastError?l`
              <div class="account-card-error">
                ${e.lastError}
              </div>
            `:g}
      </div>
    </div>
  `}const Rt=(e,t)=>{const n=e._$AN;if(n===void 0)return!1;for(const i of n)i._$AO?.(t,!1),Rt(i,t);return!0},kn=e=>{let t,n;do{if((t=e._$AM)===void 0)break;n=t._$AN,n.delete(e),e=t}while(n?.size===0)},zl=e=>{for(let t;t=e._$AM;e=t){let n=t._$AN;if(n===void 0)t._$AN=n=new Set;else if(n.has(e))break;n.add(e),Tp(t)}};function Cp(e){this._$AN!==void 0?(kn(this),this._$AM=e,zl(this)):this._$AM=e}function Ep(e,t=!1,n=0){const i=this._$AH,s=this._$AN;if(s!==void 0&&s.size!==0)if(t)if(Array.isArray(i))for(let a=n;a<i.length;a++)Rt(i[a],!1),kn(i[a]);else i!=null&&(Rt(i,!1),kn(i));else Rt(this,e)}const Tp=e=>{e.type==$s.CHILD&&(e._$AP??=Ep,e._$AQ??=Cp)};class Lp extends ks{constructor(){super(...arguments),this._$AN=void 0}_$AT(t,n,i){super._$AT(t,n,i),zl(this),this.isConnected=t._$AU}_$AO(t,n=!0){t!==this.isConnected&&(this.isConnected=t,t?this.reconnected?.():this.disconnected?.()),n&&(Rt(this,t),kn(this))}setValue(t){if(Gu(this._$Ct))this._$Ct._$AI(t,this);else{const n=[...this._$Ct._$AH];n[this._$Ci]=t,this._$Ct._$AI(n,this,0)}}disconnected(){}reconnected(){}}const hi=new WeakMap,Ip=ws(class extends Lp{render(e){return g}update(e,[t]){const n=t!==this.G;return n&&this.G!==void 0&&this.rt(void 0),(n||this.lt!==this.ct)&&(this.G=t,this.ht=e.options?.host,this.rt(this.ct=e.element)),g}rt(e){if(this.isConnected||(e=void 0),typeof this.G=="function"){const t=this.ht??globalThis;let n=hi.get(t);n===void 0&&(n=new WeakMap,hi.set(t,n)),n.get(this.G)!==void 0&&this.G.call(this.ht,void 0),n.set(this.G,e),e!==void 0&&this.G.call(this.ht,e)}else this.G.value=e}get lt(){return typeof this.G=="function"?hi.get(this.ht??globalThis)?.get(this.G):this.G?.value}disconnected(){this.lt===this.ct&&this.rt(void 0)}reconnected(){this.rt(this.ct)}});class Bi extends ks{constructor(t){if(super(t),this.it=g,t.type!==$s.CHILD)throw Error(this.constructor.directiveName+"() can only be used in child bindings")}render(t){if(t===g||t==null)return this._t=void 0,this.it=t;if(t===Me)return t;if(typeof t!="string")throw Error(this.constructor.directiveName+"() called with a non-string value");if(t===this.it)return this._t;this.it=t;const n=[t];return n.raw=n,this._t={_$litType$:this.constructor.resultType,strings:n,values:[]}}}Bi.directiveName="unsafeHTML",Bi.resultType=1;const Ui=ws(Bi);const{entries:Hl,setPrototypeOf:Qa,isFrozen:Rp,getPrototypeOf:Mp,getOwnPropertyDescriptor:Pp}=Object;let{freeze:te,seal:re,create:Ki}=Object,{apply:zi,construct:Hi}=typeof Reflect<"u"&&Reflect;te||(te=function(t){return t});re||(re=function(t){return t});zi||(zi=function(t,n){for(var i=arguments.length,s=new Array(i>2?i-2:0),a=2;a<i;a++)s[a-2]=arguments[a];return t.apply(n,s)});Hi||(Hi=function(t){for(var n=arguments.length,i=new Array(n>1?n-1:0),s=1;s<n;s++)i[s-1]=arguments[s];return new t(...i)});const on=ne(Array.prototype.forEach),Fp=ne(Array.prototype.lastIndexOf),Ja=ne(Array.prototype.pop),bt=ne(Array.prototype.push),Np=ne(Array.prototype.splice),hn=ne(String.prototype.toLowerCase),vi=ne(String.prototype.toString),mi=ne(String.prototype.match),$t=ne(String.prototype.replace),Dp=ne(String.prototype.indexOf),Op=ne(String.prototype.trim),ue=ne(Object.prototype.hasOwnProperty),X=ne(RegExp.prototype.test),wt=Bp(TypeError);function ne(e){return function(t){t instanceof RegExp&&(t.lastIndex=0);for(var n=arguments.length,i=new Array(n>1?n-1:0),s=1;s<n;s++)i[s-1]=arguments[s];return zi(e,t,i)}}function Bp(e){return function(){for(var t=arguments.length,n=new Array(t),i=0;i<t;i++)n[i]=arguments[i];return Hi(e,n)}}function M(e,t){let n=arguments.length>2&&arguments[2]!==void 0?arguments[2]:hn;Qa&&Qa(e,null);let i=t.length;for(;i--;){let s=t[i];if(typeof s=="string"){const a=n(s);a!==s&&(Rp(t)||(t[i]=a),s=a)}e[s]=!0}return e}function Up(e){for(let t=0;t<e.length;t++)ue(e,t)||(e[t]=null);return e}function be(e){const t=Ki(null);for(const[n,i]of Hl(e))ue(e,n)&&(Array.isArray(i)?t[n]=Up(i):i&&typeof i=="object"&&i.constructor===Object?t[n]=be(i):t[n]=i);return t}function kt(e,t){for(;e!==null;){const i=Pp(e,t);if(i){if(i.get)return ne(i.get);if(typeof i.value=="function")return ne(i.value)}e=Mp(e)}function n(){return null}return n}const Za=te(["a","abbr","acronym","address","area","article","aside","audio","b","bdi","bdo","big","blink","blockquote","body","br","button","canvas","caption","center","cite","code","col","colgroup","content","data","datalist","dd","decorator","del","details","dfn","dialog","dir","div","dl","dt","element","em","fieldset","figcaption","figure","font","footer","form","h1","h2","h3","h4","h5","h6","head","header","hgroup","hr","html","i","img","input","ins","kbd","label","legend","li","main","map","mark","marquee","menu","menuitem","meter","nav","nobr","ol","optgroup","option","output","p","picture","pre","progress","q","rp","rt","ruby","s","samp","search","section","select","shadow","slot","small","source","spacer","span","strike","strong","style","sub","summary","sup","table","tbody","td","template","textarea","tfoot","th","thead","time","tr","track","tt","u","ul","var","video","wbr"]),yi=te(["svg","a","altglyph","altglyphdef","altglyphitem","animatecolor","animatemotion","animatetransform","circle","clippath","defs","desc","ellipse","enterkeyhint","exportparts","filter","font","g","glyph","glyphref","hkern","image","inputmode","line","lineargradient","marker","mask","metadata","mpath","part","path","pattern","polygon","polyline","radialgradient","rect","stop","style","switch","symbol","text","textpath","title","tref","tspan","view","vkern"]),bi=te(["feBlend","feColorMatrix","feComponentTransfer","feComposite","feConvolveMatrix","feDiffuseLighting","feDisplacementMap","feDistantLight","feDropShadow","feFlood","feFuncA","feFuncB","feFuncG","feFuncR","feGaussianBlur","feImage","feMerge","feMergeNode","feMorphology","feOffset","fePointLight","feSpecularLighting","feSpotLight","feTile","feTurbulence"]),Kp=te(["animate","color-profile","cursor","discard","font-face","font-face-format","font-face-name","font-face-src","font-face-uri","foreignobject","hatch","hatchpath","mesh","meshgradient","meshpatch","meshrow","missing-glyph","script","set","solidcolor","unknown","use"]),$i=te(["math","menclose","merror","mfenced","mfrac","mglyph","mi","mlabeledtr","mmultiscripts","mn","mo","mover","mpadded","mphantom","mroot","mrow","ms","mspace","msqrt","mstyle","msub","msup","msubsup","mtable","mtd","mtext","mtr","munder","munderover","mprescripts"]),zp=te(["maction","maligngroup","malignmark","mlongdiv","mscarries","mscarry","msgroup","mstack","msline","msrow","semantics","annotation","annotation-xml","mprescripts","none"]),Xa=te(["#text"]),eo=te(["accept","action","align","alt","autocapitalize","autocomplete","autopictureinpicture","autoplay","background","bgcolor","border","capture","cellpadding","cellspacing","checked","cite","class","clear","color","cols","colspan","controls","controlslist","coords","crossorigin","datetime","decoding","default","dir","disabled","disablepictureinpicture","disableremoteplayback","download","draggable","enctype","enterkeyhint","exportparts","face","for","headers","height","hidden","high","href","hreflang","id","inert","inputmode","integrity","ismap","kind","label","lang","list","loading","loop","low","max","maxlength","media","method","min","minlength","multiple","muted","name","nonce","noshade","novalidate","nowrap","open","optimum","part","pattern","placeholder","playsinline","popover","popovertarget","popovertargetaction","poster","preload","pubdate","radiogroup","readonly","rel","required","rev","reversed","role","rows","rowspan","spellcheck","scope","selected","shape","size","sizes","slot","span","srclang","start","src","srcset","step","style","summary","tabindex","title","translate","type","usemap","valign","value","width","wrap","xmlns","slot"]),wi=te(["accent-height","accumulate","additive","alignment-baseline","amplitude","ascent","attributename","attributetype","azimuth","basefrequency","baseline-shift","begin","bias","by","class","clip","clippathunits","clip-path","clip-rule","color","color-interpolation","color-interpolation-filters","color-profile","color-rendering","cx","cy","d","dx","dy","diffuseconstant","direction","display","divisor","dur","edgemode","elevation","end","exponent","fill","fill-opacity","fill-rule","filter","filterunits","flood-color","flood-opacity","font-family","font-size","font-size-adjust","font-stretch","font-style","font-variant","font-weight","fx","fy","g1","g2","glyph-name","glyphref","gradientunits","gradienttransform","height","href","id","image-rendering","in","in2","intercept","k","k1","k2","k3","k4","kerning","keypoints","keysplines","keytimes","lang","lengthadjust","letter-spacing","kernelmatrix","kernelunitlength","lighting-color","local","marker-end","marker-mid","marker-start","markerheight","markerunits","markerwidth","maskcontentunits","maskunits","max","mask","mask-type","media","method","mode","min","name","numoctaves","offset","operator","opacity","order","orient","orientation","origin","overflow","paint-order","path","pathlength","patterncontentunits","patterntransform","patternunits","points","preservealpha","preserveaspectratio","primitiveunits","r","rx","ry","radius","refx","refy","repeatcount","repeatdur","restart","result","rotate","scale","seed","shape-rendering","slope","specularconstant","specularexponent","spreadmethod","startoffset","stddeviation","stitchtiles","stop-color","stop-opacity","stroke-dasharray","stroke-dashoffset","stroke-linecap","stroke-linejoin","stroke-miterlimit","stroke-opacity","stroke","stroke-width","style","surfacescale","systemlanguage","tabindex","tablevalues","targetx","targety","transform","transform-origin","text-anchor","text-decoration","text-rendering","textlength","type","u1","u2","unicode","values","viewbox","visibility","version","vert-adv-y","vert-origin-x","vert-origin-y","width","word-spacing","wrap","writing-mode","xchannelselector","ychannelselector","x","x1","x2","xmlns","y","y1","y2","z","zoomandpan"]),to=te(["accent","accentunder","align","bevelled","close","columnsalign","columnlines","columnspan","denomalign","depth","dir","display","displaystyle","encoding","fence","frame","height","href","id","largeop","length","linethickness","lspace","lquote","mathbackground","mathcolor","mathsize","mathvariant","maxsize","minsize","movablelimits","notation","numalign","open","rowalign","rowlines","rowspacing","rowspan","rspace","rquote","scriptlevel","scriptminsize","scriptsizemultiplier","selection","separator","separators","stretchy","subscriptshift","supscriptshift","symmetric","voffset","width","xmlns"]),ln=te(["xlink:href","xml:id","xlink:title","xml:space","xmlns:xlink"]),Hp=re(/\{\{[\w\W]*|[\w\W]*\}\}/gm),jp=re(/<%[\w\W]*|[\w\W]*%>/gm),Gp=re(/\$\{[\w\W]*/gm),qp=re(/^data-[\-\w.\u00B7-\uFFFF]+$/),Wp=re(/^aria-[\-\w]+$/),jl=re(/^(?:(?:(?:f|ht)tps?|mailto|tel|callto|sms|cid|xmpp|matrix):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i),Vp=re(/^(?:\w+script|data):/i),Yp=re(/[\u0000-\u0020\u00A0\u1680\u180E\u2000-\u2029\u205F\u3000]/g),Gl=re(/^html$/i),Qp=re(/^[a-z][.\w]*(-[.\w]+)+$/i);var no=Object.freeze({__proto__:null,ARIA_ATTR:Wp,ATTR_WHITESPACE:Yp,CUSTOM_ELEMENT:Qp,DATA_ATTR:qp,DOCTYPE_NAME:Gl,ERB_EXPR:jp,IS_ALLOWED_URI:jl,IS_SCRIPT_OR_DATA:Vp,MUSTACHE_EXPR:Hp,TMPLIT_EXPR:Gp});const At={element:1,text:3,progressingInstruction:7,comment:8,document:9},Jp=function(){return typeof window>"u"?null:window},Zp=function(t,n){if(typeof t!="object"||typeof t.createPolicy!="function")return null;let i=null;const s="data-tt-policy-suffix";n&&n.hasAttribute(s)&&(i=n.getAttribute(s));const a="dompurify"+(i?"#"+i:"");try{return t.createPolicy(a,{createHTML(o){return o},createScriptURL(o){return o}})}catch{return console.warn("TrustedTypes policy "+a+" could not be created."),null}},io=function(){return{afterSanitizeAttributes:[],afterSanitizeElements:[],afterSanitizeShadowDOM:[],beforeSanitizeAttributes:[],beforeSanitizeElements:[],beforeSanitizeShadowDOM:[],uponSanitizeAttribute:[],uponSanitizeElement:[],uponSanitizeShadowNode:[]}};function ql(){let e=arguments.length>0&&arguments[0]!==void 0?arguments[0]:Jp();const t=R=>ql(R);if(t.version="3.3.1",t.removed=[],!e||!e.document||e.document.nodeType!==At.document||!e.Element)return t.isSupported=!1,t;let{document:n}=e;const i=n,s=i.currentScript,{DocumentFragment:a,HTMLTemplateElement:o,Node:r,Element:c,NodeFilter:u,NamedNodeMap:f=e.NamedNodeMap||e.MozNamedAttrMap,HTMLFormElement:p,DOMParser:m,trustedTypes:v}=e,b=c.prototype,d=kt(b,"cloneNode"),y=kt(b,"remove"),A=kt(b,"nextSibling"),x=kt(b,"childNodes"),T=kt(b,"parentNode");if(typeof o=="function"){const R=n.createElement("template");R.content&&R.content.ownerDocument&&(n=R.content.ownerDocument)}let S,E="";const{implementation:C,createNodeIterator:P,createDocumentFragment:ce,getElementsByTagName:H}=n,{importNode:Q}=i;let D=io();t.isSupported=typeof Hl=="function"&&typeof T=="function"&&C&&C.createHTMLDocument!==void 0;const{MUSTACHE_EXPR:De,ERB_EXPR:ae,TMPLIT_EXPR:Le,DATA_ATTR:he,ARIA_ATTR:Ns,IS_SCRIPT_OR_DATA:qt,ATTR_WHITESPACE:Hn,CUSTOM_ELEMENT:fr}=no;let{IS_ALLOWED_URI:Ds}=no,j=null;const Os=M({},[...Za,...yi,...bi,...$i,...Xa]);let W=null;const Bs=M({},[...eo,...wi,...to,...ln]);let U=Object.seal(Ki(null,{tagNameCheck:{writable:!0,configurable:!1,enumerable:!0,value:null},attributeNameCheck:{writable:!0,configurable:!1,enumerable:!0,value:null},allowCustomizedBuiltInElements:{writable:!0,configurable:!1,enumerable:!0,value:!1}})),gt=null,jn=null;const et=Object.seal(Ki(null,{tagCheck:{writable:!0,configurable:!1,enumerable:!0,value:null},attributeCheck:{writable:!0,configurable:!1,enumerable:!0,value:null}}));let Us=!0,Gn=!0,Ks=!1,zs=!0,tt=!1,Wt=!0,Oe=!1,qn=!1,Wn=!1,nt=!1,Vt=!1,Yt=!1,Hs=!0,js=!1;const pr="user-content-";let Vn=!0,ht=!1,it={},ve=null;const Yn=M({},["annotation-xml","audio","colgroup","desc","foreignobject","head","iframe","math","mi","mn","mo","ms","mtext","noembed","noframes","noscript","plaintext","script","style","svg","template","thead","title","video","xmp"]);let Gs=null;const qs=M({},["audio","video","img","source","image","track"]);let Qn=null;const Ws=M({},["alt","class","for","id","label","name","pattern","placeholder","role","summary","title","value","style","xmlns"]),Qt="http://www.w3.org/1998/Math/MathML",Jt="http://www.w3.org/2000/svg",we="http://www.w3.org/1999/xhtml";let st=we,Jn=!1,Zn=null;const gr=M({},[Qt,Jt,we],vi);let Zt=M({},["mi","mo","mn","ms","mtext"]),Xt=M({},["annotation-xml"]);const hr=M({},["title","style","font","a","script"]);let vt=null;const vr=["application/xhtml+xml","text/html"],mr="text/html";let z=null,at=null;const yr=n.createElement("form"),Vs=function(h){return h instanceof RegExp||h instanceof Function},Xn=function(){let h=arguments.length>0&&arguments[0]!==void 0?arguments[0]:{};if(!(at&&at===h)){if((!h||typeof h!="object")&&(h={}),h=be(h),vt=vr.indexOf(h.PARSER_MEDIA_TYPE)===-1?mr:h.PARSER_MEDIA_TYPE,z=vt==="application/xhtml+xml"?vi:hn,j=ue(h,"ALLOWED_TAGS")?M({},h.ALLOWED_TAGS,z):Os,W=ue(h,"ALLOWED_ATTR")?M({},h.ALLOWED_ATTR,z):Bs,Zn=ue(h,"ALLOWED_NAMESPACES")?M({},h.ALLOWED_NAMESPACES,vi):gr,Qn=ue(h,"ADD_URI_SAFE_ATTR")?M(be(Ws),h.ADD_URI_SAFE_ATTR,z):Ws,Gs=ue(h,"ADD_DATA_URI_TAGS")?M(be(qs),h.ADD_DATA_URI_TAGS,z):qs,ve=ue(h,"FORBID_CONTENTS")?M({},h.FORBID_CONTENTS,z):Yn,gt=ue(h,"FORBID_TAGS")?M({},h.FORBID_TAGS,z):be({}),jn=ue(h,"FORBID_ATTR")?M({},h.FORBID_ATTR,z):be({}),it=ue(h,"USE_PROFILES")?h.USE_PROFILES:!1,Us=h.ALLOW_ARIA_ATTR!==!1,Gn=h.ALLOW_DATA_ATTR!==!1,Ks=h.ALLOW_UNKNOWN_PROTOCOLS||!1,zs=h.ALLOW_SELF_CLOSE_IN_ATTR!==!1,tt=h.SAFE_FOR_TEMPLATES||!1,Wt=h.SAFE_FOR_XML!==!1,Oe=h.WHOLE_DOCUMENT||!1,nt=h.RETURN_DOM||!1,Vt=h.RETURN_DOM_FRAGMENT||!1,Yt=h.RETURN_TRUSTED_TYPE||!1,Wn=h.FORCE_BODY||!1,Hs=h.SANITIZE_DOM!==!1,js=h.SANITIZE_NAMED_PROPS||!1,Vn=h.KEEP_CONTENT!==!1,ht=h.IN_PLACE||!1,Ds=h.ALLOWED_URI_REGEXP||jl,st=h.NAMESPACE||we,Zt=h.MATHML_TEXT_INTEGRATION_POINTS||Zt,Xt=h.HTML_INTEGRATION_POINTS||Xt,U=h.CUSTOM_ELEMENT_HANDLING||{},h.CUSTOM_ELEMENT_HANDLING&&Vs(h.CUSTOM_ELEMENT_HANDLING.tagNameCheck)&&(U.tagNameCheck=h.CUSTOM_ELEMENT_HANDLING.tagNameCheck),h.CUSTOM_ELEMENT_HANDLING&&Vs(h.CUSTOM_ELEMENT_HANDLING.attributeNameCheck)&&(U.attributeNameCheck=h.CUSTOM_ELEMENT_HANDLING.attributeNameCheck),h.CUSTOM_ELEMENT_HANDLING&&typeof h.CUSTOM_ELEMENT_HANDLING.allowCustomizedBuiltInElements=="boolean"&&(U.allowCustomizedBuiltInElements=h.CUSTOM_ELEMENT_HANDLING.allowCustomizedBuiltInElements),tt&&(Gn=!1),Vt&&(nt=!0),it&&(j=M({},Xa),W=[],it.html===!0&&(M(j,Za),M(W,eo)),it.svg===!0&&(M(j,yi),M(W,wi),M(W,ln)),it.svgFilters===!0&&(M(j,bi),M(W,wi),M(W,ln)),it.mathMl===!0&&(M(j,$i),M(W,to),M(W,ln))),h.ADD_TAGS&&(typeof h.ADD_TAGS=="function"?et.tagCheck=h.ADD_TAGS:(j===Os&&(j=be(j)),M(j,h.ADD_TAGS,z))),h.ADD_ATTR&&(typeof h.ADD_ATTR=="function"?et.attributeCheck=h.ADD_ATTR:(W===Bs&&(W=be(W)),M(W,h.ADD_ATTR,z))),h.ADD_URI_SAFE_ATTR&&M(Qn,h.ADD_URI_SAFE_ATTR,z),h.FORBID_CONTENTS&&(ve===Yn&&(ve=be(ve)),M(ve,h.FORBID_CONTENTS,z)),h.ADD_FORBID_CONTENTS&&(ve===Yn&&(ve=be(ve)),M(ve,h.ADD_FORBID_CONTENTS,z)),Vn&&(j["#text"]=!0),Oe&&M(j,["html","head","body"]),j.table&&(M(j,["tbody"]),delete gt.tbody),h.TRUSTED_TYPES_POLICY){if(typeof h.TRUSTED_TYPES_POLICY.createHTML!="function")throw wt('TRUSTED_TYPES_POLICY configuration option must provide a "createHTML" hook.');if(typeof h.TRUSTED_TYPES_POLICY.createScriptURL!="function")throw wt('TRUSTED_TYPES_POLICY configuration option must provide a "createScriptURL" hook.');S=h.TRUSTED_TYPES_POLICY,E=S.createHTML("")}else S===void 0&&(S=Zp(v,s)),S!==null&&typeof E=="string"&&(E=S.createHTML(""));te&&te(h),at=h}},Ys=M({},[...yi,...bi,...Kp]),Qs=M({},[...$i,...zp]),br=function(h){let _=T(h);(!_||!_.tagName)&&(_={namespaceURI:st,tagName:"template"});const I=hn(h.tagName),B=hn(_.tagName);return Zn[h.namespaceURI]?h.namespaceURI===Jt?_.namespaceURI===we?I==="svg":_.namespaceURI===Qt?I==="svg"&&(B==="annotation-xml"||Zt[B]):!!Ys[I]:h.namespaceURI===Qt?_.namespaceURI===we?I==="math":_.namespaceURI===Jt?I==="math"&&Xt[B]:!!Qs[I]:h.namespaceURI===we?_.namespaceURI===Jt&&!Xt[B]||_.namespaceURI===Qt&&!Zt[B]?!1:!Qs[I]&&(hr[I]||!Ys[I]):!!(vt==="application/xhtml+xml"&&Zn[h.namespaceURI]):!1},me=function(h){bt(t.removed,{element:h});try{T(h).removeChild(h)}catch{y(h)}},Be=function(h,_){try{bt(t.removed,{attribute:_.getAttributeNode(h),from:_})}catch{bt(t.removed,{attribute:null,from:_})}if(_.removeAttribute(h),h==="is")if(nt||Vt)try{me(_)}catch{}else try{_.setAttribute(h,"")}catch{}},Js=function(h){let _=null,I=null;if(Wn)h="<remove></remove>"+h;else{const K=mi(h,/^[\r\n\t ]+/);I=K&&K[0]}vt==="application/xhtml+xml"&&st===we&&(h='<html xmlns="http://www.w3.org/1999/xhtml"><head></head><body>'+h+"</body></html>");const B=S?S.createHTML(h):h;if(st===we)try{_=new m().parseFromString(B,vt)}catch{}if(!_||!_.documentElement){_=C.createDocument(st,"template",null);try{_.documentElement.innerHTML=Jn?E:B}catch{}}const J=_.body||_.documentElement;return h&&I&&J.insertBefore(n.createTextNode(I),J.childNodes[0]||null),st===we?H.call(_,Oe?"html":"body")[0]:Oe?_.documentElement:J},Zs=function(h){return P.call(h.ownerDocument||h,h,u.SHOW_ELEMENT|u.SHOW_COMMENT|u.SHOW_TEXT|u.SHOW_PROCESSING_INSTRUCTION|u.SHOW_CDATA_SECTION,null)},ei=function(h){return h instanceof p&&(typeof h.nodeName!="string"||typeof h.textContent!="string"||typeof h.removeChild!="function"||!(h.attributes instanceof f)||typeof h.removeAttribute!="function"||typeof h.setAttribute!="function"||typeof h.namespaceURI!="string"||typeof h.insertBefore!="function"||typeof h.hasChildNodes!="function")},Xs=function(h){return typeof r=="function"&&h instanceof r};function ke(R,h,_){on(R,I=>{I.call(t,h,_,at)})}const ea=function(h){let _=null;if(ke(D.beforeSanitizeElements,h,null),ei(h))return me(h),!0;const I=z(h.nodeName);if(ke(D.uponSanitizeElement,h,{tagName:I,allowedTags:j}),Wt&&h.hasChildNodes()&&!Xs(h.firstElementChild)&&X(/<[/\w!]/g,h.innerHTML)&&X(/<[/\w!]/g,h.textContent)||h.nodeType===At.progressingInstruction||Wt&&h.nodeType===At.comment&&X(/<[/\w]/g,h.data))return me(h),!0;if(!(et.tagCheck instanceof Function&&et.tagCheck(I))&&(!j[I]||gt[I])){if(!gt[I]&&na(I)&&(U.tagNameCheck instanceof RegExp&&X(U.tagNameCheck,I)||U.tagNameCheck instanceof Function&&U.tagNameCheck(I)))return!1;if(Vn&&!ve[I]){const B=T(h)||h.parentNode,J=x(h)||h.childNodes;if(J&&B){const K=J.length;for(let ie=K-1;ie>=0;--ie){const Ae=d(J[ie],!0);Ae.__removalCount=(h.__removalCount||0)+1,B.insertBefore(Ae,A(h))}}}return me(h),!0}return h instanceof c&&!br(h)||(I==="noscript"||I==="noembed"||I==="noframes")&&X(/<\/no(script|embed|frames)/i,h.innerHTML)?(me(h),!0):(tt&&h.nodeType===At.text&&(_=h.textContent,on([De,ae,Le],B=>{_=$t(_,B," ")}),h.textContent!==_&&(bt(t.removed,{element:h.cloneNode()}),h.textContent=_)),ke(D.afterSanitizeElements,h,null),!1)},ta=function(h,_,I){if(Hs&&(_==="id"||_==="name")&&(I in n||I in yr))return!1;if(!(Gn&&!jn[_]&&X(he,_))){if(!(Us&&X(Ns,_))){if(!(et.attributeCheck instanceof Function&&et.attributeCheck(_,h))){if(!W[_]||jn[_]){if(!(na(h)&&(U.tagNameCheck instanceof RegExp&&X(U.tagNameCheck,h)||U.tagNameCheck instanceof Function&&U.tagNameCheck(h))&&(U.attributeNameCheck instanceof RegExp&&X(U.attributeNameCheck,_)||U.attributeNameCheck instanceof Function&&U.attributeNameCheck(_,h))||_==="is"&&U.allowCustomizedBuiltInElements&&(U.tagNameCheck instanceof RegExp&&X(U.tagNameCheck,I)||U.tagNameCheck instanceof Function&&U.tagNameCheck(I))))return!1}else if(!Qn[_]){if(!X(Ds,$t(I,Hn,""))){if(!((_==="src"||_==="xlink:href"||_==="href")&&h!=="script"&&Dp(I,"data:")===0&&Gs[h])){if(!(Ks&&!X(qt,$t(I,Hn,"")))){if(I)return!1}}}}}}}return!0},na=function(h){return h!=="annotation-xml"&&mi(h,fr)},ia=function(h){ke(D.beforeSanitizeAttributes,h,null);const{attributes:_}=h;if(!_||ei(h))return;const I={attrName:"",attrValue:"",keepAttr:!0,allowedAttributes:W,forceKeepAttr:void 0};let B=_.length;for(;B--;){const J=_[B],{name:K,namespaceURI:ie,value:Ae}=J,ot=z(K),ti=Ae;let V=K==="value"?ti:Op(ti);if(I.attrName=ot,I.attrValue=V,I.keepAttr=!0,I.forceKeepAttr=void 0,ke(D.uponSanitizeAttribute,h,I),V=I.attrValue,js&&(ot==="id"||ot==="name")&&(Be(K,h),V=pr+V),Wt&&X(/((--!?|])>)|<\/(style|title|textarea)/i,V)){Be(K,h);continue}if(ot==="attributename"&&mi(V,"href")){Be(K,h);continue}if(I.forceKeepAttr)continue;if(!I.keepAttr){Be(K,h);continue}if(!zs&&X(/\/>/i,V)){Be(K,h);continue}tt&&on([De,ae,Le],aa=>{V=$t(V,aa," ")});const sa=z(h.nodeName);if(!ta(sa,ot,V)){Be(K,h);continue}if(S&&typeof v=="object"&&typeof v.getAttributeType=="function"&&!ie)switch(v.getAttributeType(sa,ot)){case"TrustedHTML":{V=S.createHTML(V);break}case"TrustedScriptURL":{V=S.createScriptURL(V);break}}if(V!==ti)try{ie?h.setAttributeNS(ie,K,V):h.setAttribute(K,V),ei(h)?me(h):Ja(t.removed)}catch{Be(K,h)}}ke(D.afterSanitizeAttributes,h,null)},$r=function R(h){let _=null;const I=Zs(h);for(ke(D.beforeSanitizeShadowDOM,h,null);_=I.nextNode();)ke(D.uponSanitizeShadowNode,_,null),ea(_),ia(_),_.content instanceof a&&R(_.content);ke(D.afterSanitizeShadowDOM,h,null)};return t.sanitize=function(R){let h=arguments.length>1&&arguments[1]!==void 0?arguments[1]:{},_=null,I=null,B=null,J=null;if(Jn=!R,Jn&&(R="<!-->"),typeof R!="string"&&!Xs(R))if(typeof R.toString=="function"){if(R=R.toString(),typeof R!="string")throw wt("dirty is not a string, aborting")}else throw wt("toString is not a function");if(!t.isSupported)return R;if(qn||Xn(h),t.removed=[],typeof R=="string"&&(ht=!1),ht){if(R.nodeName){const Ae=z(R.nodeName);if(!j[Ae]||gt[Ae])throw wt("root node is forbidden and cannot be sanitized in-place")}}else if(R instanceof r)_=Js("<!---->"),I=_.ownerDocument.importNode(R,!0),I.nodeType===At.element&&I.nodeName==="BODY"||I.nodeName==="HTML"?_=I:_.appendChild(I);else{if(!nt&&!tt&&!Oe&&R.indexOf("<")===-1)return S&&Yt?S.createHTML(R):R;if(_=Js(R),!_)return nt?null:Yt?E:""}_&&Wn&&me(_.firstChild);const K=Zs(ht?R:_);for(;B=K.nextNode();)ea(B),ia(B),B.content instanceof a&&$r(B.content);if(ht)return R;if(nt){if(Vt)for(J=ce.call(_.ownerDocument);_.firstChild;)J.appendChild(_.firstChild);else J=_;return(W.shadowroot||W.shadowrootmode)&&(J=Q.call(i,J,!0)),J}let ie=Oe?_.outerHTML:_.innerHTML;return Oe&&j["!doctype"]&&_.ownerDocument&&_.ownerDocument.doctype&&_.ownerDocument.doctype.name&&X(Gl,_.ownerDocument.doctype.name)&&(ie="<!DOCTYPE "+_.ownerDocument.doctype.name+`>
`+ie),tt&&on([De,ae,Le],Ae=>{ie=$t(ie,Ae," ")}),S&&Yt?S.createHTML(ie):ie},t.setConfig=function(){let R=arguments.length>0&&arguments[0]!==void 0?arguments[0]:{};Xn(R),qn=!0},t.clearConfig=function(){at=null,qn=!1},t.isValidAttribute=function(R,h,_){at||Xn({});const I=z(R),B=z(h);return ta(I,B,_)},t.addHook=function(R,h){typeof h=="function"&&bt(D[R],h)},t.removeHook=function(R,h){if(h!==void 0){const _=Fp(D[R],h);return _===-1?void 0:Np(D[R],_,1)[0]}return Ja(D[R])},t.removeHooks=function(R){D[R]=[]},t.removeAllHooks=function(){D=io()},t}var ji=ql();function Ss(){return{async:!1,breaks:!1,extensions:null,gfm:!0,hooks:null,pedantic:!1,renderer:null,silent:!1,tokenizer:null,walkTokens:null}}var Xe=Ss();function Wl(e){Xe=e}var je={exec:()=>null};function F(e,t=""){let n=typeof e=="string"?e:e.source,i={replace:(s,a)=>{let o=typeof a=="string"?a:a.source;return o=o.replace(ee.caret,"$1"),n=n.replace(s,o),i},getRegex:()=>new RegExp(n,t)};return i}var Xp=(()=>{try{return!!new RegExp("(?<=1)(?<!1)")}catch{return!1}})(),ee={codeRemoveIndent:/^(?: {1,4}| {0,3}\t)/gm,outputLinkReplace:/\\([\[\]])/g,indentCodeCompensation:/^(\s+)(?:```)/,beginningSpace:/^\s+/,endingHash:/#$/,startingSpaceChar:/^ /,endingSpaceChar:/ $/,nonSpaceChar:/[^ ]/,newLineCharGlobal:/\n/g,tabCharGlobal:/\t/g,multipleSpaceGlobal:/\s+/g,blankLine:/^[ \t]*$/,doubleBlankLine:/\n[ \t]*\n[ \t]*$/,blockquoteStart:/^ {0,3}>/,blockquoteSetextReplace:/\n {0,3}((?:=+|-+) *)(?=\n|$)/g,blockquoteSetextReplace2:/^ {0,3}>[ \t]?/gm,listReplaceNesting:/^ {1,4}(?=( {4})*[^ ])/g,listIsTask:/^\[[ xX]\] +\S/,listReplaceTask:/^\[[ xX]\] +/,listTaskCheckbox:/\[[ xX]\]/,anyLine:/\n.*\n/,hrefBrackets:/^<(.*)>$/,tableDelimiter:/[:|]/,tableAlignChars:/^\||\| *$/g,tableRowBlankLine:/\n[ \t]*$/,tableAlignRight:/^ *-+: *$/,tableAlignCenter:/^ *:-+: *$/,tableAlignLeft:/^ *:-+ *$/,startATag:/^<a /i,endATag:/^<\/a>/i,startPreScriptTag:/^<(pre|code|kbd|script)(\s|>)/i,endPreScriptTag:/^<\/(pre|code|kbd|script)(\s|>)/i,startAngleBracket:/^</,endAngleBracket:/>$/,pedanticHrefTitle:/^([^'"]*[^\s])\s+(['"])(.*)\2/,unicodeAlphaNumeric:/[\p{L}\p{N}]/u,escapeTest:/[&<>"']/,escapeReplace:/[&<>"']/g,escapeTestNoEncode:/[<>"']|&(?!(#\d{1,7}|#[Xx][a-fA-F0-9]{1,6}|\w+);)/,escapeReplaceNoEncode:/[<>"']|&(?!(#\d{1,7}|#[Xx][a-fA-F0-9]{1,6}|\w+);)/g,unescapeTest:/&(#(?:\d+)|(?:#x[0-9A-Fa-f]+)|(?:\w+));?/ig,caret:/(^|[^\[])\^/g,percentDecode:/%25/g,findPipe:/\|/g,splitPipe:/ \|/,slashPipe:/\\\|/g,carriageReturn:/\r\n|\r/g,spaceLine:/^ +$/gm,notSpaceStart:/^\S*/,endingNewline:/\n$/,listItemRegex:e=>new RegExp(`^( {0,3}${e})((?:[	 ][^\\n]*)?(?:\\n|$))`),nextBulletRegex:e=>new RegExp(`^ {0,${Math.min(3,e-1)}}(?:[*+-]|\\d{1,9}[.)])((?:[ 	][^\\n]*)?(?:\\n|$))`),hrRegex:e=>new RegExp(`^ {0,${Math.min(3,e-1)}}((?:- *){3,}|(?:_ *){3,}|(?:\\* *){3,})(?:\\n+|$)`),fencesBeginRegex:e=>new RegExp(`^ {0,${Math.min(3,e-1)}}(?:\`\`\`|~~~)`),headingBeginRegex:e=>new RegExp(`^ {0,${Math.min(3,e-1)}}#`),htmlBeginRegex:e=>new RegExp(`^ {0,${Math.min(3,e-1)}}<(?:[a-z].*>|!--)`,"i"),blockquoteBeginRegex:e=>new RegExp(`^ {0,${Math.min(3,e-1)}}>`)},eg=/^(?:[ \t]*(?:\n|$))+/,tg=/^((?: {4}| {0,3}\t)[^\n]+(?:\n(?:[ \t]*(?:\n|$))*)?)+/,ng=/^ {0,3}(`{3,}(?=[^`\n]*(?:\n|$))|~{3,})([^\n]*)(?:\n|$)(?:|([\s\S]*?)(?:\n|$))(?: {0,3}\1[~`]* *(?=\n|$)|$)/,Gt=/^ {0,3}((?:-[\t ]*){3,}|(?:_[ \t]*){3,}|(?:\*[ \t]*){3,})(?:\n+|$)/,ig=/^ {0,3}(#{1,6})(?=\s|$)(.*)(?:\n+|$)/,_s=/ {0,3}(?:[*+-]|\d{1,9}[.)])/,Vl=/^(?!bull |blockCode|fences|blockquote|heading|html|table)((?:.|\n(?!\s*?\n|bull |blockCode|fences|blockquote|heading|html|table))+?)\n {0,3}(=+|-+) *(?:\n+|$)/,Yl=F(Vl).replace(/bull/g,_s).replace(/blockCode/g,/(?: {4}| {0,3}\t)/).replace(/fences/g,/ {0,3}(?:`{3,}|~{3,})/).replace(/blockquote/g,/ {0,3}>/).replace(/heading/g,/ {0,3}#{1,6}/).replace(/html/g,/ {0,3}<[^\n>]+>\n/).replace(/\|table/g,"").getRegex(),sg=F(Vl).replace(/bull/g,_s).replace(/blockCode/g,/(?: {4}| {0,3}\t)/).replace(/fences/g,/ {0,3}(?:`{3,}|~{3,})/).replace(/blockquote/g,/ {0,3}>/).replace(/heading/g,/ {0,3}#{1,6}/).replace(/html/g,/ {0,3}<[^\n>]+>\n/).replace(/table/g,/ {0,3}\|?(?:[:\- ]*\|)+[\:\- ]*\n/).getRegex(),Cs=/^([^\n]+(?:\n(?!hr|heading|lheading|blockquote|fences|list|html|table| +\n)[^\n]+)*)/,ag=/^[^\n]+/,Es=/(?!\s*\])(?:\\[\s\S]|[^\[\]\\])+/,og=F(/^ {0,3}\[(label)\]: *(?:\n[ \t]*)?([^<\s][^\s]*|<.*?>)(?:(?: +(?:\n[ \t]*)?| *\n[ \t]*)(title))? *(?:\n+|$)/).replace("label",Es).replace("title",/(?:"(?:\\"?|[^"\\])*"|'[^'\n]*(?:\n[^'\n]+)*\n?'|\([^()]*\))/).getRegex(),lg=F(/^(bull)([ \t][^\n]+?)?(?:\n|$)/).replace(/bull/g,_s).getRegex(),Un="address|article|aside|base|basefont|blockquote|body|caption|center|col|colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|footer|form|frame|frameset|h[1-6]|head|header|hr|html|iframe|legend|li|link|main|menu|menuitem|meta|nav|noframes|ol|optgroup|option|p|param|search|section|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul",Ts=/<!--(?:-?>|[\s\S]*?(?:-->|$))/,rg=F("^ {0,3}(?:<(script|pre|style|textarea)[\\s>][\\s\\S]*?(?:</\\1>[^\\n]*\\n+|$)|comment[^\\n]*(\\n+|$)|<\\?[\\s\\S]*?(?:\\?>\\n*|$)|<![A-Z][\\s\\S]*?(?:>\\n*|$)|<!\\[CDATA\\[[\\s\\S]*?(?:\\]\\]>\\n*|$)|</?(tag)(?: +|\\n|/?>)[\\s\\S]*?(?:(?:\\n[ 	]*)+\\n|$)|<(?!script|pre|style|textarea)([a-z][\\w-]*)(?:attribute)*? */?>(?=[ \\t]*(?:\\n|$))[\\s\\S]*?(?:(?:\\n[ 	]*)+\\n|$)|</(?!script|pre|style|textarea)[a-z][\\w-]*\\s*>(?=[ \\t]*(?:\\n|$))[\\s\\S]*?(?:(?:\\n[ 	]*)+\\n|$))","i").replace("comment",Ts).replace("tag",Un).replace("attribute",/ +[a-zA-Z:_][\w.:-]*(?: *= *"[^"\n]*"| *= *'[^'\n]*'| *= *[^\s"'=<>`]+)?/).getRegex(),Ql=F(Cs).replace("hr",Gt).replace("heading"," {0,3}#{1,6}(?:\\s|$)").replace("|lheading","").replace("|table","").replace("blockquote"," {0,3}>").replace("fences"," {0,3}(?:`{3,}(?=[^`\\n]*\\n)|~{3,})[^\\n]*\\n").replace("list"," {0,3}(?:[*+-]|1[.)])[ \\t]").replace("html","</?(?:tag)(?: +|\\n|/?>)|<(?:script|pre|style|textarea|!--)").replace("tag",Un).getRegex(),cg=F(/^( {0,3}> ?(paragraph|[^\n]*)(?:\n|$))+/).replace("paragraph",Ql).getRegex(),Ls={blockquote:cg,code:tg,def:og,fences:ng,heading:ig,hr:Gt,html:rg,lheading:Yl,list:lg,newline:eg,paragraph:Ql,table:je,text:ag},so=F("^ *([^\\n ].*)\\n {0,3}((?:\\| *)?:?-+:? *(?:\\| *:?-+:? *)*(?:\\| *)?)(?:\\n((?:(?! *\\n|hr|heading|blockquote|code|fences|list|html).*(?:\\n|$))*)\\n*|$)").replace("hr",Gt).replace("heading"," {0,3}#{1,6}(?:\\s|$)").replace("blockquote"," {0,3}>").replace("code","(?: {4}| {0,3}	)[^\\n]").replace("fences"," {0,3}(?:`{3,}(?=[^`\\n]*\\n)|~{3,})[^\\n]*\\n").replace("list"," {0,3}(?:[*+-]|1[.)])[ \\t]").replace("html","</?(?:tag)(?: +|\\n|/?>)|<(?:script|pre|style|textarea|!--)").replace("tag",Un).getRegex(),dg={...Ls,lheading:sg,table:so,paragraph:F(Cs).replace("hr",Gt).replace("heading"," {0,3}#{1,6}(?:\\s|$)").replace("|lheading","").replace("table",so).replace("blockquote"," {0,3}>").replace("fences"," {0,3}(?:`{3,}(?=[^`\\n]*\\n)|~{3,})[^\\n]*\\n").replace("list"," {0,3}(?:[*+-]|1[.)])[ \\t]").replace("html","</?(?:tag)(?: +|\\n|/?>)|<(?:script|pre|style|textarea|!--)").replace("tag",Un).getRegex()},ug={...Ls,html:F(`^ *(?:comment *(?:\\n|\\s*$)|<(tag)[\\s\\S]+?</\\1> *(?:\\n{2,}|\\s*$)|<tag(?:"[^"]*"|'[^']*'|\\s[^'"/>\\s]*)*?/?> *(?:\\n{2,}|\\s*$))`).replace("comment",Ts).replace(/tag/g,"(?!(?:a|em|strong|small|s|cite|q|dfn|abbr|data|time|code|var|samp|kbd|sub|sup|i|b|u|mark|ruby|rt|rp|bdi|bdo|span|br|wbr|ins|del|img)\\b)\\w+(?!:|[^\\w\\s@]*@)\\b").getRegex(),def:/^ *\[([^\]]+)\]: *<?([^\s>]+)>?(?: +(["(][^\n]+[")]))? *(?:\n+|$)/,heading:/^(#{1,6})(.*)(?:\n+|$)/,fences:je,lheading:/^(.+?)\n {0,3}(=+|-+) *(?:\n+|$)/,paragraph:F(Cs).replace("hr",Gt).replace("heading",` *#{1,6} *[^
]`).replace("lheading",Yl).replace("|table","").replace("blockquote"," {0,3}>").replace("|fences","").replace("|list","").replace("|html","").replace("|tag","").getRegex()},fg=/^\\([!"#$%&'()*+,\-./:;<=>?@\[\]\\^_`{|}~])/,pg=/^(`+)([^`]|[^`][\s\S]*?[^`])\1(?!`)/,Jl=/^( {2,}|\\)\n(?!\s*$)/,gg=/^(`+|[^`])(?:(?= {2,}\n)|[\s\S]*?(?:(?=[\\<!\[`*_]|\b_|$)|[^ ](?= {2,}\n)))/,Kn=/[\p{P}\p{S}]/u,Is=/[\s\p{P}\p{S}]/u,Zl=/[^\s\p{P}\p{S}]/u,hg=F(/^((?![*_])punctSpace)/,"u").replace(/punctSpace/g,Is).getRegex(),Xl=/(?!~)[\p{P}\p{S}]/u,vg=/(?!~)[\s\p{P}\p{S}]/u,mg=/(?:[^\s\p{P}\p{S}]|~)/u,er=/(?![*_])[\p{P}\p{S}]/u,yg=/(?![*_])[\s\p{P}\p{S}]/u,bg=/(?:[^\s\p{P}\p{S}]|[*_])/u,$g=F(/link|precode-code|html/,"g").replace("link",/\[(?:[^\[\]`]|(?<a>`+)[^`]+\k<a>(?!`))*?\]\((?:\\[\s\S]|[^\\\(\)]|\((?:\\[\s\S]|[^\\\(\)])*\))*\)/).replace("precode-",Xp?"(?<!`)()":"(^^|[^`])").replace("code",/(?<b>`+)[^`]+\k<b>(?!`)/).replace("html",/<(?! )[^<>]*?>/).getRegex(),tr=/^(?:\*+(?:((?!\*)punct)|[^\s*]))|^_+(?:((?!_)punct)|([^\s_]))/,wg=F(tr,"u").replace(/punct/g,Kn).getRegex(),kg=F(tr,"u").replace(/punct/g,Xl).getRegex(),nr="^[^_*]*?__[^_*]*?\\*[^_*]*?(?=__)|[^*]+(?=[^*])|(?!\\*)punct(\\*+)(?=[\\s]|$)|notPunctSpace(\\*+)(?!\\*)(?=punctSpace|$)|(?!\\*)punctSpace(\\*+)(?=notPunctSpace)|[\\s](\\*+)(?!\\*)(?=punct)|(?!\\*)punct(\\*+)(?!\\*)(?=punct)|notPunctSpace(\\*+)(?=notPunctSpace)",Ag=F(nr,"gu").replace(/notPunctSpace/g,Zl).replace(/punctSpace/g,Is).replace(/punct/g,Kn).getRegex(),xg=F(nr,"gu").replace(/notPunctSpace/g,mg).replace(/punctSpace/g,vg).replace(/punct/g,Xl).getRegex(),Sg=F("^[^_*]*?\\*\\*[^_*]*?_[^_*]*?(?=\\*\\*)|[^_]+(?=[^_])|(?!_)punct(_+)(?=[\\s]|$)|notPunctSpace(_+)(?!_)(?=punctSpace|$)|(?!_)punctSpace(_+)(?=notPunctSpace)|[\\s](_+)(?!_)(?=punct)|(?!_)punct(_+)(?!_)(?=punct)","gu").replace(/notPunctSpace/g,Zl).replace(/punctSpace/g,Is).replace(/punct/g,Kn).getRegex(),_g=F(/^~~?(?:((?!~)punct)|[^\s~])/,"u").replace(/punct/g,er).getRegex(),Cg="^[^~]+(?=[^~])|(?!~)punct(~~?)(?=[\\s]|$)|notPunctSpace(~~?)(?!~)(?=punctSpace|$)|(?!~)punctSpace(~~?)(?=notPunctSpace)|[\\s](~~?)(?!~)(?=punct)|(?!~)punct(~~?)(?!~)(?=punct)|notPunctSpace(~~?)(?=notPunctSpace)",Eg=F(Cg,"gu").replace(/notPunctSpace/g,bg).replace(/punctSpace/g,yg).replace(/punct/g,er).getRegex(),Tg=F(/\\(punct)/,"gu").replace(/punct/g,Kn).getRegex(),Lg=F(/^<(scheme:[^\s\x00-\x1f<>]*|email)>/).replace("scheme",/[a-zA-Z][a-zA-Z0-9+.-]{1,31}/).replace("email",/[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+(@)[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+(?![-_])/).getRegex(),Ig=F(Ts).replace("(?:-->|$)","-->").getRegex(),Rg=F("^comment|^</[a-zA-Z][\\w:-]*\\s*>|^<[a-zA-Z][\\w-]*(?:attribute)*?\\s*/?>|^<\\?[\\s\\S]*?\\?>|^<![a-zA-Z]+\\s[\\s\\S]*?>|^<!\\[CDATA\\[[\\s\\S]*?\\]\\]>").replace("comment",Ig).replace("attribute",/\s+[a-zA-Z:_][\w.:-]*(?:\s*=\s*"[^"]*"|\s*=\s*'[^']*'|\s*=\s*[^\s"'=<>`]+)?/).getRegex(),An=/(?:\[(?:\\[\s\S]|[^\[\]\\])*\]|\\[\s\S]|`+[^`]*?`+(?!`)|[^\[\]\\`])*?/,Mg=F(/^!?\[(label)\]\(\s*(href)(?:(?:[ \t]*(?:\n[ \t]*)?)(title))?\s*\)/).replace("label",An).replace("href",/<(?:\\.|[^\n<>\\])+>|[^ \t\n\x00-\x1f]*/).replace("title",/"(?:\\"?|[^"\\])*"|'(?:\\'?|[^'\\])*'|\((?:\\\)?|[^)\\])*\)/).getRegex(),ir=F(/^!?\[(label)\]\[(ref)\]/).replace("label",An).replace("ref",Es).getRegex(),sr=F(/^!?\[(ref)\](?:\[\])?/).replace("ref",Es).getRegex(),Pg=F("reflink|nolink(?!\\()","g").replace("reflink",ir).replace("nolink",sr).getRegex(),ao=/[hH][tT][tT][pP][sS]?|[fF][tT][pP]/,Rs={_backpedal:je,anyPunctuation:Tg,autolink:Lg,blockSkip:$g,br:Jl,code:pg,del:je,delLDelim:je,delRDelim:je,emStrongLDelim:wg,emStrongRDelimAst:Ag,emStrongRDelimUnd:Sg,escape:fg,link:Mg,nolink:sr,punctuation:hg,reflink:ir,reflinkSearch:Pg,tag:Rg,text:gg,url:je},Fg={...Rs,link:F(/^!?\[(label)\]\((.*?)\)/).replace("label",An).getRegex(),reflink:F(/^!?\[(label)\]\s*\[([^\]]*)\]/).replace("label",An).getRegex()},Gi={...Rs,emStrongRDelimAst:xg,emStrongLDelim:kg,delLDelim:_g,delRDelim:Eg,url:F(/^((?:protocol):\/\/|www\.)(?:[a-zA-Z0-9\-]+\.?)+[^\s<]*|^email/).replace("protocol",ao).replace("email",/[A-Za-z0-9._+-]+(@)[a-zA-Z0-9-_]+(?:\.[a-zA-Z0-9-_]*[a-zA-Z0-9])+(?![-_])/).getRegex(),_backpedal:/(?:[^?!.,:;*_'"~()&]+|\([^)]*\)|&(?![a-zA-Z0-9]+;$)|[?!.,:;*_'"~)]+(?!$))+/,del:/^(~~?)(?=[^\s~])((?:\\[\s\S]|[^\\])*?(?:\\[\s\S]|[^\s~\\]))\1(?=[^~]|$)/,text:F(/^([`~]+|[^`~])(?:(?= {2,}\n)|(?=[a-zA-Z0-9.!#$%&'*+\/=?_`{\|}~-]+@)|[\s\S]*?(?:(?=[\\<!\[`*~_]|\b_|protocol:\/\/|www\.|$)|[^ ](?= {2,}\n)|[^a-zA-Z0-9.!#$%&'*+\/=?_`{\|}~-](?=[a-zA-Z0-9.!#$%&'*+\/=?_`{\|}~-]+@)))/).replace("protocol",ao).getRegex()},Ng={...Gi,br:F(Jl).replace("{2,}","*").getRegex(),text:F(Gi.text).replace("\\b_","\\b_| {2,}\\n").replace(/\{2,\}/g,"*").getRegex()},rn={normal:Ls,gfm:dg,pedantic:ug},xt={normal:Rs,gfm:Gi,breaks:Ng,pedantic:Fg},Dg={"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"},oo=e=>Dg[e];function Se(e,t){if(t){if(ee.escapeTest.test(e))return e.replace(ee.escapeReplace,oo)}else if(ee.escapeTestNoEncode.test(e))return e.replace(ee.escapeReplaceNoEncode,oo);return e}function lo(e){try{e=encodeURI(e).replace(ee.percentDecode,"%")}catch{return null}return e}function ro(e,t){let n=e.replace(ee.findPipe,(a,o,r)=>{let c=!1,u=o;for(;--u>=0&&r[u]==="\\";)c=!c;return c?"|":" |"}),i=n.split(ee.splitPipe),s=0;if(i[0].trim()||i.shift(),i.length>0&&!i.at(-1)?.trim()&&i.pop(),t)if(i.length>t)i.splice(t);else for(;i.length<t;)i.push("");for(;s<i.length;s++)i[s]=i[s].trim().replace(ee.slashPipe,"|");return i}function St(e,t,n){let i=e.length;if(i===0)return"";let s=0;for(;s<i&&e.charAt(i-s-1)===t;)s++;return e.slice(0,i-s)}function Og(e,t){if(e.indexOf(t[1])===-1)return-1;let n=0;for(let i=0;i<e.length;i++)if(e[i]==="\\")i++;else if(e[i]===t[0])n++;else if(e[i]===t[1]&&(n--,n<0))return i;return n>0?-2:-1}function Bg(e,t=0){let n=t,i="";for(let s of e)if(s==="	"){let a=4-n%4;i+=" ".repeat(a),n+=a}else i+=s,n++;return i}function co(e,t,n,i,s){let a=t.href,o=t.title||null,r=e[1].replace(s.other.outputLinkReplace,"$1");i.state.inLink=!0;let c={type:e[0].charAt(0)==="!"?"image":"link",raw:n,href:a,title:o,text:r,tokens:i.inlineTokens(r)};return i.state.inLink=!1,c}function Ug(e,t,n){let i=e.match(n.other.indentCodeCompensation);if(i===null)return t;let s=i[1];return t.split(`
`).map(a=>{let o=a.match(n.other.beginningSpace);if(o===null)return a;let[r]=o;return r.length>=s.length?a.slice(s.length):a}).join(`
`)}var xn=class{options;rules;lexer;constructor(e){this.options=e||Xe}space(e){let t=this.rules.block.newline.exec(e);if(t&&t[0].length>0)return{type:"space",raw:t[0]}}code(e){let t=this.rules.block.code.exec(e);if(t){let n=t[0].replace(this.rules.other.codeRemoveIndent,"");return{type:"code",raw:t[0],codeBlockStyle:"indented",text:this.options.pedantic?n:St(n,`
`)}}}fences(e){let t=this.rules.block.fences.exec(e);if(t){let n=t[0],i=Ug(n,t[3]||"",this.rules);return{type:"code",raw:n,lang:t[2]?t[2].trim().replace(this.rules.inline.anyPunctuation,"$1"):t[2],text:i}}}heading(e){let t=this.rules.block.heading.exec(e);if(t){let n=t[2].trim();if(this.rules.other.endingHash.test(n)){let i=St(n,"#");(this.options.pedantic||!i||this.rules.other.endingSpaceChar.test(i))&&(n=i.trim())}return{type:"heading",raw:t[0],depth:t[1].length,text:n,tokens:this.lexer.inline(n)}}}hr(e){let t=this.rules.block.hr.exec(e);if(t)return{type:"hr",raw:St(t[0],`
`)}}blockquote(e){let t=this.rules.block.blockquote.exec(e);if(t){let n=St(t[0],`
`).split(`
`),i="",s="",a=[];for(;n.length>0;){let o=!1,r=[],c;for(c=0;c<n.length;c++)if(this.rules.other.blockquoteStart.test(n[c]))r.push(n[c]),o=!0;else if(!o)r.push(n[c]);else break;n=n.slice(c);let u=r.join(`
`),f=u.replace(this.rules.other.blockquoteSetextReplace,`
    $1`).replace(this.rules.other.blockquoteSetextReplace2,"");i=i?`${i}
${u}`:u,s=s?`${s}
${f}`:f;let p=this.lexer.state.top;if(this.lexer.state.top=!0,this.lexer.blockTokens(f,a,!0),this.lexer.state.top=p,n.length===0)break;let m=a.at(-1);if(m?.type==="code")break;if(m?.type==="blockquote"){let v=m,b=v.raw+`
`+n.join(`
`),d=this.blockquote(b);a[a.length-1]=d,i=i.substring(0,i.length-v.raw.length)+d.raw,s=s.substring(0,s.length-v.text.length)+d.text;break}else if(m?.type==="list"){let v=m,b=v.raw+`
`+n.join(`
`),d=this.list(b);a[a.length-1]=d,i=i.substring(0,i.length-m.raw.length)+d.raw,s=s.substring(0,s.length-v.raw.length)+d.raw,n=b.substring(a.at(-1).raw.length).split(`
`);continue}}return{type:"blockquote",raw:i,tokens:a,text:s}}}list(e){let t=this.rules.block.list.exec(e);if(t){let n=t[1].trim(),i=n.length>1,s={type:"list",raw:"",ordered:i,start:i?+n.slice(0,-1):"",loose:!1,items:[]};n=i?`\\d{1,9}\\${n.slice(-1)}`:`\\${n}`,this.options.pedantic&&(n=i?n:"[*+-]");let a=this.rules.other.listItemRegex(n),o=!1;for(;e;){let c=!1,u="",f="";if(!(t=a.exec(e))||this.rules.block.hr.test(e))break;u=t[0],e=e.substring(u.length);let p=Bg(t[2].split(`
`,1)[0],t[1].length),m=e.split(`
`,1)[0],v=!p.trim(),b=0;if(this.options.pedantic?(b=2,f=p.trimStart()):v?b=t[1].length+1:(b=p.search(this.rules.other.nonSpaceChar),b=b>4?1:b,f=p.slice(b),b+=t[1].length),v&&this.rules.other.blankLine.test(m)&&(u+=m+`
`,e=e.substring(m.length+1),c=!0),!c){let d=this.rules.other.nextBulletRegex(b),y=this.rules.other.hrRegex(b),A=this.rules.other.fencesBeginRegex(b),x=this.rules.other.headingBeginRegex(b),T=this.rules.other.htmlBeginRegex(b),S=this.rules.other.blockquoteBeginRegex(b);for(;e;){let E=e.split(`
`,1)[0],C;if(m=E,this.options.pedantic?(m=m.replace(this.rules.other.listReplaceNesting,"  "),C=m):C=m.replace(this.rules.other.tabCharGlobal,"    "),A.test(m)||x.test(m)||T.test(m)||S.test(m)||d.test(m)||y.test(m))break;if(C.search(this.rules.other.nonSpaceChar)>=b||!m.trim())f+=`
`+C.slice(b);else{if(v||p.replace(this.rules.other.tabCharGlobal,"    ").search(this.rules.other.nonSpaceChar)>=4||A.test(p)||x.test(p)||y.test(p))break;f+=`
`+m}v=!m.trim(),u+=E+`
`,e=e.substring(E.length+1),p=C.slice(b)}}s.loose||(o?s.loose=!0:this.rules.other.doubleBlankLine.test(u)&&(o=!0)),s.items.push({type:"list_item",raw:u,task:!!this.options.gfm&&this.rules.other.listIsTask.test(f),loose:!1,text:f,tokens:[]}),s.raw+=u}let r=s.items.at(-1);if(r)r.raw=r.raw.trimEnd(),r.text=r.text.trimEnd();else return;s.raw=s.raw.trimEnd();for(let c of s.items){if(this.lexer.state.top=!1,c.tokens=this.lexer.blockTokens(c.text,[]),c.task){if(c.text=c.text.replace(this.rules.other.listReplaceTask,""),c.tokens[0]?.type==="text"||c.tokens[0]?.type==="paragraph"){c.tokens[0].raw=c.tokens[0].raw.replace(this.rules.other.listReplaceTask,""),c.tokens[0].text=c.tokens[0].text.replace(this.rules.other.listReplaceTask,"");for(let f=this.lexer.inlineQueue.length-1;f>=0;f--)if(this.rules.other.listIsTask.test(this.lexer.inlineQueue[f].src)){this.lexer.inlineQueue[f].src=this.lexer.inlineQueue[f].src.replace(this.rules.other.listReplaceTask,"");break}}let u=this.rules.other.listTaskCheckbox.exec(c.raw);if(u){let f={type:"checkbox",raw:u[0]+" ",checked:u[0]!=="[ ]"};c.checked=f.checked,s.loose?c.tokens[0]&&["paragraph","text"].includes(c.tokens[0].type)&&"tokens"in c.tokens[0]&&c.tokens[0].tokens?(c.tokens[0].raw=f.raw+c.tokens[0].raw,c.tokens[0].text=f.raw+c.tokens[0].text,c.tokens[0].tokens.unshift(f)):c.tokens.unshift({type:"paragraph",raw:f.raw,text:f.raw,tokens:[f]}):c.tokens.unshift(f)}}if(!s.loose){let u=c.tokens.filter(p=>p.type==="space"),f=u.length>0&&u.some(p=>this.rules.other.anyLine.test(p.raw));s.loose=f}}if(s.loose)for(let c of s.items){c.loose=!0;for(let u of c.tokens)u.type==="text"&&(u.type="paragraph")}return s}}html(e){let t=this.rules.block.html.exec(e);if(t)return{type:"html",block:!0,raw:t[0],pre:t[1]==="pre"||t[1]==="script"||t[1]==="style",text:t[0]}}def(e){let t=this.rules.block.def.exec(e);if(t){let n=t[1].toLowerCase().replace(this.rules.other.multipleSpaceGlobal," "),i=t[2]?t[2].replace(this.rules.other.hrefBrackets,"$1").replace(this.rules.inline.anyPunctuation,"$1"):"",s=t[3]?t[3].substring(1,t[3].length-1).replace(this.rules.inline.anyPunctuation,"$1"):t[3];return{type:"def",tag:n,raw:t[0],href:i,title:s}}}table(e){let t=this.rules.block.table.exec(e);if(!t||!this.rules.other.tableDelimiter.test(t[2]))return;let n=ro(t[1]),i=t[2].replace(this.rules.other.tableAlignChars,"").split("|"),s=t[3]?.trim()?t[3].replace(this.rules.other.tableRowBlankLine,"").split(`
`):[],a={type:"table",raw:t[0],header:[],align:[],rows:[]};if(n.length===i.length){for(let o of i)this.rules.other.tableAlignRight.test(o)?a.align.push("right"):this.rules.other.tableAlignCenter.test(o)?a.align.push("center"):this.rules.other.tableAlignLeft.test(o)?a.align.push("left"):a.align.push(null);for(let o=0;o<n.length;o++)a.header.push({text:n[o],tokens:this.lexer.inline(n[o]),header:!0,align:a.align[o]});for(let o of s)a.rows.push(ro(o,a.header.length).map((r,c)=>({text:r,tokens:this.lexer.inline(r),header:!1,align:a.align[c]})));return a}}lheading(e){let t=this.rules.block.lheading.exec(e);if(t)return{type:"heading",raw:t[0],depth:t[2].charAt(0)==="="?1:2,text:t[1],tokens:this.lexer.inline(t[1])}}paragraph(e){let t=this.rules.block.paragraph.exec(e);if(t){let n=t[1].charAt(t[1].length-1)===`
`?t[1].slice(0,-1):t[1];return{type:"paragraph",raw:t[0],text:n,tokens:this.lexer.inline(n)}}}text(e){let t=this.rules.block.text.exec(e);if(t)return{type:"text",raw:t[0],text:t[0],tokens:this.lexer.inline(t[0])}}escape(e){let t=this.rules.inline.escape.exec(e);if(t)return{type:"escape",raw:t[0],text:t[1]}}tag(e){let t=this.rules.inline.tag.exec(e);if(t)return!this.lexer.state.inLink&&this.rules.other.startATag.test(t[0])?this.lexer.state.inLink=!0:this.lexer.state.inLink&&this.rules.other.endATag.test(t[0])&&(this.lexer.state.inLink=!1),!this.lexer.state.inRawBlock&&this.rules.other.startPreScriptTag.test(t[0])?this.lexer.state.inRawBlock=!0:this.lexer.state.inRawBlock&&this.rules.other.endPreScriptTag.test(t[0])&&(this.lexer.state.inRawBlock=!1),{type:"html",raw:t[0],inLink:this.lexer.state.inLink,inRawBlock:this.lexer.state.inRawBlock,block:!1,text:t[0]}}link(e){let t=this.rules.inline.link.exec(e);if(t){let n=t[2].trim();if(!this.options.pedantic&&this.rules.other.startAngleBracket.test(n)){if(!this.rules.other.endAngleBracket.test(n))return;let a=St(n.slice(0,-1),"\\");if((n.length-a.length)%2===0)return}else{let a=Og(t[2],"()");if(a===-2)return;if(a>-1){let o=(t[0].indexOf("!")===0?5:4)+t[1].length+a;t[2]=t[2].substring(0,a),t[0]=t[0].substring(0,o).trim(),t[3]=""}}let i=t[2],s="";if(this.options.pedantic){let a=this.rules.other.pedanticHrefTitle.exec(i);a&&(i=a[1],s=a[3])}else s=t[3]?t[3].slice(1,-1):"";return i=i.trim(),this.rules.other.startAngleBracket.test(i)&&(this.options.pedantic&&!this.rules.other.endAngleBracket.test(n)?i=i.slice(1):i=i.slice(1,-1)),co(t,{href:i&&i.replace(this.rules.inline.anyPunctuation,"$1"),title:s&&s.replace(this.rules.inline.anyPunctuation,"$1")},t[0],this.lexer,this.rules)}}reflink(e,t){let n;if((n=this.rules.inline.reflink.exec(e))||(n=this.rules.inline.nolink.exec(e))){let i=(n[2]||n[1]).replace(this.rules.other.multipleSpaceGlobal," "),s=t[i.toLowerCase()];if(!s){let a=n[0].charAt(0);return{type:"text",raw:a,text:a}}return co(n,s,n[0],this.lexer,this.rules)}}emStrong(e,t,n=""){let i=this.rules.inline.emStrongLDelim.exec(e);if(!(!i||i[3]&&n.match(this.rules.other.unicodeAlphaNumeric))&&(!(i[1]||i[2])||!n||this.rules.inline.punctuation.exec(n))){let s=[...i[0]].length-1,a,o,r=s,c=0,u=i[0][0]==="*"?this.rules.inline.emStrongRDelimAst:this.rules.inline.emStrongRDelimUnd;for(u.lastIndex=0,t=t.slice(-1*e.length+s);(i=u.exec(t))!=null;){if(a=i[1]||i[2]||i[3]||i[4]||i[5]||i[6],!a)continue;if(o=[...a].length,i[3]||i[4]){r+=o;continue}else if((i[5]||i[6])&&s%3&&!((s+o)%3)){c+=o;continue}if(r-=o,r>0)continue;o=Math.min(o,o+r+c);let f=[...i[0]][0].length,p=e.slice(0,s+i.index+f+o);if(Math.min(s,o)%2){let v=p.slice(1,-1);return{type:"em",raw:p,text:v,tokens:this.lexer.inlineTokens(v)}}let m=p.slice(2,-2);return{type:"strong",raw:p,text:m,tokens:this.lexer.inlineTokens(m)}}}}codespan(e){let t=this.rules.inline.code.exec(e);if(t){let n=t[2].replace(this.rules.other.newLineCharGlobal," "),i=this.rules.other.nonSpaceChar.test(n),s=this.rules.other.startingSpaceChar.test(n)&&this.rules.other.endingSpaceChar.test(n);return i&&s&&(n=n.substring(1,n.length-1)),{type:"codespan",raw:t[0],text:n}}}br(e){let t=this.rules.inline.br.exec(e);if(t)return{type:"br",raw:t[0]}}del(e,t,n=""){let i=this.rules.inline.delLDelim.exec(e);if(i&&(!i[1]||!n||this.rules.inline.punctuation.exec(n))){let s=[...i[0]].length-1,a,o,r=s,c=this.rules.inline.delRDelim;for(c.lastIndex=0,t=t.slice(-1*e.length+s);(i=c.exec(t))!=null;){if(a=i[1]||i[2]||i[3]||i[4]||i[5]||i[6],!a||(o=[...a].length,o!==s))continue;if(i[3]||i[4]){r+=o;continue}if(r-=o,r>0)continue;o=Math.min(o,o+r);let u=[...i[0]][0].length,f=e.slice(0,s+i.index+u+o),p=f.slice(s,-s);return{type:"del",raw:f,text:p,tokens:this.lexer.inlineTokens(p)}}}}autolink(e){let t=this.rules.inline.autolink.exec(e);if(t){let n,i;return t[2]==="@"?(n=t[1],i="mailto:"+n):(n=t[1],i=n),{type:"link",raw:t[0],text:n,href:i,tokens:[{type:"text",raw:n,text:n}]}}}url(e){let t;if(t=this.rules.inline.url.exec(e)){let n,i;if(t[2]==="@")n=t[0],i="mailto:"+n;else{let s;do s=t[0],t[0]=this.rules.inline._backpedal.exec(t[0])?.[0]??"";while(s!==t[0]);n=t[0],t[1]==="www."?i="http://"+t[0]:i=t[0]}return{type:"link",raw:t[0],text:n,href:i,tokens:[{type:"text",raw:n,text:n}]}}}inlineText(e){let t=this.rules.inline.text.exec(e);if(t){let n=this.lexer.state.inRawBlock;return{type:"text",raw:t[0],text:t[0],escaped:n}}}},fe=class qi{tokens;options;state;inlineQueue;tokenizer;constructor(t){this.tokens=[],this.tokens.links=Object.create(null),this.options=t||Xe,this.options.tokenizer=this.options.tokenizer||new xn,this.tokenizer=this.options.tokenizer,this.tokenizer.options=this.options,this.tokenizer.lexer=this,this.inlineQueue=[],this.state={inLink:!1,inRawBlock:!1,top:!0};let n={other:ee,block:rn.normal,inline:xt.normal};this.options.pedantic?(n.block=rn.pedantic,n.inline=xt.pedantic):this.options.gfm&&(n.block=rn.gfm,this.options.breaks?n.inline=xt.breaks:n.inline=xt.gfm),this.tokenizer.rules=n}static get rules(){return{block:rn,inline:xt}}static lex(t,n){return new qi(n).lex(t)}static lexInline(t,n){return new qi(n).inlineTokens(t)}lex(t){t=t.replace(ee.carriageReturn,`
`),this.blockTokens(t,this.tokens);for(let n=0;n<this.inlineQueue.length;n++){let i=this.inlineQueue[n];this.inlineTokens(i.src,i.tokens)}return this.inlineQueue=[],this.tokens}blockTokens(t,n=[],i=!1){for(this.options.pedantic&&(t=t.replace(ee.tabCharGlobal,"    ").replace(ee.spaceLine,""));t;){let s;if(this.options.extensions?.block?.some(o=>(s=o.call({lexer:this},t,n))?(t=t.substring(s.raw.length),n.push(s),!0):!1))continue;if(s=this.tokenizer.space(t)){t=t.substring(s.raw.length);let o=n.at(-1);s.raw.length===1&&o!==void 0?o.raw+=`
`:n.push(s);continue}if(s=this.tokenizer.code(t)){t=t.substring(s.raw.length);let o=n.at(-1);o?.type==="paragraph"||o?.type==="text"?(o.raw+=(o.raw.endsWith(`
`)?"":`
`)+s.raw,o.text+=`
`+s.text,this.inlineQueue.at(-1).src=o.text):n.push(s);continue}if(s=this.tokenizer.fences(t)){t=t.substring(s.raw.length),n.push(s);continue}if(s=this.tokenizer.heading(t)){t=t.substring(s.raw.length),n.push(s);continue}if(s=this.tokenizer.hr(t)){t=t.substring(s.raw.length),n.push(s);continue}if(s=this.tokenizer.blockquote(t)){t=t.substring(s.raw.length),n.push(s);continue}if(s=this.tokenizer.list(t)){t=t.substring(s.raw.length),n.push(s);continue}if(s=this.tokenizer.html(t)){t=t.substring(s.raw.length),n.push(s);continue}if(s=this.tokenizer.def(t)){t=t.substring(s.raw.length);let o=n.at(-1);o?.type==="paragraph"||o?.type==="text"?(o.raw+=(o.raw.endsWith(`
`)?"":`
`)+s.raw,o.text+=`
`+s.raw,this.inlineQueue.at(-1).src=o.text):this.tokens.links[s.tag]||(this.tokens.links[s.tag]={href:s.href,title:s.title},n.push(s));continue}if(s=this.tokenizer.table(t)){t=t.substring(s.raw.length),n.push(s);continue}if(s=this.tokenizer.lheading(t)){t=t.substring(s.raw.length),n.push(s);continue}let a=t;if(this.options.extensions?.startBlock){let o=1/0,r=t.slice(1),c;this.options.extensions.startBlock.forEach(u=>{c=u.call({lexer:this},r),typeof c=="number"&&c>=0&&(o=Math.min(o,c))}),o<1/0&&o>=0&&(a=t.substring(0,o+1))}if(this.state.top&&(s=this.tokenizer.paragraph(a))){let o=n.at(-1);i&&o?.type==="paragraph"?(o.raw+=(o.raw.endsWith(`
`)?"":`
`)+s.raw,o.text+=`
`+s.text,this.inlineQueue.pop(),this.inlineQueue.at(-1).src=o.text):n.push(s),i=a.length!==t.length,t=t.substring(s.raw.length);continue}if(s=this.tokenizer.text(t)){t=t.substring(s.raw.length);let o=n.at(-1);o?.type==="text"?(o.raw+=(o.raw.endsWith(`
`)?"":`
`)+s.raw,o.text+=`
`+s.text,this.inlineQueue.pop(),this.inlineQueue.at(-1).src=o.text):n.push(s);continue}if(t){let o="Infinite loop on byte: "+t.charCodeAt(0);if(this.options.silent){console.error(o);break}else throw new Error(o)}}return this.state.top=!0,n}inline(t,n=[]){return this.inlineQueue.push({src:t,tokens:n}),n}inlineTokens(t,n=[]){let i=t,s=null;if(this.tokens.links){let c=Object.keys(this.tokens.links);if(c.length>0)for(;(s=this.tokenizer.rules.inline.reflinkSearch.exec(i))!=null;)c.includes(s[0].slice(s[0].lastIndexOf("[")+1,-1))&&(i=i.slice(0,s.index)+"["+"a".repeat(s[0].length-2)+"]"+i.slice(this.tokenizer.rules.inline.reflinkSearch.lastIndex))}for(;(s=this.tokenizer.rules.inline.anyPunctuation.exec(i))!=null;)i=i.slice(0,s.index)+"++"+i.slice(this.tokenizer.rules.inline.anyPunctuation.lastIndex);let a;for(;(s=this.tokenizer.rules.inline.blockSkip.exec(i))!=null;)a=s[2]?s[2].length:0,i=i.slice(0,s.index+a)+"["+"a".repeat(s[0].length-a-2)+"]"+i.slice(this.tokenizer.rules.inline.blockSkip.lastIndex);i=this.options.hooks?.emStrongMask?.call({lexer:this},i)??i;let o=!1,r="";for(;t;){o||(r=""),o=!1;let c;if(this.options.extensions?.inline?.some(f=>(c=f.call({lexer:this},t,n))?(t=t.substring(c.raw.length),n.push(c),!0):!1))continue;if(c=this.tokenizer.escape(t)){t=t.substring(c.raw.length),n.push(c);continue}if(c=this.tokenizer.tag(t)){t=t.substring(c.raw.length),n.push(c);continue}if(c=this.tokenizer.link(t)){t=t.substring(c.raw.length),n.push(c);continue}if(c=this.tokenizer.reflink(t,this.tokens.links)){t=t.substring(c.raw.length);let f=n.at(-1);c.type==="text"&&f?.type==="text"?(f.raw+=c.raw,f.text+=c.text):n.push(c);continue}if(c=this.tokenizer.emStrong(t,i,r)){t=t.substring(c.raw.length),n.push(c);continue}if(c=this.tokenizer.codespan(t)){t=t.substring(c.raw.length),n.push(c);continue}if(c=this.tokenizer.br(t)){t=t.substring(c.raw.length),n.push(c);continue}if(c=this.tokenizer.del(t,i,r)){t=t.substring(c.raw.length),n.push(c);continue}if(c=this.tokenizer.autolink(t)){t=t.substring(c.raw.length),n.push(c);continue}if(!this.state.inLink&&(c=this.tokenizer.url(t))){t=t.substring(c.raw.length),n.push(c);continue}let u=t;if(this.options.extensions?.startInline){let f=1/0,p=t.slice(1),m;this.options.extensions.startInline.forEach(v=>{m=v.call({lexer:this},p),typeof m=="number"&&m>=0&&(f=Math.min(f,m))}),f<1/0&&f>=0&&(u=t.substring(0,f+1))}if(c=this.tokenizer.inlineText(u)){t=t.substring(c.raw.length),c.raw.slice(-1)!=="_"&&(r=c.raw.slice(-1)),o=!0;let f=n.at(-1);f?.type==="text"?(f.raw+=c.raw,f.text+=c.text):n.push(c);continue}if(t){let f="Infinite loop on byte: "+t.charCodeAt(0);if(this.options.silent){console.error(f);break}else throw new Error(f)}}return n}},Sn=class{options;parser;constructor(e){this.options=e||Xe}space(e){return""}code({text:e,lang:t,escaped:n}){let i=(t||"").match(ee.notSpaceStart)?.[0],s=e.replace(ee.endingNewline,"")+`
`;return i?'<pre><code class="language-'+Se(i)+'">'+(n?s:Se(s,!0))+`</code></pre>
`:"<pre><code>"+(n?s:Se(s,!0))+`</code></pre>
`}blockquote({tokens:e}){return`<blockquote>
${this.parser.parse(e)}</blockquote>
`}html({text:e}){return e}def(e){return""}heading({tokens:e,depth:t}){return`<h${t}>${this.parser.parseInline(e)}</h${t}>
`}hr(e){return`<hr>
`}list(e){let t=e.ordered,n=e.start,i="";for(let o=0;o<e.items.length;o++){let r=e.items[o];i+=this.listitem(r)}let s=t?"ol":"ul",a=t&&n!==1?' start="'+n+'"':"";return"<"+s+a+`>
`+i+"</"+s+`>
`}listitem(e){return`<li>${this.parser.parse(e.tokens)}</li>
`}checkbox({checked:e}){return"<input "+(e?'checked="" ':"")+'disabled="" type="checkbox"> '}paragraph({tokens:e}){return`<p>${this.parser.parseInline(e)}</p>
`}table(e){let t="",n="";for(let s=0;s<e.header.length;s++)n+=this.tablecell(e.header[s]);t+=this.tablerow({text:n});let i="";for(let s=0;s<e.rows.length;s++){let a=e.rows[s];n="";for(let o=0;o<a.length;o++)n+=this.tablecell(a[o]);i+=this.tablerow({text:n})}return i&&(i=`<tbody>${i}</tbody>`),`<table>
<thead>
`+t+`</thead>
`+i+`</table>
`}tablerow({text:e}){return`<tr>
${e}</tr>
`}tablecell(e){let t=this.parser.parseInline(e.tokens),n=e.header?"th":"td";return(e.align?`<${n} align="${e.align}">`:`<${n}>`)+t+`</${n}>
`}strong({tokens:e}){return`<strong>${this.parser.parseInline(e)}</strong>`}em({tokens:e}){return`<em>${this.parser.parseInline(e)}</em>`}codespan({text:e}){return`<code>${Se(e,!0)}</code>`}br(e){return"<br>"}del({tokens:e}){return`<del>${this.parser.parseInline(e)}</del>`}link({href:e,title:t,tokens:n}){let i=this.parser.parseInline(n),s=lo(e);if(s===null)return i;e=s;let a='<a href="'+e+'"';return t&&(a+=' title="'+Se(t)+'"'),a+=">"+i+"</a>",a}image({href:e,title:t,text:n,tokens:i}){i&&(n=this.parser.parseInline(i,this.parser.textRenderer));let s=lo(e);if(s===null)return Se(n);e=s;let a=`<img src="${e}" alt="${n}"`;return t&&(a+=` title="${Se(t)}"`),a+=">",a}text(e){return"tokens"in e&&e.tokens?this.parser.parseInline(e.tokens):"escaped"in e&&e.escaped?e.text:Se(e.text)}},Ms=class{strong({text:e}){return e}em({text:e}){return e}codespan({text:e}){return e}del({text:e}){return e}html({text:e}){return e}text({text:e}){return e}link({text:e}){return""+e}image({text:e}){return""+e}br(){return""}checkbox({raw:e}){return e}},pe=class Wi{options;renderer;textRenderer;constructor(t){this.options=t||Xe,this.options.renderer=this.options.renderer||new Sn,this.renderer=this.options.renderer,this.renderer.options=this.options,this.renderer.parser=this,this.textRenderer=new Ms}static parse(t,n){return new Wi(n).parse(t)}static parseInline(t,n){return new Wi(n).parseInline(t)}parse(t){let n="";for(let i=0;i<t.length;i++){let s=t[i];if(this.options.extensions?.renderers?.[s.type]){let o=s,r=this.options.extensions.renderers[o.type].call({parser:this},o);if(r!==!1||!["space","hr","heading","code","table","blockquote","list","html","def","paragraph","text"].includes(o.type)){n+=r||"";continue}}let a=s;switch(a.type){case"space":{n+=this.renderer.space(a);break}case"hr":{n+=this.renderer.hr(a);break}case"heading":{n+=this.renderer.heading(a);break}case"code":{n+=this.renderer.code(a);break}case"table":{n+=this.renderer.table(a);break}case"blockquote":{n+=this.renderer.blockquote(a);break}case"list":{n+=this.renderer.list(a);break}case"checkbox":{n+=this.renderer.checkbox(a);break}case"html":{n+=this.renderer.html(a);break}case"def":{n+=this.renderer.def(a);break}case"paragraph":{n+=this.renderer.paragraph(a);break}case"text":{n+=this.renderer.text(a);break}default:{let o='Token with "'+a.type+'" type was not found.';if(this.options.silent)return console.error(o),"";throw new Error(o)}}}return n}parseInline(t,n=this.renderer){let i="";for(let s=0;s<t.length;s++){let a=t[s];if(this.options.extensions?.renderers?.[a.type]){let r=this.options.extensions.renderers[a.type].call({parser:this},a);if(r!==!1||!["escape","html","link","image","strong","em","codespan","br","del","text"].includes(a.type)){i+=r||"";continue}}let o=a;switch(o.type){case"escape":{i+=n.text(o);break}case"html":{i+=n.html(o);break}case"link":{i+=n.link(o);break}case"image":{i+=n.image(o);break}case"checkbox":{i+=n.checkbox(o);break}case"strong":{i+=n.strong(o);break}case"em":{i+=n.em(o);break}case"codespan":{i+=n.codespan(o);break}case"br":{i+=n.br(o);break}case"del":{i+=n.del(o);break}case"text":{i+=n.text(o);break}default:{let r='Token with "'+o.type+'" type was not found.';if(this.options.silent)return console.error(r),"";throw new Error(r)}}}return i}},Ct=class{options;block;constructor(e){this.options=e||Xe}static passThroughHooks=new Set(["preprocess","postprocess","processAllTokens","emStrongMask"]);static passThroughHooksRespectAsync=new Set(["preprocess","postprocess","processAllTokens"]);preprocess(e){return e}postprocess(e){return e}processAllTokens(e){return e}emStrongMask(e){return e}provideLexer(){return this.block?fe.lex:fe.lexInline}provideParser(){return this.block?pe.parse:pe.parseInline}},Kg=class{defaults=Ss();options=this.setOptions;parse=this.parseMarkdown(!0);parseInline=this.parseMarkdown(!1);Parser=pe;Renderer=Sn;TextRenderer=Ms;Lexer=fe;Tokenizer=xn;Hooks=Ct;constructor(...e){this.use(...e)}walkTokens(e,t){let n=[];for(let i of e)switch(n=n.concat(t.call(this,i)),i.type){case"table":{let s=i;for(let a of s.header)n=n.concat(this.walkTokens(a.tokens,t));for(let a of s.rows)for(let o of a)n=n.concat(this.walkTokens(o.tokens,t));break}case"list":{let s=i;n=n.concat(this.walkTokens(s.items,t));break}default:{let s=i;this.defaults.extensions?.childTokens?.[s.type]?this.defaults.extensions.childTokens[s.type].forEach(a=>{let o=s[a].flat(1/0);n=n.concat(this.walkTokens(o,t))}):s.tokens&&(n=n.concat(this.walkTokens(s.tokens,t)))}}return n}use(...e){let t=this.defaults.extensions||{renderers:{},childTokens:{}};return e.forEach(n=>{let i={...n};if(i.async=this.defaults.async||i.async||!1,n.extensions&&(n.extensions.forEach(s=>{if(!s.name)throw new Error("extension name required");if("renderer"in s){let a=t.renderers[s.name];a?t.renderers[s.name]=function(...o){let r=s.renderer.apply(this,o);return r===!1&&(r=a.apply(this,o)),r}:t.renderers[s.name]=s.renderer}if("tokenizer"in s){if(!s.level||s.level!=="block"&&s.level!=="inline")throw new Error("extension level must be 'block' or 'inline'");let a=t[s.level];a?a.unshift(s.tokenizer):t[s.level]=[s.tokenizer],s.start&&(s.level==="block"?t.startBlock?t.startBlock.push(s.start):t.startBlock=[s.start]:s.level==="inline"&&(t.startInline?t.startInline.push(s.start):t.startInline=[s.start]))}"childTokens"in s&&s.childTokens&&(t.childTokens[s.name]=s.childTokens)}),i.extensions=t),n.renderer){let s=this.defaults.renderer||new Sn(this.defaults);for(let a in n.renderer){if(!(a in s))throw new Error(`renderer '${a}' does not exist`);if(["options","parser"].includes(a))continue;let o=a,r=n.renderer[o],c=s[o];s[o]=(...u)=>{let f=r.apply(s,u);return f===!1&&(f=c.apply(s,u)),f||""}}i.renderer=s}if(n.tokenizer){let s=this.defaults.tokenizer||new xn(this.defaults);for(let a in n.tokenizer){if(!(a in s))throw new Error(`tokenizer '${a}' does not exist`);if(["options","rules","lexer"].includes(a))continue;let o=a,r=n.tokenizer[o],c=s[o];s[o]=(...u)=>{let f=r.apply(s,u);return f===!1&&(f=c.apply(s,u)),f}}i.tokenizer=s}if(n.hooks){let s=this.defaults.hooks||new Ct;for(let a in n.hooks){if(!(a in s))throw new Error(`hook '${a}' does not exist`);if(["options","block"].includes(a))continue;let o=a,r=n.hooks[o],c=s[o];Ct.passThroughHooks.has(a)?s[o]=u=>{if(this.defaults.async&&Ct.passThroughHooksRespectAsync.has(a))return(async()=>{let p=await r.call(s,u);return c.call(s,p)})();let f=r.call(s,u);return c.call(s,f)}:s[o]=(...u)=>{if(this.defaults.async)return(async()=>{let p=await r.apply(s,u);return p===!1&&(p=await c.apply(s,u)),p})();let f=r.apply(s,u);return f===!1&&(f=c.apply(s,u)),f}}i.hooks=s}if(n.walkTokens){let s=this.defaults.walkTokens,a=n.walkTokens;i.walkTokens=function(o){let r=[];return r.push(a.call(this,o)),s&&(r=r.concat(s.call(this,o))),r}}this.defaults={...this.defaults,...i}}),this}setOptions(e){return this.defaults={...this.defaults,...e},this}lexer(e,t){return fe.lex(e,t??this.defaults)}parser(e,t){return pe.parse(e,t??this.defaults)}parseMarkdown(e){return(t,n)=>{let i={...n},s={...this.defaults,...i},a=this.onError(!!s.silent,!!s.async);if(this.defaults.async===!0&&i.async===!1)return a(new Error("marked(): The async option was set to true by an extension. Remove async: false from the parse options object to return a Promise."));if(typeof t>"u"||t===null)return a(new Error("marked(): input parameter is undefined or null"));if(typeof t!="string")return a(new Error("marked(): input parameter is of type "+Object.prototype.toString.call(t)+", string expected"));if(s.hooks&&(s.hooks.options=s,s.hooks.block=e),s.async)return(async()=>{let o=s.hooks?await s.hooks.preprocess(t):t,r=await(s.hooks?await s.hooks.provideLexer():e?fe.lex:fe.lexInline)(o,s),c=s.hooks?await s.hooks.processAllTokens(r):r;s.walkTokens&&await Promise.all(this.walkTokens(c,s.walkTokens));let u=await(s.hooks?await s.hooks.provideParser():e?pe.parse:pe.parseInline)(c,s);return s.hooks?await s.hooks.postprocess(u):u})().catch(a);try{s.hooks&&(t=s.hooks.preprocess(t));let o=(s.hooks?s.hooks.provideLexer():e?fe.lex:fe.lexInline)(t,s);s.hooks&&(o=s.hooks.processAllTokens(o)),s.walkTokens&&this.walkTokens(o,s.walkTokens);let r=(s.hooks?s.hooks.provideParser():e?pe.parse:pe.parseInline)(o,s);return s.hooks&&(r=s.hooks.postprocess(r)),r}catch(o){return a(o)}}}onError(e,t){return n=>{if(n.message+=`
Please report this to https://github.com/markedjs/marked.`,e){let i="<p>An error occurred:</p><pre>"+Se(n.message+"",!0)+"</pre>";return t?Promise.resolve(i):i}if(t)return Promise.reject(n);throw n}}},Je=new Kg;function N(e,t){return Je.parse(e,t)}N.options=N.setOptions=function(e){return Je.setOptions(e),N.defaults=Je.defaults,Wl(N.defaults),N};N.getDefaults=Ss;N.defaults=Xe;N.use=function(...e){return Je.use(...e),N.defaults=Je.defaults,Wl(N.defaults),N};N.walkTokens=function(e,t){return Je.walkTokens(e,t)};N.parseInline=Je.parseInline;N.Parser=pe;N.parser=pe.parse;N.Renderer=Sn;N.TextRenderer=Ms;N.Lexer=fe;N.lexer=fe.lex;N.Tokenizer=xn;N.Hooks=Ct;N.parse=N;N.options;N.setOptions;N.use;N.walkTokens;N.parseInline;pe.parse;fe.lex;N.setOptions({gfm:!0,breaks:!0});const uo=["a","b","blockquote","br","code","del","em","h1","h2","h3","h4","hr","i","li","ol","p","pre","strong","table","tbody","td","th","thead","tr","ul"],fo=["class","href","rel","target","title","start"];let po=!1;const zg=14e4,Hg=4e4,jg=200,ki=5e4,qe=new Map;function Gg(e){const t=qe.get(e);return t===void 0?null:(qe.delete(e),qe.set(e,t),t)}function go(e,t){if(qe.set(e,t),qe.size<=jg)return;const n=qe.keys().next().value;n&&qe.delete(n)}function qg(){po||(po=!0,ji.addHook("afterSanitizeAttributes",e=>{!(e instanceof HTMLAnchorElement)||!e.getAttribute("href")||(e.setAttribute("rel","noreferrer noopener"),e.setAttribute("target","_blank"))}))}function Vi(e){const t=e.trim();if(!t)return"";if(qg(),t.length<=ki){const o=Gg(t);if(o!==null)return o}const n=Go(t,zg),i=n.truncated?`

… truncated (${n.total} chars, showing first ${n.text.length}).`:"";if(n.text.length>Hg){const r=`<pre class="code-block">${Wg(`${n.text}${i}`)}</pre>`,c=ji.sanitize(r,{ALLOWED_TAGS:uo,ALLOWED_ATTR:fo});return t.length<=ki&&go(t,c),c}const s=N.parse(`${n.text}${i}`),a=ji.sanitize(s,{ALLOWED_TAGS:uo,ALLOWED_ATTR:fo});return t.length<=ki&&go(t,a),a}function Wg(e){return e.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;")}const Vg=1500,Yg=2e3,ar="Copy as markdown",Qg="Copied",Jg="Copy failed";async function Zg(e){if(!e)return!1;try{return await navigator.clipboard.writeText(e),!0}catch{return!1}}function cn(e,t){e.title=t,e.setAttribute("aria-label",t)}function Xg(e){const t=e.label??ar;return l`
    <button
      class="chat-copy-btn"
      type="button"
      title=${t}
      aria-label=${t}
      @click=${async n=>{const i=n.currentTarget;if(!i||i.dataset.copying==="1")return;i.dataset.copying="1",i.setAttribute("aria-busy","true"),i.disabled=!0;const s=await Zg(e.text());if(i.isConnected){if(delete i.dataset.copying,i.removeAttribute("aria-busy"),i.disabled=!1,!s){i.dataset.error="1",cn(i,Jg),window.setTimeout(()=>{i.isConnected&&(delete i.dataset.error,cn(i,t))},Yg);return}i.dataset.copied="1",cn(i,Qg),window.setTimeout(()=>{i.isConnected&&(delete i.dataset.copied,cn(i,t))},Vg)}}}
    >
      <span class="chat-copy-btn__icon" aria-hidden="true">
        <span class="chat-copy-btn__icon-copy">${Y.copy}</span>
        <span class="chat-copy-btn__icon-check">${Y.check}</span>
      </span>
    </button>
  `}function eh(e){return Xg({text:()=>e,label:ar})}function or(e){const t=e;let n=typeof t.role=="string"?t.role:"unknown";const i=typeof t.toolCallId=="string"||typeof t.tool_call_id=="string",s=t.content,a=Array.isArray(s)?s:null,o=Array.isArray(a)&&a.some(p=>{const m=p,v=(typeof m.type=="string"?m.type:"").toLowerCase();return v==="toolresult"||v==="tool_result"}),r=typeof t.toolName=="string"||typeof t.tool_name=="string";(i||o||r)&&(n="toolResult");let c=[];typeof t.content=="string"?c=[{type:"text",text:t.content}]:Array.isArray(t.content)?c=t.content.map(p=>({type:p.type||"text",text:p.text,name:p.name,args:p.args||p.arguments})):typeof t.text=="string"&&(c=[{type:"text",text:t.text}]);const u=typeof t.timestamp=="number"?t.timestamp:Date.now(),f=typeof t.id=="string"?t.id:void 0;return{role:n,content:c,timestamp:u,id:f}}function Ps(e){const t=e.toLowerCase();return e==="user"||e==="User"?e:e==="assistant"?"assistant":e==="system"?"system":t==="toolresult"||t==="tool_result"||t==="tool"||t==="function"?"tool":e}function lr(e){const t=e,n=typeof t.role=="string"?t.role.toLowerCase():"";return n==="toolresult"||n==="tool_result"}const th={icon:"puzzle",detailKeys:["command","path","url","targetUrl","targetId","ref","element","node","nodeId","id","requestId","to","channelId","guildId","userId","name","query","pattern","messageId"]},nh={bash:{icon:"wrench",title:"Bash",detailKeys:["command"]},process:{icon:"wrench",title:"Process",detailKeys:["sessionId"]},read:{icon:"fileText",title:"Read",detailKeys:["path"]},write:{icon:"edit",title:"Write",detailKeys:["path"]},edit:{icon:"penLine",title:"Edit",detailKeys:["path"]},attach:{icon:"paperclip",title:"Attach",detailKeys:["path","url","fileName"]},browser:{icon:"globe",title:"Browser",actions:{status:{label:"status"},start:{label:"start"},stop:{label:"stop"},tabs:{label:"tabs"},open:{label:"open",detailKeys:["targetUrl"]},focus:{label:"focus",detailKeys:["targetId"]},close:{label:"close",detailKeys:["targetId"]},snapshot:{label:"snapshot",detailKeys:["targetUrl","targetId","ref","element","format"]},screenshot:{label:"screenshot",detailKeys:["targetUrl","targetId","ref","element"]},navigate:{label:"navigate",detailKeys:["targetUrl","targetId"]},console:{label:"console",detailKeys:["level","targetId"]},pdf:{label:"pdf",detailKeys:["targetId"]},upload:{label:"upload",detailKeys:["paths","ref","inputRef","element","targetId"]},dialog:{label:"dialog",detailKeys:["accept","promptText","targetId"]},act:{label:"act",detailKeys:["request.kind","request.ref","request.selector","request.text","request.value"]}}},canvas:{icon:"image",title:"Canvas",actions:{present:{label:"present",detailKeys:["target","node","nodeId"]},hide:{label:"hide",detailKeys:["node","nodeId"]},navigate:{label:"navigate",detailKeys:["url","node","nodeId"]},eval:{label:"eval",detailKeys:["javaScript","node","nodeId"]},snapshot:{label:"snapshot",detailKeys:["format","node","nodeId"]},a2ui_push:{label:"A2UI push",detailKeys:["jsonlPath","node","nodeId"]},a2ui_reset:{label:"A2UI reset",detailKeys:["node","nodeId"]}}},nodes:{icon:"smartphone",title:"Nodes",actions:{status:{label:"status"},describe:{label:"describe",detailKeys:["node","nodeId"]},pending:{label:"pending"},approve:{label:"approve",detailKeys:["requestId"]},reject:{label:"reject",detailKeys:["requestId"]},notify:{label:"notify",detailKeys:["node","nodeId","title","body"]},camera_snap:{label:"camera snap",detailKeys:["node","nodeId","facing","deviceId"]},camera_list:{label:"camera list",detailKeys:["node","nodeId"]},camera_clip:{label:"camera clip",detailKeys:["node","nodeId","facing","duration","durationMs"]},screen_record:{label:"screen record",detailKeys:["node","nodeId","duration","durationMs","fps","screenIndex"]}}},cron:{icon:"loader",title:"Cron",actions:{status:{label:"status"},list:{label:"list"},add:{label:"add",detailKeys:["job.name","job.id","job.schedule","job.cron"]},update:{label:"update",detailKeys:["id"]},remove:{label:"remove",detailKeys:["id"]},run:{label:"run",detailKeys:["id"]},runs:{label:"runs",detailKeys:["id"]},wake:{label:"wake",detailKeys:["text","mode"]}}},gateway:{icon:"plug",title:"Gateway",actions:{restart:{label:"restart",detailKeys:["reason","delayMs"]},"config.get":{label:"config get"},"config.schema":{label:"config schema"},"config.apply":{label:"config apply",detailKeys:["restartDelayMs"]},"update.run":{label:"update run",detailKeys:["restartDelayMs"]}}},whatsapp_login:{icon:"circle",title:"WhatsApp Login",actions:{start:{label:"start"},wait:{label:"wait"}}},discord:{icon:"messageSquare",title:"Discord",actions:{react:{label:"react",detailKeys:["channelId","messageId","emoji"]},reactions:{label:"reactions",detailKeys:["channelId","messageId"]},sticker:{label:"sticker",detailKeys:["to","stickerIds"]},poll:{label:"poll",detailKeys:["question","to"]},permissions:{label:"permissions",detailKeys:["channelId"]},readMessages:{label:"read messages",detailKeys:["channelId","limit"]},sendMessage:{label:"send",detailKeys:["to","content"]},editMessage:{label:"edit",detailKeys:["channelId","messageId"]},deleteMessage:{label:"delete",detailKeys:["channelId","messageId"]},threadCreate:{label:"thread create",detailKeys:["channelId","name"]},threadList:{label:"thread list",detailKeys:["guildId","channelId"]},threadReply:{label:"thread reply",detailKeys:["channelId","content"]},pinMessage:{label:"pin",detailKeys:["channelId","messageId"]},unpinMessage:{label:"unpin",detailKeys:["channelId","messageId"]},listPins:{label:"list pins",detailKeys:["channelId"]},searchMessages:{label:"search",detailKeys:["guildId","content"]},memberInfo:{label:"member",detailKeys:["guildId","userId"]},roleInfo:{label:"roles",detailKeys:["guildId"]},emojiList:{label:"emoji list",detailKeys:["guildId"]},roleAdd:{label:"role add",detailKeys:["guildId","userId","roleId"]},roleRemove:{label:"role remove",detailKeys:["guildId","userId","roleId"]},channelInfo:{label:"channel",detailKeys:["channelId"]},channelList:{label:"channels",detailKeys:["guildId"]},voiceStatus:{label:"voice",detailKeys:["guildId","userId"]},eventList:{label:"events",detailKeys:["guildId"]},eventCreate:{label:"event create",detailKeys:["guildId","name"]},timeout:{label:"timeout",detailKeys:["guildId","userId"]},kick:{label:"kick",detailKeys:["guildId","userId"]},ban:{label:"ban",detailKeys:["guildId","userId"]}}},slack:{icon:"messageSquare",title:"Slack",actions:{react:{label:"react",detailKeys:["channelId","messageId","emoji"]},reactions:{label:"reactions",detailKeys:["channelId","messageId"]},sendMessage:{label:"send",detailKeys:["to","content"]},editMessage:{label:"edit",detailKeys:["channelId","messageId"]},deleteMessage:{label:"delete",detailKeys:["channelId","messageId"]},readMessages:{label:"read messages",detailKeys:["channelId","limit"]},pinMessage:{label:"pin",detailKeys:["channelId","messageId"]},unpinMessage:{label:"unpin",detailKeys:["channelId","messageId"]},listPins:{label:"list pins",detailKeys:["channelId"]},memberInfo:{label:"member",detailKeys:["userId"]},emojiList:{label:"emoji list"}}}},ih={fallback:th,tools:nh},rr=ih,ho=rr.fallback??{icon:"puzzle"},sh=rr.tools??{};function ah(e){return(e??"tool").trim()}function oh(e){const t=e.replace(/_/g," ").trim();return t?t.split(/\s+/).map(n=>n.length<=2&&n.toUpperCase()===n?n:`${n.at(0)?.toUpperCase()??""}${n.slice(1)}`).join(" "):"Tool"}function lh(e){const t=e?.trim();if(t)return t.replace(/_/g," ")}function cr(e){if(e!=null){if(typeof e=="string"){const t=e.trim();if(!t)return;const n=t.split(/\r?\n/)[0]?.trim()??"";return n?n.length>160?`${n.slice(0,157)}…`:n:void 0}if(typeof e=="number"||typeof e=="boolean")return String(e);if(Array.isArray(e)){const t=e.map(i=>cr(i)).filter(i=>!!i);if(t.length===0)return;const n=t.slice(0,3).join(", ");return t.length>3?`${n}…`:n}}}function rh(e,t){if(!e||typeof e!="object")return;let n=e;for(const i of t.split(".")){if(!i||!n||typeof n!="object")return;n=n[i]}return n}function ch(e,t){for(const n of t){const i=rh(e,n),s=cr(i);if(s)return s}}function dh(e){if(!e||typeof e!="object")return;const t=e,n=typeof t.path=="string"?t.path:void 0;if(!n)return;const i=typeof t.offset=="number"?t.offset:void 0,s=typeof t.limit=="number"?t.limit:void 0;return i!==void 0&&s!==void 0?`${n}:${i}-${i+s}`:n}function uh(e){if(!e||typeof e!="object")return;const t=e;return typeof t.path=="string"?t.path:void 0}function fh(e,t){if(!(!e||!t))return e.actions?.[t]??void 0}function ph(e){const t=ah(e.name),n=t.toLowerCase(),i=sh[n],s=i?.icon??ho.icon??"puzzle",a=i?.title??oh(t),o=i?.label??t,r=e.args&&typeof e.args=="object"?e.args.action:void 0,c=typeof r=="string"?r.trim():void 0,u=fh(i,c),f=lh(u?.label??c);let p;n==="read"&&(p=dh(e.args)),!p&&(n==="write"||n==="edit"||n==="attach")&&(p=uh(e.args));const m=u?.detailKeys??i?.detailKeys??ho.detailKeys??[];return!p&&m.length>0&&(p=ch(e.args,m)),!p&&e.meta&&(p=e.meta),p&&(p=hh(p)),{name:t,icon:s,title:a,label:o,verb:f,detail:p}}function gh(e){const t=[];if(e.verb&&t.push(e.verb),e.detail&&t.push(e.detail),t.length!==0)return t.join(" · ")}function hh(e){return e&&e.replace(/\/Users\/[^/]+/g,"~").replace(/\/home\/[^/]+/g,"~")}const vh=80,mh=2,vo=100;function yh(e){const t=e.trim();if(t.startsWith("{")||t.startsWith("["))try{const n=JSON.parse(t);return"```json\n"+JSON.stringify(n,null,2)+"\n```"}catch{}return e}function bh(e){const t=e.split(`
`),n=t.slice(0,mh),i=n.join(`
`);return i.length>vo?i.slice(0,vo)+"…":n.length<t.length?i+"…":i}function $h(e){const t=e,n=wh(t.content),i=[];for(const s of n){const a=(typeof s.type=="string"?s.type:"").toLowerCase();(["toolcall","tool_call","tooluse","tool_use"].includes(a)||typeof s.name=="string"&&s.arguments!=null)&&i.push({kind:"call",name:s.name??"tool",args:kh(s.arguments??s.args)})}for(const s of n){const a=(typeof s.type=="string"?s.type:"").toLowerCase();if(a!=="toolresult"&&a!=="tool_result")continue;const o=Ah(s),r=typeof s.name=="string"?s.name:"tool";i.push({kind:"result",name:r,text:o})}if(lr(e)&&!i.some(s=>s.kind==="result")){const s=typeof t.toolName=="string"&&t.toolName||typeof t.tool_name=="string"&&t.tool_name||"tool",a=bl(e)??void 0;i.push({kind:"result",name:s,text:a})}return i}function mo(e,t){const n=ph({name:e.name,args:e.args}),i=gh(n),s=!!e.text?.trim(),a=!!t,o=a?()=>{if(s){t(yh(e.text));return}const p=`## ${n.label}

${i?`**Command:** \`${i}\`

`:""}*No output — tool completed successfully.*`;t(p)}:void 0,r=s&&(e.text?.length??0)<=vh,c=s&&!r,u=s&&r,f=!s;return l`
    <div
      class="chat-tool-card ${a?"chat-tool-card--clickable":""}"
      @click=${o}
      role=${a?"button":g}
      tabindex=${a?"0":g}
      @keydown=${a?p=>{p.key!=="Enter"&&p.key!==" "||(p.preventDefault(),o?.())}:g}
    >
      <div class="chat-tool-card__header">
        <div class="chat-tool-card__title">
          <span class="chat-tool-card__icon">${Y[n.icon]}</span>
          <span>${n.label}</span>
        </div>
        ${a?l`<span class="chat-tool-card__action">${s?"View":""} ${Y.check}</span>`:g}
        ${f&&!a?l`<span class="chat-tool-card__status">${Y.check}</span>`:g}
      </div>
      ${i?l`<div class="chat-tool-card__detail">${i}</div>`:g}
      ${f?l`
              <div class="chat-tool-card__status-text muted">Completed</div>
            `:g}
      ${c?l`<div class="chat-tool-card__preview mono">${bh(e.text)}</div>`:g}
      ${u?l`<div class="chat-tool-card__inline mono">${e.text}</div>`:g}
    </div>
  `}function wh(e){return Array.isArray(e)?e.filter(Boolean):[]}function kh(e){if(typeof e!="string")return e;const t=e.trim();if(!t||!t.startsWith("{")&&!t.startsWith("["))return e;try{return JSON.parse(t)}catch{return e}}function Ah(e){if(typeof e.text=="string")return e.text;if(typeof e.content=="string")return e.content}function xh(e){const n=e.content,i=[];if(Array.isArray(n))for(const s of n){if(typeof s!="object"||s===null)continue;const a=s;if(a.type==="image"){const o=a.source;if(o?.type==="base64"&&typeof o.data=="string"){const r=o.data,c=o.media_type||"image/png",u=r.startsWith("data:")?r:`data:${c};base64,${r}`;i.push({url:u})}else typeof a.url=="string"&&i.push({url:a.url})}else if(a.type==="image_url"){const o=a.image_url;typeof o?.url=="string"&&i.push({url:o.url})}}return i}function Sh(e){return l`
    <div class="chat-group assistant">
      ${Fs("assistant",e)}
      <div class="chat-group-messages">
        <div class="chat-bubble chat-reading-indicator" aria-hidden="true">
          <span class="chat-reading-indicator__dots">
            <span></span><span></span><span></span>
          </span>
        </div>
      </div>
    </div>
  `}function _h(e,t,n,i){const s=new Date(t).toLocaleTimeString([],{hour:"numeric",minute:"2-digit"}),a=i?.name??"Assistant";return l`
    <div class="chat-group assistant">
      ${Fs("assistant",i)}
      <div class="chat-group-messages">
        ${dr({role:"assistant",content:[{type:"text",text:e}],timestamp:t},{isStreaming:!0,showReasoning:!1},n)}
        <div class="chat-group-footer">
          <span class="chat-sender-name">${a}</span>
          <span class="chat-group-timestamp">${s}</span>
        </div>
      </div>
    </div>
  `}function Ch(e,t){const n=Ps(e.role),i=t.assistantName??"Assistant",s=n==="user"?"You":n==="assistant"?i:n,a=n==="user"?"user":n==="assistant"?"assistant":"other",o=new Date(e.timestamp).toLocaleTimeString([],{hour:"numeric",minute:"2-digit"});return l`
    <div class="chat-group ${a}">
      ${Fs(e.role,{name:i,avatar:t.assistantAvatar??null})}
      <div class="chat-group-messages">
        ${e.messages.map((r,c)=>dr(r.message,{isStreaming:e.isStreaming&&c===e.messages.length-1,showReasoning:t.showReasoning},t.onOpenSidebar))}
        <div class="chat-group-footer">
          <span class="chat-sender-name">${s}</span>
          <span class="chat-group-timestamp">${o}</span>
        </div>
      </div>
    </div>
  `}function Fs(e,t){const n=Ps(e),i=t?.name?.trim()||"Assistant",s=t?.avatar?.trim()||"",a=n==="user"?"U":n==="assistant"?i.charAt(0).toUpperCase()||"A":n==="tool"?"⚙":"?",o=n==="user"?"user":n==="assistant"?"assistant":n==="tool"?"tool":"other";return s&&n==="assistant"?Eh(s)?l`<img
        class="chat-avatar ${o}"
        src="${s}"
        alt="${i}"
      />`:l`<div class="chat-avatar ${o}">${s}</div>`:l`<div class="chat-avatar ${o}">${a}</div>`}function Eh(e){return/^https?:\/\//i.test(e)||/^data:image\//i.test(e)||e.startsWith("/")}function Th(e){return e.length===0?g:l`
    <div class="chat-message-images">
      ${e.map(t=>l`
          <img
            src=${t.url}
            alt=${t.alt??"Attached image"}
            class="chat-message-image"
            @click=${()=>window.open(t.url,"_blank")}
          />
        `)}
    </div>
  `}function dr(e,t,n){const i=e,s=typeof i.role=="string"?i.role:"unknown",a=lr(e)||s.toLowerCase()==="toolresult"||s.toLowerCase()==="tool_result"||typeof i.toolCallId=="string"||typeof i.tool_call_id=="string",o=$h(e),r=o.length>0,c=xh(e),u=c.length>0,f=bl(e),p=t.showReasoning&&s==="assistant"?ou(e):null,m=f?.trim()?f:null,v=p?ru(p):null,b=m,d=s==="assistant"&&!!b?.trim(),y=["chat-bubble",d?"has-copy":"",t.isStreaming?"streaming":"","fade-in"].filter(Boolean).join(" ");return!b&&r&&a?l`${o.map(A=>mo(A,n))}`:!b&&!r&&!u?g:l`
    <div class="${y}">
      ${d?eh(b):g}
      ${Th(c)}
      ${v?l`<div class="chat-thinking">${Ui(Vi(v))}</div>`:g}
      ${b?l`<div class="chat-text">${Ui(Vi(b))}</div>`:g}
      ${o.map(A=>mo(A,n))}
    </div>
  `}function Lh(e){return l`
    <div class="sidebar-panel">
      <div class="sidebar-header">
        <div class="sidebar-title">Tool Output</div>
        <button @click=${e.onClose} class="btn" title="Close sidebar">
          ${Y.x}
        </button>
      </div>
      <div class="sidebar-content">
        ${e.error?l`
              <div class="callout danger">${e.error}</div>
              <button @click=${e.onViewRawText} class="btn" style="margin-top: 12px;">
                View Raw Text
              </button>
            `:e.content?l`<div class="sidebar-markdown">${Ui(Vi(e.content))}</div>`:l`
                  <div class="muted">No content available</div>
                `}
      </div>
    </div>
  `}var Ih=Object.defineProperty,Rh=Object.getOwnPropertyDescriptor,zn=(e,t,n,i)=>{for(var s=i>1?void 0:i?Rh(t,n):t,a=e.length-1,o;a>=0;a--)(o=e[a])&&(s=(i?o(t,n,s):o(s))||s);return i&&s&&Ih(t,n,s),s};let pt=class extends ct{constructor(){super(...arguments),this.splitRatio=.6,this.minRatio=.4,this.maxRatio=.7,this.isDragging=!1,this.startX=0,this.startRatio=0,this.handleMouseDown=e=>{this.isDragging=!0,this.startX=e.clientX,this.startRatio=this.splitRatio,this.classList.add("dragging"),document.addEventListener("mousemove",this.handleMouseMove),document.addEventListener("mouseup",this.handleMouseUp),e.preventDefault()},this.handleMouseMove=e=>{if(!this.isDragging)return;const t=this.parentElement;if(!t)return;const n=t.getBoundingClientRect().width,s=(e.clientX-this.startX)/n;let a=this.startRatio+s;a=Math.max(this.minRatio,Math.min(this.maxRatio,a)),this.dispatchEvent(new CustomEvent("resize",{detail:{splitRatio:a},bubbles:!0,composed:!0}))},this.handleMouseUp=()=>{this.isDragging=!1,this.classList.remove("dragging"),document.removeEventListener("mousemove",this.handleMouseMove),document.removeEventListener("mouseup",this.handleMouseUp)}}render(){return g}connectedCallback(){super.connectedCallback(),this.addEventListener("mousedown",this.handleMouseDown)}disconnectedCallback(){super.disconnectedCallback(),this.removeEventListener("mousedown",this.handleMouseDown),document.removeEventListener("mousemove",this.handleMouseMove),document.removeEventListener("mouseup",this.handleMouseUp)}};pt.styles=kr`
    :host {
      width: 4px;
      cursor: col-resize;
      background: var(--border, #333);
      transition: background 150ms ease-out;
      flex-shrink: 0;
      position: relative;
    }
    :host::before {
      content: "";
      position: absolute;
      top: 0;
      left: -4px;
      right: -4px;
      bottom: 0;
    }
    :host(:hover) {
      background: var(--accent, #007bff);
    }
    :host(.dragging) {
      background: var(--accent, #007bff);
    }
  `;zn([Tn({type:Number})],pt.prototype,"splitRatio",2);zn([Tn({type:Number})],pt.prototype,"minRatio",2);zn([Tn({type:Number})],pt.prototype,"maxRatio",2);pt=zn([Po("resizable-divider")],pt);const Mh=5e3;function yo(e){e.style.height="auto",e.style.height=`${e.scrollHeight}px`}function Ph(e){return e?e.active?l`
      <div class="callout info compaction-indicator compaction-indicator--active">
        ${Y.loader} Compacting context...
      </div>
    `:e.completedAt&&Date.now()-e.completedAt<Mh?l`
        <div class="callout success compaction-indicator compaction-indicator--complete">
          ${Y.check} Context compacted
        </div>
      `:g:g}function Fh(){return`att-${Date.now()}-${Math.random().toString(36).slice(2,9)}`}function Nh(e,t){const n=e.clipboardData?.items;if(!n||!t.onAttachmentsChange)return;const i=[];for(let s=0;s<n.length;s++){const a=n[s];a.type.startsWith("image/")&&i.push(a)}if(i.length!==0){e.preventDefault();for(const s of i){const a=s.getAsFile();if(!a)continue;const o=new FileReader;o.addEventListener("load",()=>{const r=o.result,c={id:Fh(),dataUrl:r,mimeType:a.type},u=t.attachments??[];t.onAttachmentsChange?.([...u,c])}),o.readAsDataURL(a)}}}function Dh(e){const t=e.attachments??[];return t.length===0?g:l`
    <div class="chat-attachments">
      ${t.map(n=>l`
          <div class="chat-attachment">
            <img
              src=${n.dataUrl}
              alt="Attachment preview"
              class="chat-attachment__img"
            />
            <button
              class="chat-attachment__remove"
              type="button"
              aria-label="Remove attachment"
              @click=${()=>{const i=(e.attachments??[]).filter(s=>s.id!==n.id);e.onAttachmentsChange?.(i)}}
            >
              ${Y.x}
            </button>
          </div>
        `)}
    </div>
  `}function Oh(e){const t=e.connected,n=e.sending||e.stream!==null,i=!!(e.canAbort&&e.onAbort),a=e.sessions?.sessions?.find(v=>v.key===e.sessionKey)?.reasoningLevel??"off",o=e.showThinking&&a!=="off",r={name:e.assistantName,avatar:e.assistantAvatar??e.assistantAvatarUrl??null},c=(e.attachments?.length??0)>0,u=e.connected?c?"Add a message or paste more images...":"Message (↩ to send, Shift+↩ for line breaks, paste images)":"Connect to the gateway to start chatting…",f=e.splitRatio??.6,p=!!(e.sidebarOpen&&e.onCloseSidebar),m=l`
    <div
      class="chat-thread"
      role="log"
      aria-live="polite"
      @scroll=${e.onChatScroll}
    >
      ${e.loading?l`
              <div class="muted">Loading chat…</div>
            `:g}
      ${Tl(Uh(e),v=>v.key,v=>v.kind==="reading-indicator"?Sh(r):v.kind==="stream"?_h(v.text,v.startedAt,e.onOpenSidebar,r):v.kind==="group"?Ch(v,{onOpenSidebar:e.onOpenSidebar,showReasoning:o,assistantName:e.assistantName,assistantAvatar:r.avatar}):g)}
    </div>
  `;return l`
    <section class="card chat">
      ${e.disabledReason?l`<div class="callout">${e.disabledReason}</div>`:g}

      ${e.error?l`<div class="callout danger">${e.error}</div>`:g}

      ${Ph(e.compactionStatus)}

      ${e.focusMode?l`
            <button
              class="chat-focus-exit"
              type="button"
              @click=${e.onToggleFocusMode}
              aria-label="Exit focus mode"
              title="Exit focus mode"
            >
              ${Y.x}
            </button>
          `:g}

      <div
        class="chat-split-container ${p?"chat-split-container--open":""}"
      >
        <div
          class="chat-main"
          style="flex: ${p?`0 0 ${f*100}%`:"1 1 100%"}"
        >
          ${m}
        </div>

        ${p?l`
              <resizable-divider
                .splitRatio=${f}
                @resize=${v=>e.onSplitRatioChange?.(v.detail.splitRatio)}
              ></resizable-divider>
              <div class="chat-sidebar">
                ${Lh({content:e.sidebarContent??null,error:e.sidebarError??null,onClose:e.onCloseSidebar,onViewRawText:()=>{!e.sidebarContent||!e.onOpenSidebar||e.onOpenSidebar(`\`\`\`
${e.sidebarContent}
\`\`\``)}})}
              </div>
            `:g}
      </div>

      ${e.queue.length?l`
            <div class="chat-queue" role="status" aria-live="polite">
              <div class="chat-queue__title">Queued (${e.queue.length})</div>
              <div class="chat-queue__list">
                ${e.queue.map(v=>l`
                    <div class="chat-queue__item">
                      <div class="chat-queue__text">
                        ${v.text||(v.attachments?.length?`Image (${v.attachments.length})`:"")}
                      </div>
                      <button
                        class="btn chat-queue__remove"
                        type="button"
                        aria-label="Remove queued message"
                        @click=${()=>e.onQueueRemove(v.id)}
                      >
                        ${Y.x}
                      </button>
                    </div>
                  `)}
              </div>
            </div>
          `:g}

      ${e.showNewMessages?l`
            <button
              class="btn chat-new-messages"
              type="button"
              @click=${e.onScrollToBottom}
            >
              New messages ${Y.arrowDown}
            </button>
          `:g}

      <div class="chat-compose">
        ${Dh(e)}
        <div class="chat-compose__row">
          <label class="field chat-compose__field">
            <span>Message</span>
            <textarea
              ${Ip(v=>v&&yo(v))}
              .value=${e.draft}
              ?disabled=${!e.connected}
              @keydown=${v=>{v.key==="Enter"&&(v.isComposing||v.keyCode===229||v.shiftKey||e.connected&&(v.preventDefault(),t&&e.onSend()))}}
              @input=${v=>{const b=v.target;yo(b),e.onDraftChange(b.value)}}
              @paste=${v=>Nh(v,e)}
              placeholder=${u}
            ></textarea>
          </label>
          <div class="chat-compose__actions">
            <button
              class="btn"
              ?disabled=${!e.connected||!i&&e.sending}
              @click=${i?e.onAbort:e.onNewSession}
            >
              ${i?"Stop":"New session"}
            </button>
            <button
              class="btn primary"
              ?disabled=${!e.connected}
              @click=${e.onSend}
            >
              ${n?"Queue":"Send"}<kbd class="btn-kbd">↵</kbd>
            </button>
          </div>
        </div>
      </div>
    </section>
  `}const bo=200;function Bh(e){const t=[];let n=null;for(const i of e){if(i.kind!=="message"){n&&(t.push(n),n=null),t.push(i);continue}const s=or(i.message),a=Ps(s.role),o=s.timestamp||Date.now();!n||n.role!==a?(n&&t.push(n),n={kind:"group",key:`group:${a}:${i.key}`,role:a,messages:[{message:i.message,key:i.key}],timestamp:o,isStreaming:!1}):n.messages.push({message:i.message,key:i.key})}return n&&t.push(n),t}function Uh(e){const t=[],n=Array.isArray(e.messages)?e.messages:[],i=Array.isArray(e.toolMessages)?e.toolMessages:[],s=Math.max(0,n.length-bo);s>0&&t.push({kind:"message",key:"chat:history:notice",message:{role:"system",content:`Showing last ${bo} messages (${s} hidden).`,timestamp:Date.now()}});for(let a=s;a<n.length;a++){const o=n[a],r=or(o);!e.showThinking&&r.role.toLowerCase()==="toolresult"||t.push({kind:"message",key:$o(o,a),message:o})}if(e.showThinking)for(let a=0;a<i.length;a++)t.push({kind:"message",key:$o(i[a],a+n.length),message:i[a]});if(e.stream!==null){const a=`stream:${e.sessionKey}:${e.streamStartedAt??"live"}`;e.stream.trim().length>0?t.push({kind:"stream",key:a,text:e.stream,startedAt:e.streamStartedAt??Date.now()}):t.push({kind:"reading-indicator",key:a})}return Bh(t)}function $o(e,t){const n=e,i=typeof n.toolCallId=="string"?n.toolCallId:"";if(i)return`tool:${i}`;const s=typeof n.id=="string"?n.id:"";if(s)return`msg:${s}`;const a=typeof n.messageId=="string"?n.messageId:"";if(a)return`msg:${a}`;const o=typeof n.timestamp=="number"?n.timestamp:null,r=typeof n.role=="string"?n.role:"unknown";return o!=null?`msg:${r}:${o}:${t}`:`msg:${r}:${t}`}const Yi={all:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <rect x="3" y="3" width="7" height="7"></rect>
      <rect x="14" y="3" width="7" height="7"></rect>
      <rect x="14" y="14" width="7" height="7"></rect>
      <rect x="3" y="14" width="7" height="7"></rect>
    </svg>
  `,env:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <circle cx="12" cy="12" r="3"></circle>
      <path
        d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"
      ></path>
    </svg>
  `,update:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
      <polyline points="7 10 12 15 17 10"></polyline>
      <line x1="12" y1="15" x2="12" y2="3"></line>
    </svg>
  `,agents:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path
        d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7h1a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1h-1v1a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-1H2a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1h1a7 7 0 0 1 7-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 0 1 2-2z"
      ></path>
      <circle cx="8" cy="14" r="1"></circle>
      <circle cx="16" cy="14" r="1"></circle>
    </svg>
  `,auth:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
      <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
    </svg>
  `,channels:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
    </svg>
  `,messages:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>
      <polyline points="22,6 12,13 2,6"></polyline>
    </svg>
  `,commands:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <polyline points="4 17 10 11 4 5"></polyline>
      <line x1="12" y1="19" x2="20" y2="19"></line>
    </svg>
  `,hooks:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
      <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
    </svg>
  `,skills:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <polygon
        points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"
      ></polygon>
    </svg>
  `,tools:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path
        d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"
      ></path>
    </svg>
  `,gateway:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <circle cx="12" cy="12" r="10"></circle>
      <line x1="2" y1="12" x2="22" y2="12"></line>
      <path
        d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"
      ></path>
    </svg>
  `,wizard:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M15 4V2"></path>
      <path d="M15 16v-2"></path>
      <path d="M8 9h2"></path>
      <path d="M20 9h2"></path>
      <path d="M17.8 11.8 19 13"></path>
      <path d="M15 9h0"></path>
      <path d="M17.8 6.2 19 5"></path>
      <path d="m3 21 9-9"></path>
      <path d="M12.2 6.2 11 5"></path>
    </svg>
  `,meta:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M12 20h9"></path>
      <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"></path>
    </svg>
  `,logging:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
      <polyline points="14 2 14 8 20 8"></polyline>
      <line x1="16" y1="13" x2="8" y2="13"></line>
      <line x1="16" y1="17" x2="8" y2="17"></line>
      <polyline points="10 9 9 9 8 9"></polyline>
    </svg>
  `,browser:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <circle cx="12" cy="12" r="10"></circle>
      <circle cx="12" cy="12" r="4"></circle>
      <line x1="21.17" y1="8" x2="12" y2="8"></line>
      <line x1="3.95" y1="6.06" x2="8.54" y2="14"></line>
      <line x1="10.88" y1="21.94" x2="15.46" y2="14"></line>
    </svg>
  `,ui:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
      <line x1="3" y1="9" x2="21" y2="9"></line>
      <line x1="9" y1="21" x2="9" y2="9"></line>
    </svg>
  `,models:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path
        d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"
      ></path>
      <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
      <line x1="12" y1="22.08" x2="12" y2="12"></line>
    </svg>
  `,bindings:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <rect x="2" y="2" width="20" height="8" rx="2" ry="2"></rect>
      <rect x="2" y="14" width="20" height="8" rx="2" ry="2"></rect>
      <line x1="6" y1="6" x2="6.01" y2="6"></line>
      <line x1="6" y1="18" x2="6.01" y2="18"></line>
    </svg>
  `,broadcast:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M4.9 19.1C1 15.2 1 8.8 4.9 4.9"></path>
      <path d="M7.8 16.2c-2.3-2.3-2.3-6.1 0-8.5"></path>
      <circle cx="12" cy="12" r="2"></circle>
      <path d="M16.2 7.8c2.3 2.3 2.3 6.1 0 8.5"></path>
      <path d="M19.1 4.9C23 8.8 23 15.1 19.1 19"></path>
    </svg>
  `,audio:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M9 18V5l12-2v13"></path>
      <circle cx="6" cy="18" r="3"></circle>
      <circle cx="18" cy="16" r="3"></circle>
    </svg>
  `,session:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
      <circle cx="9" cy="7" r="4"></circle>
      <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
      <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
    </svg>
  `,cron:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <circle cx="12" cy="12" r="10"></circle>
      <polyline points="12 6 12 12 16 14"></polyline>
    </svg>
  `,web:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <circle cx="12" cy="12" r="10"></circle>
      <line x1="2" y1="12" x2="22" y2="12"></line>
      <path
        d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"
      ></path>
    </svg>
  `,discovery:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <circle cx="11" cy="11" r="8"></circle>
      <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
    </svg>
  `,canvasHost:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
      <circle cx="8.5" cy="8.5" r="1.5"></circle>
      <polyline points="21 15 16 10 5 21"></polyline>
    </svg>
  `,talk:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
      <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
      <line x1="12" y1="19" x2="12" y2="23"></line>
      <line x1="8" y1="23" x2="16" y2="23"></line>
    </svg>
  `,plugins:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M12 2v6"></path>
      <path d="m4.93 10.93 4.24 4.24"></path>
      <path d="M2 12h6"></path>
      <path d="m4.93 13.07 4.24-4.24"></path>
      <path d="M12 22v-6"></path>
      <path d="m19.07 13.07-4.24-4.24"></path>
      <path d="M22 12h-6"></path>
      <path d="m19.07 10.93-4.24 4.24"></path>
    </svg>
  `,default:l`
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
      <polyline points="14 2 14 8 20 8"></polyline>
    </svg>
  `},wo=[{key:"env",label:"Environment"},{key:"update",label:"Updates"},{key:"agents",label:"Agents"},{key:"auth",label:"Authentication"},{key:"channels",label:"Channels"},{key:"messages",label:"Messages"},{key:"commands",label:"Commands"},{key:"hooks",label:"Hooks"},{key:"skills",label:"Skills"},{key:"tools",label:"Tools"},{key:"gateway",label:"Gateway"},{key:"wizard",label:"Setup Wizard"}],ko="__all__";function Ao(e){return Yi[e]??Yi.default}function Kh(e,t){const n=xs[e];return n||{label:t?.title??Ee(e),description:t?.description??""}}function zh(e){const{key:t,schema:n,uiHints:i}=e;if(!n||$e(n)!=="object"||!n.properties)return[];const s=Object.entries(n.properties).map(([a,o])=>{const r=le([t,a],i),c=r?.label??o.title??Ee(a),u=r?.help??o.description??"",f=r?.order??50;return{key:a,label:c,description:u,order:f}});return s.sort((a,o)=>a.order!==o.order?a.order-o.order:a.key.localeCompare(o.key)),s}function Hh(e,t){if(!e||!t)return[];const n=[];function i(s,a,o){if(s===a)return;if(typeof s!=typeof a){n.push({path:o,from:s,to:a});return}if(typeof s!="object"||s===null||a===null){s!==a&&n.push({path:o,from:s,to:a});return}if(Array.isArray(s)&&Array.isArray(a)){JSON.stringify(s)!==JSON.stringify(a)&&n.push({path:o,from:s,to:a});return}const r=s,c=a,u=new Set([...Object.keys(r),...Object.keys(c)]);for(const f of u)i(r[f],c[f],o?`${o}.${f}`:f)}return i(e,t,""),n}function xo(e,t=40){let n;try{n=JSON.stringify(e)??String(e)}catch{n=String(e)}return n.length<=t?n:n.slice(0,t-3)+"..."}function jh(e){const t=e.valid==null?"unknown":e.valid?"valid":"invalid",n=Bl(e.schema),i=n.schema?n.unsupportedPaths.length>0:!1,s=n.schema?.properties??{},a=wo.filter(C=>C.key in s),o=new Set(wo.map(C=>C.key)),r=Object.keys(s).filter(C=>!o.has(C)).map(C=>({key:C,label:C.charAt(0).toUpperCase()+C.slice(1)})),c=[...a,...r],u=e.activeSection&&n.schema&&$e(n.schema)==="object"?n.schema.properties?.[e.activeSection]:void 0,f=e.activeSection?Kh(e.activeSection,u):null,p=e.activeSection?zh({key:e.activeSection,schema:u,uiHints:e.uiHints}):[],m=e.formMode==="form"&&!!e.activeSection&&p.length>0,v=e.activeSubsection===ko,b=e.searchQuery||v?null:e.activeSubsection??p[0]?.key??null,d=e.formMode==="form"?Hh(e.originalValue,e.formValue):[],y=e.formMode==="raw"&&e.raw!==e.originalRaw,A=e.formMode==="form"?d.length>0:y,x=!!e.formValue&&!e.loading&&!!n.schema,T=e.connected&&!e.saving&&A&&(e.formMode==="raw"?!0:x),S=e.connected&&!e.applying&&!e.updating&&A&&(e.formMode==="raw"?!0:x),E=e.connected&&!e.applying&&!e.updating;return l`
    <div class="config-layout">
      <!-- Sidebar -->
      <aside class="config-sidebar">
        <div class="config-sidebar__header">
          <div class="config-sidebar__title">Settings</div>
          <span
            class="pill pill--sm ${t==="valid"?"pill--ok":t==="invalid"?"pill--danger":""}"
            >${t}</span
          >
        </div>

        <!-- Search -->
        <div class="config-search">
          <svg
            class="config-search__icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <circle cx="11" cy="11" r="8"></circle>
            <path d="M21 21l-4.35-4.35"></path>
          </svg>
          <input
            type="text"
            class="config-search__input"
            placeholder="Search settings..."
            .value=${e.searchQuery}
            @input=${C=>e.onSearchChange(C.target.value)}
          />
          ${e.searchQuery?l`
                <button
                  class="config-search__clear"
                  @click=${()=>e.onSearchChange("")}
                >
                  ×
                </button>
              `:g}
        </div>

        <!-- Section nav -->
        <nav class="config-nav">
          <button
            class="config-nav__item ${e.activeSection===null?"active":""}"
            @click=${()=>e.onSectionChange(null)}
          >
            <span class="config-nav__icon">${Yi.all}</span>
            <span class="config-nav__label">All Settings</span>
          </button>
          ${c.map(C=>l`
              <button
                class="config-nav__item ${e.activeSection===C.key?"active":""}"
                @click=${()=>e.onSectionChange(C.key)}
              >
                <span class="config-nav__icon"
                  >${Ao(C.key)}</span
                >
                <span class="config-nav__label">${C.label}</span>
              </button>
            `)}
        </nav>

        <!-- Mode toggle at bottom -->
        <div class="config-sidebar__footer">
          <div class="config-mode-toggle">
            <button
              class="config-mode-toggle__btn ${e.formMode==="form"?"active":""}"
              ?disabled=${e.schemaLoading||!e.schema}
              @click=${()=>e.onFormModeChange("form")}
            >
              Form
            </button>
            <button
              class="config-mode-toggle__btn ${e.formMode==="raw"?"active":""}"
              @click=${()=>e.onFormModeChange("raw")}
            >
              Raw
            </button>
          </div>
        </div>
      </aside>

      <!-- Main content -->
      <main class="config-main">
        <!-- Action bar -->
        <div class="config-actions">
          <div class="config-actions__left">
            ${A?l`
                  <span class="config-changes-badge"
                    >${e.formMode==="raw"?"Unsaved changes":`${d.length} unsaved change${d.length!==1?"s":""}`}</span
                  >
                `:l`
                    <span class="config-status muted">No changes</span>
                  `}
          </div>
          <div class="config-actions__right">
            <button
              class="btn btn--sm"
              ?disabled=${e.loading}
              @click=${e.onReload}
            >
              ${e.loading?"Loading…":"Reload"}
            </button>
            <button
              class="btn btn--sm primary"
              ?disabled=${!T}
              @click=${e.onSave}
            >
              ${e.saving?"Saving…":"Save"}
            </button>
            <button
              class="btn btn--sm"
              ?disabled=${!S}
              @click=${e.onApply}
            >
              ${e.applying?"Applying…":"Apply"}
            </button>
            <button
              class="btn btn--sm"
              ?disabled=${!E}
              @click=${e.onUpdate}
            >
              ${e.updating?"Updating…":"Update"}
            </button>
          </div>
        </div>

        <!-- Diff panel (form mode only - raw mode doesn't have granular diff) -->
        ${A&&e.formMode==="form"?l`
              <details class="config-diff">
                <summary class="config-diff__summary">
                  <span
                    >View ${d.length} pending
                    change${d.length!==1?"s":""}</span
                  >
                  <svg
                    class="config-diff__chevron"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                  >
                    <polyline points="6 9 12 15 18 9"></polyline>
                  </svg>
                </summary>
                <div class="config-diff__content">
                  ${d.map(C=>l`
                      <div class="config-diff__item">
                        <div class="config-diff__path">${C.path}</div>
                        <div class="config-diff__values">
                          <span class="config-diff__from"
                            >${xo(C.from)}</span
                          >
                          <span class="config-diff__arrow">→</span>
                          <span class="config-diff__to"
                            >${xo(C.to)}</span
                          >
                        </div>
                      </div>
                    `)}
                </div>
              </details>
            `:g}
        ${f&&e.formMode==="form"?l`
              <div class="config-section-hero">
                <div class="config-section-hero__icon">
                  ${Ao(e.activeSection??"")}
                </div>
                <div class="config-section-hero__text">
                  <div class="config-section-hero__title">
                    ${f.label}
                  </div>
                  ${f.description?l`<div class="config-section-hero__desc">
                        ${f.description}
                      </div>`:g}
                </div>
              </div>
            `:g}
        ${m?l`
              <div class="config-subnav">
                <button
                  class="config-subnav__item ${b===null?"active":""}"
                  @click=${()=>e.onSubsectionChange(ko)}
                >
                  All
                </button>
                ${p.map(C=>l`
                    <button
                      class="config-subnav__item ${b===C.key?"active":""}"
                      title=${C.description||C.label}
                      @click=${()=>e.onSubsectionChange(C.key)}
                    >
                      ${C.label}
                    </button>
                  `)}
              </div>
            `:g}

        <!-- Form content -->
        <div class="config-content">
          ${e.formMode==="form"?l`
                ${e.schemaLoading?l`
                        <div class="config-loading">
                          <div class="config-loading__spinner"></div>
                          <span>Loading schema…</span>
                        </div>
                      `:Qf({schema:n.schema,uiHints:e.uiHints,value:e.formValue,disabled:e.loading||!e.formValue,unsupportedPaths:n.unsupportedPaths,onPatch:e.onFormPatch,searchQuery:e.searchQuery,activeSection:e.activeSection,activeSubsection:b})}
                ${i?l`
                        <div class="callout danger" style="margin-top: 12px">
                          Form view can't safely edit some fields. Use Raw to avoid losing config entries.
                        </div>
                      `:g}
              `:l`
                <label class="field config-raw-field">
                  <span>Raw JSON5</span>
                  <textarea
                    .value=${e.raw}
                    @input=${C=>e.onRawChange(C.target.value)}
                  ></textarea>
                </label>
              `}
        </div>

        ${e.issues.length>0?l`<div class="callout danger" style="margin-top: 12px;">
              <pre class="code-block">
${JSON.stringify(e.issues,null,2)}</pre
              >
            </div>`:g}
      </main>
    </div>
  `}function Gh(e){const t=["last",...e.channels.filter(Boolean)],n=e.form.deliveryChannel?.trim();n&&!t.includes(n)&&t.push(n);const i=new Set;return t.filter(s=>i.has(s)?!1:(i.add(s),!0))}function qh(e,t){if(t==="last")return"last";const n=e.channelMeta?.find(i=>i.id===t);return n?.label?n.label:e.channelLabels?.[t]??t}function Wh(e){const t=Gh(e);return l`
    <section class="grid grid-cols-2">
      <div class="card">
        <div class="card-title">Scheduler</div>
        <div class="card-sub">Gateway-owned cron scheduler status.</div>
        <div class="stat-grid" style="margin-top: 16px;">
          <div class="stat">
            <div class="stat-label">Enabled</div>
            <div class="stat-value">
              ${e.status?e.status.enabled?"Yes":"No":"n/a"}
            </div>
          </div>
          <div class="stat">
            <div class="stat-label">Jobs</div>
            <div class="stat-value">${e.status?.jobs??"n/a"}</div>
          </div>
          <div class="stat">
            <div class="stat-label">Next wake</div>
            <div class="stat-value">${As(e.status?.nextWakeAtMs??null)}</div>
          </div>
        </div>
        <div class="row" style="margin-top: 12px;">
          <button class="btn" ?disabled=${e.loading} @click=${e.onRefresh}>
            ${e.loading?"Refreshing…":"Refresh"}
          </button>
          ${e.error?l`<span class="muted">${e.error}</span>`:g}
        </div>
      </div>

      <div class="card">
        <div class="card-title">New Job</div>
        <div class="card-sub">Create a scheduled wakeup or agent run.</div>
        <div class="form-grid" style="margin-top: 16px;">
          <label class="field">
            <span>Name</span>
            <input
              .value=${e.form.name}
              @input=${n=>e.onFormChange({name:n.target.value})}
            />
          </label>
          <label class="field">
            <span>Description</span>
            <input
              .value=${e.form.description}
              @input=${n=>e.onFormChange({description:n.target.value})}
            />
          </label>
          <label class="field">
            <span>Agent ID</span>
            <input
              .value=${e.form.agentId}
              @input=${n=>e.onFormChange({agentId:n.target.value})}
              placeholder="default"
            />
          </label>
          <label class="field checkbox">
            <span>Enabled</span>
            <input
              type="checkbox"
              .checked=${e.form.enabled}
              @change=${n=>e.onFormChange({enabled:n.target.checked})}
            />
          </label>
          <label class="field">
            <span>Schedule</span>
            <select
              .value=${e.form.scheduleKind}
              @change=${n=>e.onFormChange({scheduleKind:n.target.value})}
            >
              <option value="every">Every</option>
              <option value="at">At</option>
              <option value="cron">Cron</option>
            </select>
          </label>
        </div>
        ${Vh(e)}
        <div class="form-grid" style="margin-top: 12px;">
          <label class="field">
            <span>Session</span>
            <select
              .value=${e.form.sessionTarget}
              @change=${n=>e.onFormChange({sessionTarget:n.target.value})}
            >
              <option value="main">Main</option>
              <option value="isolated">Isolated</option>
            </select>
          </label>
          <label class="field">
            <span>Wake mode</span>
            <select
              .value=${e.form.wakeMode}
              @change=${n=>e.onFormChange({wakeMode:n.target.value})}
            >
              <option value="next-heartbeat">Next heartbeat</option>
              <option value="now">Now</option>
            </select>
          </label>
          <label class="field">
            <span>Payload</span>
            <select
              .value=${e.form.payloadKind}
              @change=${n=>e.onFormChange({payloadKind:n.target.value})}
            >
              <option value="systemEvent">System event</option>
              <option value="agentTurn">Agent turn</option>
            </select>
          </label>
        </div>
        <label class="field" style="margin-top: 12px;">
          <span>${e.form.payloadKind==="systemEvent"?"System text":"Agent message"}</span>
          <textarea
            .value=${e.form.payloadText}
            @input=${n=>e.onFormChange({payloadText:n.target.value})}
            rows="4"
          ></textarea>
        </label>
        ${e.form.payloadKind==="agentTurn"?l`
                <div class="form-grid" style="margin-top: 12px;">
                  <label class="field">
                    <span>Delivery</span>
                    <select
                      .value=${e.form.deliveryMode}
                      @change=${n=>e.onFormChange({deliveryMode:n.target.value})}
                    >
                      <option value="announce">Announce summary (default)</option>
                      <option value="none">None (internal)</option>
                    </select>
                  </label>
                  <label class="field">
                    <span>Timeout (seconds)</span>
                    <input
                      .value=${e.form.timeoutSeconds}
                      @input=${n=>e.onFormChange({timeoutSeconds:n.target.value})}
                    />
                  </label>
                  ${e.form.deliveryMode==="announce"?l`
                          <label class="field">
                            <span>Channel</span>
                            <select
                              .value=${e.form.deliveryChannel||"last"}
                              @change=${n=>e.onFormChange({deliveryChannel:n.target.value})}
                            >
                              ${t.map(n=>l`<option value=${n}>
                                    ${qh(e,n)}
                                  </option>`)}
                            </select>
                          </label>
                          <label class="field">
                            <span>To</span>
                            <input
                              .value=${e.form.deliveryTo}
                              @input=${n=>e.onFormChange({deliveryTo:n.target.value})}
                              placeholder="+1555… or chat id"
                            />
                          </label>
                        `:g}
                </div>
              `:g}
        <div class="row" style="margin-top: 14px;">
          <button class="btn primary" ?disabled=${e.busy} @click=${e.onAdd}>
            ${e.busy?"Saving…":"Add job"}
          </button>
        </div>
      </div>
    </section>

    <section class="card" style="margin-top: 18px;">
      <div class="card-title">Jobs</div>
      <div class="card-sub">All scheduled jobs stored in the gateway.</div>
      ${e.jobs.length===0?l`
              <div class="muted" style="margin-top: 12px">No jobs yet.</div>
            `:l`
            <div class="list" style="margin-top: 12px;">
              ${e.jobs.map(n=>Yh(n,e))}
            </div>
          `}
    </section>

    <section class="card" style="margin-top: 18px;">
      <div class="card-title">Run history</div>
      <div class="card-sub">Latest runs for ${e.runsJobId??"(select a job)"}.</div>
      ${e.runsJobId==null?l`
              <div class="muted" style="margin-top: 12px">Select a job to inspect run history.</div>
            `:e.runs.length===0?l`
                <div class="muted" style="margin-top: 12px">No runs yet.</div>
              `:l`
              <div class="list" style="margin-top: 12px;">
                ${e.runs.map(n=>Qh(n))}
              </div>
            `}
    </section>
  `}function Vh(e){const t=e.form;return t.scheduleKind==="at"?l`
      <label class="field" style="margin-top: 12px;">
        <span>Run at</span>
        <input
          type="datetime-local"
          .value=${t.scheduleAt}
          @input=${n=>e.onFormChange({scheduleAt:n.target.value})}
        />
      </label>
    `:t.scheduleKind==="every"?l`
      <div class="form-grid" style="margin-top: 12px;">
        <label class="field">
          <span>Every</span>
          <input
            .value=${t.everyAmount}
            @input=${n=>e.onFormChange({everyAmount:n.target.value})}
          />
        </label>
        <label class="field">
          <span>Unit</span>
          <select
            .value=${t.everyUnit}
            @change=${n=>e.onFormChange({everyUnit:n.target.value})}
          >
            <option value="minutes">Minutes</option>
            <option value="hours">Hours</option>
            <option value="days">Days</option>
          </select>
        </label>
      </div>
    `:l`
    <div class="form-grid" style="margin-top: 12px;">
      <label class="field">
        <span>Expression</span>
        <input
          .value=${t.cronExpr}
          @input=${n=>e.onFormChange({cronExpr:n.target.value})}
        />
      </label>
      <label class="field">
        <span>Timezone (optional)</span>
        <input
          .value=${t.cronTz}
          @input=${n=>e.onFormChange({cronTz:n.target.value})}
        />
      </label>
    </div>
  `}function Yh(e,t){const i=`list-item list-item-clickable${t.runsJobId===e.id?" list-item-selected":""}`;return l`
    <div class=${i} @click=${()=>t.onLoadRuns(e.id)}>
      <div class="list-main">
        <div class="list-title">${e.name}</div>
        <div class="list-sub">${Rl(e)}</div>
        <div class="muted">${Ml(e)}</div>
        ${e.agentId?l`<div class="muted">Agent: ${e.agentId}</div>`:g}
        <div class="chip-row" style="margin-top: 6px;">
          <span class="chip">${e.enabled?"enabled":"disabled"}</span>
          <span class="chip">${e.sessionTarget}</span>
          <span class="chip">${e.wakeMode}</span>
        </div>
      </div>
      <div class="list-meta">
        <div>${Il(e)}</div>
        <div class="row" style="justify-content: flex-end; margin-top: 8px;">
          <button
            class="btn"
            ?disabled=${t.busy}
            @click=${s=>{s.stopPropagation(),t.onToggle(e,!e.enabled)}}
          >
            ${e.enabled?"Disable":"Enable"}
          </button>
          <button
            class="btn"
            ?disabled=${t.busy}
            @click=${s=>{s.stopPropagation(),t.onRun(e)}}
          >
            Run
          </button>
          <button
            class="btn"
            ?disabled=${t.busy}
            @click=${s=>{s.stopPropagation(),t.onLoadRuns(e.id)}}
          >
            Runs
          </button>
          <button
            class="btn danger"
            ?disabled=${t.busy}
            @click=${s=>{s.stopPropagation(),t.onRemove(e)}}
          >
            Remove
          </button>
        </div>
      </div>
    </div>
  `}function Qh(e){return l`
    <div class="list-item">
      <div class="list-main">
        <div class="list-title">${e.status}</div>
        <div class="list-sub">${e.summary??""}</div>
      </div>
      <div class="list-meta">
        <div>${Nt(e.ts)}</div>
        <div class="muted">${e.durationMs??0}ms</div>
        ${e.error?l`<div class="muted">${e.error}</div>`:g}
      </div>
    </div>
  `}function Jh(e){const n=(e.status&&typeof e.status=="object"?e.status.securityAudit:null)?.summary??null,i=n?.critical??0,s=n?.warn??0,a=n?.info??0,o=i>0?"danger":s>0?"warn":"success",r=i>0?`${i} critical`:s>0?`${s} warnings`:"No critical issues";return l`
    <section class="grid grid-cols-2">
      <div class="card">
        <div class="row" style="justify-content: space-between;">
          <div>
            <div class="card-title">Snapshots</div>
            <div class="card-sub">Status, health, and heartbeat data.</div>
          </div>
          <button class="btn" ?disabled=${e.loading} @click=${e.onRefresh}>
            ${e.loading?"Refreshing…":"Refresh"}
          </button>
        </div>
        <div class="stack" style="margin-top: 12px;">
          <div>
            <div class="muted">Status</div>
            ${n?l`<div class="callout ${o}" style="margin-top: 8px;">
                  Security audit: ${r}${a>0?` · ${a} info`:""}. Run
                  <span class="mono">openclaw security audit --deep</span> for details.
                </div>`:g}
            <pre class="code-block">${JSON.stringify(e.status??{},null,2)}</pre>
          </div>
          <div>
            <div class="muted">Health</div>
            <pre class="code-block">${JSON.stringify(e.health??{},null,2)}</pre>
          </div>
          <div>
            <div class="muted">Last heartbeat</div>
            <pre class="code-block">${JSON.stringify(e.heartbeat??{},null,2)}</pre>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-title">Manual RPC</div>
        <div class="card-sub">Send a raw gateway method with JSON params.</div>
        <div class="form-grid" style="margin-top: 16px;">
          <label class="field">
            <span>Method</span>
            <input
              .value=${e.callMethod}
              @input=${c=>e.onCallMethodChange(c.target.value)}
              placeholder="system-presence"
            />
          </label>
          <label class="field">
            <span>Params (JSON)</span>
            <textarea
              .value=${e.callParams}
              @input=${c=>e.onCallParamsChange(c.target.value)}
              rows="6"
            ></textarea>
          </label>
        </div>
        <div class="row" style="margin-top: 12px;">
          <button class="btn primary" @click=${e.onCall}>Call</button>
        </div>
        ${e.callError?l`<div class="callout danger" style="margin-top: 12px;">
              ${e.callError}
            </div>`:g}
        ${e.callResult?l`<pre class="code-block" style="margin-top: 12px;">${e.callResult}</pre>`:g}
      </div>
    </section>

    <section class="card" style="margin-top: 18px;">
      <div class="card-title">Models</div>
      <div class="card-sub">Catalog from models.list.</div>
      <pre class="code-block" style="margin-top: 12px;">${JSON.stringify(e.models??[],null,2)}</pre>
    </section>

    <section class="card" style="margin-top: 18px;">
      <div class="card-title">Event Log</div>
      <div class="card-sub">Latest gateway events.</div>
      ${e.eventLog.length===0?l`
              <div class="muted" style="margin-top: 12px">No events yet.</div>
            `:l`
            <div class="list" style="margin-top: 12px;">
              ${e.eventLog.map(c=>l`
                  <div class="list-item">
                    <div class="list-main">
                      <div class="list-title">${c.event}</div>
                      <div class="list-sub">${new Date(c.ts).toLocaleTimeString()}</div>
                    </div>
                    <div class="list-meta">
                      <pre class="code-block">${uf(c.payload)}</pre>
                    </div>
                  </div>
                `)}
            </div>
          `}
    </section>
  `}function Zh(e){const t=Math.max(0,e),n=Math.floor(t/1e3);if(n<60)return`${n}s`;const i=Math.floor(n/60);return i<60?`${i}m`:`${Math.floor(i/60)}h`}function ze(e,t){return t?l`<div class="exec-approval-meta-row"><span>${e}</span><span>${t}</span></div>`:g}function Xh(e){const t=e.execApprovalQueue[0];if(!t)return g;const n=t.request,i=t.expiresAtMs-Date.now(),s=i>0?`expires in ${Zh(i)}`:"expired",a=e.execApprovalQueue.length;return l`
    <div class="exec-approval-overlay" role="dialog" aria-live="polite">
      <div class="exec-approval-card">
        <div class="exec-approval-header">
          <div>
            <div class="exec-approval-title">Exec approval needed</div>
            <div class="exec-approval-sub">${s}</div>
          </div>
          ${a>1?l`<div class="exec-approval-queue">${a} pending</div>`:g}
        </div>
        <div class="exec-approval-command mono">${n.command}</div>
        <div class="exec-approval-meta">
          ${ze("Host",n.host)}
          ${ze("Agent",n.agentId)}
          ${ze("Session",n.sessionKey)}
          ${ze("CWD",n.cwd)}
          ${ze("Resolved",n.resolvedPath)}
          ${ze("Security",n.security)}
          ${ze("Ask",n.ask)}
        </div>
        ${e.execApprovalError?l`<div class="exec-approval-error">${e.execApprovalError}</div>`:g}
        <div class="exec-approval-actions">
          <button
            class="btn primary"
            ?disabled=${e.execApprovalBusy}
            @click=${()=>e.handleExecApprovalDecision("allow-once")}
          >
            Allow once
          </button>
          <button
            class="btn"
            ?disabled=${e.execApprovalBusy}
            @click=${()=>e.handleExecApprovalDecision("allow-always")}
          >
            Always allow
          </button>
          <button
            class="btn danger"
            ?disabled=${e.execApprovalBusy}
            @click=${()=>e.handleExecApprovalDecision("deny")}
          >
            Deny
          </button>
        </div>
      </div>
    </div>
  `}function ev(e){const{pendingGatewayUrl:t}=e;return t?l`
    <div class="exec-approval-overlay" role="dialog" aria-modal="true" aria-live="polite">
      <div class="exec-approval-card">
        <div class="exec-approval-header">
          <div>
            <div class="exec-approval-title">Change Gateway URL</div>
            <div class="exec-approval-sub">This will reconnect to a different gateway server</div>
          </div>
        </div>
        <div class="exec-approval-command mono">${t}</div>
        <div class="callout danger" style="margin-top: 12px;">
          Only confirm if you trust this URL. Malicious URLs can compromise your system.
        </div>
        <div class="exec-approval-actions">
          <button
            class="btn primary"
            @click=${()=>e.handleGatewayUrlConfirm()}
          >
            Confirm
          </button>
          <button
            class="btn"
            @click=${()=>e.handleGatewayUrlCancel()}
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  `:g}function tv(e){return l`
    <section class="card">
      <div class="row" style="justify-content: space-between;">
        <div>
          <div class="card-title">Connected Instances</div>
          <div class="card-sub">Presence beacons from the gateway and clients.</div>
        </div>
        <button class="btn" ?disabled=${e.loading} @click=${e.onRefresh}>
          ${e.loading?"Loading…":"Refresh"}
        </button>
      </div>
      ${e.lastError?l`<div class="callout danger" style="margin-top: 12px;">
            ${e.lastError}
          </div>`:g}
      ${e.statusMessage?l`<div class="callout" style="margin-top: 12px;">
            ${e.statusMessage}
          </div>`:g}
      <div class="list" style="margin-top: 16px;">
        ${e.entries.length===0?l`
                <div class="muted">No instances reported yet.</div>
              `:e.entries.map(t=>nv(t))}
      </div>
    </section>
  `}function nv(e){const t=e.lastInputSeconds!=null?`${e.lastInputSeconds}s ago`:"n/a",n=e.mode??"unknown",i=Array.isArray(e.roles)?e.roles.filter(Boolean):[],s=Array.isArray(e.scopes)?e.scopes.filter(Boolean):[],a=s.length>0?s.length>3?`${s.length} scopes`:`scopes: ${s.join(", ")}`:null;return l`
    <div class="list-item">
      <div class="list-main">
        <div class="list-title">${e.host??"unknown host"}</div>
        <div class="list-sub">${rf(e)}</div>
        <div class="chip-row">
          <span class="chip">${n}</span>
          ${i.map(o=>l`<span class="chip">${o}</span>`)}
          ${a?l`<span class="chip">${a}</span>`:g}
          ${e.platform?l`<span class="chip">${e.platform}</span>`:g}
          ${e.deviceFamily?l`<span class="chip">${e.deviceFamily}</span>`:g}
          ${e.modelIdentifier?l`<span class="chip">${e.modelIdentifier}</span>`:g}
          ${e.version?l`<span class="chip">${e.version}</span>`:g}
        </div>
      </div>
      <div class="list-meta">
        <div>${cf(e)}</div>
        <div class="muted">Last input ${t}</div>
        <div class="muted">Reason ${e.reason??""}</div>
      </div>
    </div>
  `}const So=["trace","debug","info","warn","error","fatal"];function iv(e){if(!e)return"";const t=new Date(e);return Number.isNaN(t.getTime())?e:t.toLocaleTimeString()}function sv(e,t){return t?[e.message,e.subsystem,e.raw].filter(Boolean).join(" ").toLowerCase().includes(t):!0}function av(e){const t=e.filterText.trim().toLowerCase(),n=So.some(a=>!e.levelFilters[a]),i=e.entries.filter(a=>a.level&&!e.levelFilters[a.level]?!1:sv(a,t)),s=t||n?"filtered":"visible";return l`
    <section class="card">
      <div class="row" style="justify-content: space-between;">
        <div>
          <div class="card-title">Logs</div>
          <div class="card-sub">Gateway file logs (JSONL).</div>
        </div>
        <div class="row" style="gap: 8px;">
          <button class="btn" ?disabled=${e.loading} @click=${e.onRefresh}>
            ${e.loading?"Loading…":"Refresh"}
          </button>
          <button
            class="btn"
            ?disabled=${i.length===0}
            @click=${()=>e.onExport(i.map(a=>a.raw),s)}
          >
            Export ${s}
          </button>
        </div>
      </div>

      <div class="filters" style="margin-top: 14px;">
        <label class="field" style="min-width: 220px;">
          <span>Filter</span>
          <input
            .value=${e.filterText}
            @input=${a=>e.onFilterTextChange(a.target.value)}
            placeholder="Search logs"
          />
        </label>
        <label class="field checkbox">
          <span>Auto-follow</span>
          <input
            type="checkbox"
            .checked=${e.autoFollow}
            @change=${a=>e.onToggleAutoFollow(a.target.checked)}
          />
        </label>
      </div>

      <div class="chip-row" style="margin-top: 12px;">
        ${So.map(a=>l`
            <label class="chip log-chip ${a}">
              <input
                type="checkbox"
                .checked=${e.levelFilters[a]}
                @change=${o=>e.onLevelToggle(a,o.target.checked)}
              />
              <span>${a}</span>
            </label>
          `)}
      </div>

      ${e.file?l`<div class="muted" style="margin-top: 10px;">File: ${e.file}</div>`:g}
      ${e.truncated?l`
              <div class="callout" style="margin-top: 10px">Log output truncated; showing latest chunk.</div>
            `:g}
      ${e.error?l`<div class="callout danger" style="margin-top: 10px;">${e.error}</div>`:g}

      <div class="log-stream" style="margin-top: 12px;" @scroll=${e.onScroll}>
        ${i.length===0?l`
                <div class="muted" style="padding: 12px">No log entries.</div>
              `:i.map(a=>l`
                <div class="log-row">
                  <div class="log-time mono">${iv(a.time)}</div>
                  <div class="log-level ${a.level??""}">${a.level??""}</div>
                  <div class="log-subsystem mono">${a.subsystem??""}</div>
                  <div class="log-message mono">${a.message??a.raw}</div>
                </div>
              `)}
      </div>
    </section>
  `}function ov(e){const t=fv(e),n=yv(e);return l`
    ${$v(n)}
    ${bv(t)}
    ${lv(e)}
    <section class="card">
      <div class="row" style="justify-content: space-between;">
        <div>
          <div class="card-title">Nodes</div>
          <div class="card-sub">Paired devices and live links.</div>
        </div>
        <button class="btn" ?disabled=${e.loading} @click=${e.onRefresh}>
          ${e.loading?"Loading…":"Refresh"}
        </button>
      </div>
      <div class="list" style="margin-top: 16px;">
        ${e.nodes.length===0?l`
                <div class="muted">No nodes found.</div>
              `:e.nodes.map(i=>Lv(i))}
      </div>
    </section>
  `}function lv(e){const t=e.devicesList??{pending:[],paired:[]},n=Array.isArray(t.pending)?t.pending:[],i=Array.isArray(t.paired)?t.paired:[];return l`
    <section class="card">
      <div class="row" style="justify-content: space-between;">
        <div>
          <div class="card-title">Devices</div>
          <div class="card-sub">Pairing requests + role tokens.</div>
        </div>
        <button class="btn" ?disabled=${e.devicesLoading} @click=${e.onDevicesRefresh}>
          ${e.devicesLoading?"Loading…":"Refresh"}
        </button>
      </div>
      ${e.devicesError?l`<div class="callout danger" style="margin-top: 12px;">${e.devicesError}</div>`:g}
      <div class="list" style="margin-top: 16px;">
        ${n.length>0?l`
              <div class="muted" style="margin-bottom: 8px;">Pending</div>
              ${n.map(s=>rv(s,e))}
            `:g}
        ${i.length>0?l`
              <div class="muted" style="margin-top: 12px; margin-bottom: 8px;">Paired</div>
              ${i.map(s=>cv(s,e))}
            `:g}
        ${n.length===0&&i.length===0?l`
                <div class="muted">No paired devices.</div>
              `:g}
      </div>
    </section>
  `}function rv(e,t){const n=e.displayName?.trim()||e.deviceId,i=typeof e.ts=="number"?O(e.ts):"n/a",s=e.role?.trim()?`role: ${e.role}`:"role: -",a=e.isRepair?" · repair":"",o=e.remoteIp?` · ${e.remoteIp}`:"";return l`
    <div class="list-item">
      <div class="list-main">
        <div class="list-title">${n}</div>
        <div class="list-sub">${e.deviceId}${o}</div>
        <div class="muted" style="margin-top: 6px;">
          ${s} · requested ${i}${a}
        </div>
      </div>
      <div class="list-meta">
        <div class="row" style="justify-content: flex-end; gap: 8px; flex-wrap: wrap;">
          <button class="btn btn--sm primary" @click=${()=>t.onDeviceApprove(e.requestId)}>
            Approve
          </button>
          <button class="btn btn--sm" @click=${()=>t.onDeviceReject(e.requestId)}>
            Reject
          </button>
        </div>
      </div>
    </div>
  `}function cv(e,t){const n=e.displayName?.trim()||e.deviceId,i=e.remoteIp?` · ${e.remoteIp}`:"",s=`roles: ${Si(e.roles)}`,a=`scopes: ${Si(e.scopes)}`,o=Array.isArray(e.tokens)?e.tokens:[];return l`
    <div class="list-item">
      <div class="list-main">
        <div class="list-title">${n}</div>
        <div class="list-sub">${e.deviceId}${i}</div>
        <div class="muted" style="margin-top: 6px;">${s} · ${a}</div>
        ${o.length===0?l`
                <div class="muted" style="margin-top: 6px">Tokens: none</div>
              `:l`
              <div class="muted" style="margin-top: 10px;">Tokens</div>
              <div style="display: flex; flex-direction: column; gap: 8px; margin-top: 6px;">
                ${o.map(r=>dv(e.deviceId,r,t))}
              </div>
            `}
      </div>
    </div>
  `}function dv(e,t,n){const i=t.revokedAtMs?"revoked":"active",s=`scopes: ${Si(t.scopes)}`,a=O(t.rotatedAtMs??t.createdAtMs??t.lastUsedAtMs??null);return l`
    <div class="row" style="justify-content: space-between; gap: 8px;">
      <div class="list-sub">${t.role} · ${i} · ${s} · ${a}</div>
      <div class="row" style="justify-content: flex-end; gap: 6px; flex-wrap: wrap;">
        <button
          class="btn btn--sm"
          @click=${()=>n.onDeviceRotate(e,t.role,t.scopes)}
        >
          Rotate
        </button>
        ${t.revokedAtMs?g:l`
              <button
                class="btn btn--sm danger"
                @click=${()=>n.onDeviceRevoke(e,t.role)}
              >
                Revoke
              </button>
            `}
      </div>
    </div>
  `}const Re="__defaults__",_o=[{value:"deny",label:"Deny"},{value:"allowlist",label:"Allowlist"},{value:"full",label:"Full"}],uv=[{value:"off",label:"Off"},{value:"on-miss",label:"On miss"},{value:"always",label:"Always"}];function fv(e){const t=e.configForm,n=Cv(e.nodes),{defaultBinding:i,agents:s}=Tv(t),a=!!t,o=e.configSaving||e.configFormMode==="raw";return{ready:a,disabled:o,configDirty:e.configDirty,configLoading:e.configLoading,configSaving:e.configSaving,defaultBinding:i,agents:s,nodes:n,onBindDefault:e.onBindDefault,onBindAgent:e.onBindAgent,onSave:e.onSaveBindings,onLoadConfig:e.onLoadConfig,formMode:e.configFormMode}}function Co(e){return e==="allowlist"||e==="full"||e==="deny"?e:"deny"}function pv(e){return e==="always"||e==="off"||e==="on-miss"?e:"on-miss"}function gv(e){const t=e?.defaults??{};return{security:Co(t.security),ask:pv(t.ask),askFallback:Co(t.askFallback??"deny"),autoAllowSkills:!!(t.autoAllowSkills??!1)}}function hv(e){const t=e?.agents??{},n=Array.isArray(t.list)?t.list:[],i=[];return n.forEach(s=>{if(!s||typeof s!="object")return;const a=s,o=typeof a.id=="string"?a.id.trim():"";if(!o)return;const r=typeof a.name=="string"?a.name.trim():void 0,c=a.default===!0;i.push({id:o,name:r||void 0,isDefault:c})}),i}function vv(e,t){const n=hv(e),i=Object.keys(t?.agents??{}),s=new Map;n.forEach(o=>s.set(o.id,o)),i.forEach(o=>{s.has(o)||s.set(o,{id:o})});const a=Array.from(s.values());return a.length===0&&a.push({id:"main",isDefault:!0}),a.sort((o,r)=>{if(o.isDefault&&!r.isDefault)return-1;if(!o.isDefault&&r.isDefault)return 1;const c=o.name?.trim()?o.name:o.id,u=r.name?.trim()?r.name:r.id;return c.localeCompare(u)}),a}function mv(e,t){return e===Re?Re:e&&t.some(n=>n.id===e)?e:Re}function yv(e){const t=e.execApprovalsForm??e.execApprovalsSnapshot?.file??null,n=!!t,i=gv(t),s=vv(e.configForm,t),a=Ev(e.nodes),o=e.execApprovalsTarget;let r=o==="node"&&e.execApprovalsTargetNodeId?e.execApprovalsTargetNodeId:null;o==="node"&&r&&!a.some(p=>p.id===r)&&(r=null);const c=mv(e.execApprovalsSelectedAgent,s),u=c!==Re?(t?.agents??{})[c]??null:null,f=Array.isArray(u?.allowlist)?u.allowlist??[]:[];return{ready:n,disabled:e.execApprovalsSaving||e.execApprovalsLoading,dirty:e.execApprovalsDirty,loading:e.execApprovalsLoading,saving:e.execApprovalsSaving,form:t,defaults:i,selectedScope:c,selectedAgent:u,agents:s,allowlist:f,target:o,targetNodeId:r,targetNodes:a,onSelectScope:e.onExecApprovalsSelectAgent,onSelectTarget:e.onExecApprovalsTargetChange,onPatch:e.onExecApprovalsPatch,onRemove:e.onExecApprovalsRemove,onLoad:e.onLoadExecApprovals,onSave:e.onSaveExecApprovals}}function bv(e){const t=e.nodes.length>0,n=e.defaultBinding??"";return l`
    <section class="card">
      <div class="row" style="justify-content: space-between; align-items: center;">
        <div>
          <div class="card-title">Exec node binding</div>
          <div class="card-sub">
            Pin agents to a specific node when using <span class="mono">exec host=node</span>.
          </div>
        </div>
        <button
          class="btn"
          ?disabled=${e.disabled||!e.configDirty}
          @click=${e.onSave}
        >
          ${e.configSaving?"Saving…":"Save"}
        </button>
      </div>

      ${e.formMode==="raw"?l`
              <div class="callout warn" style="margin-top: 12px">
                Switch the Config tab to <strong>Form</strong> mode to edit bindings here.
              </div>
            `:g}

      ${e.ready?l`
            <div class="list" style="margin-top: 16px;">
              <div class="list-item">
                <div class="list-main">
                  <div class="list-title">Default binding</div>
                  <div class="list-sub">Used when agents do not override a node binding.</div>
                </div>
                <div class="list-meta">
                  <label class="field">
                    <span>Node</span>
                    <select
                      ?disabled=${e.disabled||!t}
                      @change=${i=>{const a=i.target.value.trim();e.onBindDefault(a||null)}}
                    >
                      <option value="" ?selected=${n===""}>Any node</option>
                      ${e.nodes.map(i=>l`<option
                            value=${i.id}
                            ?selected=${n===i.id}
                          >
                            ${i.label}
                          </option>`)}
                    </select>
                  </label>
                  ${t?g:l`
                          <div class="muted">No nodes with system.run available.</div>
                        `}
                </div>
              </div>

              ${e.agents.length===0?l`
                      <div class="muted">No agents found.</div>
                    `:e.agents.map(i=>_v(i,e))}
            </div>
          `:l`<div class="row" style="margin-top: 12px; gap: 12px;">
            <div class="muted">Load config to edit bindings.</div>
            <button class="btn" ?disabled=${e.configLoading} @click=${e.onLoadConfig}>
              ${e.configLoading?"Loading…":"Load config"}
            </button>
          </div>`}
    </section>
  `}function $v(e){const t=e.ready,n=e.target!=="node"||!!e.targetNodeId;return l`
    <section class="card">
      <div class="row" style="justify-content: space-between; align-items: center;">
        <div>
          <div class="card-title">Exec approvals</div>
          <div class="card-sub">
            Allowlist and approval policy for <span class="mono">exec host=gateway/node</span>.
          </div>
        </div>
        <button
          class="btn"
          ?disabled=${e.disabled||!e.dirty||!n}
          @click=${e.onSave}
        >
          ${e.saving?"Saving…":"Save"}
        </button>
      </div>

      ${wv(e)}

      ${t?l`
            ${kv(e)}
            ${Av(e)}
            ${e.selectedScope===Re?g:xv(e)}
          `:l`<div class="row" style="margin-top: 12px; gap: 12px;">
            <div class="muted">Load exec approvals to edit allowlists.</div>
            <button class="btn" ?disabled=${e.loading||!n} @click=${e.onLoad}>
              ${e.loading?"Loading…":"Load approvals"}
            </button>
          </div>`}
    </section>
  `}function wv(e){const t=e.targetNodes.length>0,n=e.targetNodeId??"";return l`
    <div class="list" style="margin-top: 12px;">
      <div class="list-item">
        <div class="list-main">
          <div class="list-title">Target</div>
          <div class="list-sub">
            Gateway edits local approvals; node edits the selected node.
          </div>
        </div>
        <div class="list-meta">
          <label class="field">
            <span>Host</span>
            <select
              ?disabled=${e.disabled}
              @change=${i=>{if(i.target.value==="node"){const o=e.targetNodes[0]?.id??null;e.onSelectTarget("node",n||o)}else e.onSelectTarget("gateway",null)}}
            >
              <option value="gateway" ?selected=${e.target==="gateway"}>Gateway</option>
              <option value="node" ?selected=${e.target==="node"}>Node</option>
            </select>
          </label>
          ${e.target==="node"?l`
                <label class="field">
                  <span>Node</span>
                  <select
                    ?disabled=${e.disabled||!t}
                    @change=${i=>{const a=i.target.value.trim();e.onSelectTarget("node",a||null)}}
                  >
                    <option value="" ?selected=${n===""}>Select node</option>
                    ${e.targetNodes.map(i=>l`<option
                          value=${i.id}
                          ?selected=${n===i.id}
                        >
                          ${i.label}
                        </option>`)}
                  </select>
                </label>
              `:g}
        </div>
      </div>
      ${e.target==="node"&&!t?l`
              <div class="muted">No nodes advertise exec approvals yet.</div>
            `:g}
    </div>
  `}function kv(e){return l`
    <div class="row" style="margin-top: 12px; gap: 8px; flex-wrap: wrap;">
      <span class="label">Scope</span>
      <div class="row" style="gap: 8px; flex-wrap: wrap;">
        <button
          class="btn btn--sm ${e.selectedScope===Re?"active":""}"
          @click=${()=>e.onSelectScope(Re)}
        >
          Defaults
        </button>
        ${e.agents.map(t=>{const n=t.name?.trim()?`${t.name} (${t.id})`:t.id;return l`
            <button
              class="btn btn--sm ${e.selectedScope===t.id?"active":""}"
              @click=${()=>e.onSelectScope(t.id)}
            >
              ${n}
            </button>
          `})}
      </div>
    </div>
  `}function Av(e){const t=e.selectedScope===Re,n=e.defaults,i=e.selectedAgent??{},s=t?["defaults"]:["agents",e.selectedScope],a=typeof i.security=="string"?i.security:void 0,o=typeof i.ask=="string"?i.ask:void 0,r=typeof i.askFallback=="string"?i.askFallback:void 0,c=t?n.security:a??"__default__",u=t?n.ask:o??"__default__",f=t?n.askFallback:r??"__default__",p=typeof i.autoAllowSkills=="boolean"?i.autoAllowSkills:void 0,m=p??n.autoAllowSkills,v=p==null;return l`
    <div class="list" style="margin-top: 16px;">
      <div class="list-item">
        <div class="list-main">
          <div class="list-title">Security</div>
          <div class="list-sub">
            ${t?"Default security mode.":`Default: ${n.security}.`}
          </div>
        </div>
        <div class="list-meta">
          <label class="field">
            <span>Mode</span>
            <select
              ?disabled=${e.disabled}
              @change=${b=>{const y=b.target.value;!t&&y==="__default__"?e.onRemove([...s,"security"]):e.onPatch([...s,"security"],y)}}
            >
              ${t?g:l`<option value="__default__" ?selected=${c==="__default__"}>
                    Use default (${n.security})
                  </option>`}
              ${_o.map(b=>l`<option
                    value=${b.value}
                    ?selected=${c===b.value}
                  >
                    ${b.label}
                  </option>`)}
            </select>
          </label>
        </div>
      </div>

      <div class="list-item">
        <div class="list-main">
          <div class="list-title">Ask</div>
          <div class="list-sub">
            ${t?"Default prompt policy.":`Default: ${n.ask}.`}
          </div>
        </div>
        <div class="list-meta">
          <label class="field">
            <span>Mode</span>
            <select
              ?disabled=${e.disabled}
              @change=${b=>{const y=b.target.value;!t&&y==="__default__"?e.onRemove([...s,"ask"]):e.onPatch([...s,"ask"],y)}}
            >
              ${t?g:l`<option value="__default__" ?selected=${u==="__default__"}>
                    Use default (${n.ask})
                  </option>`}
              ${uv.map(b=>l`<option
                    value=${b.value}
                    ?selected=${u===b.value}
                  >
                    ${b.label}
                  </option>`)}
            </select>
          </label>
        </div>
      </div>

      <div class="list-item">
        <div class="list-main">
          <div class="list-title">Ask fallback</div>
          <div class="list-sub">
            ${t?"Applied when the UI prompt is unavailable.":`Default: ${n.askFallback}.`}
          </div>
        </div>
        <div class="list-meta">
          <label class="field">
            <span>Fallback</span>
            <select
              ?disabled=${e.disabled}
              @change=${b=>{const y=b.target.value;!t&&y==="__default__"?e.onRemove([...s,"askFallback"]):e.onPatch([...s,"askFallback"],y)}}
            >
              ${t?g:l`<option value="__default__" ?selected=${f==="__default__"}>
                    Use default (${n.askFallback})
                  </option>`}
              ${_o.map(b=>l`<option
                    value=${b.value}
                    ?selected=${f===b.value}
                  >
                    ${b.label}
                  </option>`)}
            </select>
          </label>
        </div>
      </div>

      <div class="list-item">
        <div class="list-main">
          <div class="list-title">Auto-allow skill CLIs</div>
          <div class="list-sub">
            ${t?"Allow skill executables listed by the Gateway.":v?`Using default (${n.autoAllowSkills?"on":"off"}).`:`Override (${m?"on":"off"}).`}
          </div>
        </div>
        <div class="list-meta">
          <label class="field">
            <span>Enabled</span>
            <input
              type="checkbox"
              ?disabled=${e.disabled}
              .checked=${m}
              @change=${b=>{const d=b.target;e.onPatch([...s,"autoAllowSkills"],d.checked)}}
            />
          </label>
          ${!t&&!v?l`<button
                class="btn btn--sm"
                ?disabled=${e.disabled}
                @click=${()=>e.onRemove([...s,"autoAllowSkills"])}
              >
                Use default
              </button>`:g}
        </div>
      </div>
    </div>
  `}function xv(e){const t=["agents",e.selectedScope,"allowlist"],n=e.allowlist;return l`
    <div class="row" style="margin-top: 18px; justify-content: space-between;">
      <div>
        <div class="card-title">Allowlist</div>
        <div class="card-sub">Case-insensitive glob patterns.</div>
      </div>
      <button
        class="btn btn--sm"
        ?disabled=${e.disabled}
        @click=${()=>{const i=[...n,{pattern:""}];e.onPatch(t,i)}}
      >
        Add pattern
      </button>
    </div>
    <div class="list" style="margin-top: 12px;">
      ${n.length===0?l`
              <div class="muted">No allowlist entries yet.</div>
            `:n.map((i,s)=>Sv(e,i,s))}
    </div>
  `}function Sv(e,t,n){const i=t.lastUsedAt?O(t.lastUsedAt):"never",s=t.lastUsedCommand?_i(t.lastUsedCommand,120):null,a=t.lastResolvedPath?_i(t.lastResolvedPath,120):null;return l`
    <div class="list-item">
      <div class="list-main">
        <div class="list-title">${t.pattern?.trim()?t.pattern:"New pattern"}</div>
        <div class="list-sub">Last used: ${i}</div>
        ${s?l`<div class="list-sub mono">${s}</div>`:g}
        ${a?l`<div class="list-sub mono">${a}</div>`:g}
      </div>
      <div class="list-meta">
        <label class="field">
          <span>Pattern</span>
          <input
            type="text"
            .value=${t.pattern??""}
            ?disabled=${e.disabled}
            @input=${o=>{const r=o.target;e.onPatch(["agents",e.selectedScope,"allowlist",n,"pattern"],r.value)}}
          />
        </label>
        <button
          class="btn btn--sm danger"
          ?disabled=${e.disabled}
          @click=${()=>{if(e.allowlist.length<=1){e.onRemove(["agents",e.selectedScope,"allowlist"]);return}e.onRemove(["agents",e.selectedScope,"allowlist",n])}}
        >
          Remove
        </button>
      </div>
    </div>
  `}function _v(e,t){const n=e.binding??"__default__",i=e.name?.trim()?`${e.name} (${e.id})`:e.id,s=t.nodes.length>0;return l`
    <div class="list-item">
      <div class="list-main">
        <div class="list-title">${i}</div>
        <div class="list-sub">
          ${e.isDefault?"default agent":"agent"} ·
          ${n==="__default__"?`uses default (${t.defaultBinding??"any"})`:`override: ${e.binding}`}
        </div>
      </div>
      <div class="list-meta">
        <label class="field">
          <span>Binding</span>
          <select
            ?disabled=${t.disabled||!s}
            @change=${a=>{const r=a.target.value.trim();t.onBindAgent(e.index,r==="__default__"?null:r)}}
          >
            <option value="__default__" ?selected=${n==="__default__"}>
              Use default
            </option>
            ${t.nodes.map(a=>l`<option
                  value=${a.id}
                  ?selected=${n===a.id}
                >
                  ${a.label}
                </option>`)}
          </select>
        </label>
      </div>
    </div>
  `}function Cv(e){const t=[];for(const n of e){if(!(Array.isArray(n.commands)?n.commands:[]).some(r=>String(r)==="system.run"))continue;const a=typeof n.nodeId=="string"?n.nodeId.trim():"";if(!a)continue;const o=typeof n.displayName=="string"&&n.displayName.trim()?n.displayName.trim():a;t.push({id:a,label:o===a?a:`${o} · ${a}`})}return t.sort((n,i)=>n.label.localeCompare(i.label)),t}function Ev(e){const t=[];for(const n of e){if(!(Array.isArray(n.commands)?n.commands:[]).some(r=>String(r)==="system.execApprovals.get"||String(r)==="system.execApprovals.set"))continue;const a=typeof n.nodeId=="string"?n.nodeId.trim():"";if(!a)continue;const o=typeof n.displayName=="string"&&n.displayName.trim()?n.displayName.trim():a;t.push({id:a,label:o===a?a:`${o} · ${a}`})}return t.sort((n,i)=>n.label.localeCompare(i.label)),t}function Tv(e){const t={id:"main",name:void 0,index:0,isDefault:!0,binding:null};if(!e||typeof e!="object")return{defaultBinding:null,agents:[t]};const i=(e.tools??{}).exec??{},s=typeof i.node=="string"&&i.node.trim()?i.node.trim():null,a=e.agents??{},o=Array.isArray(a.list)?a.list:[];if(o.length===0)return{defaultBinding:s,agents:[t]};const r=[];return o.forEach((c,u)=>{if(!c||typeof c!="object")return;const f=c,p=typeof f.id=="string"?f.id.trim():"";if(!p)return;const m=typeof f.name=="string"?f.name.trim():void 0,v=f.default===!0,d=(f.tools??{}).exec??{},y=typeof d.node=="string"&&d.node.trim()?d.node.trim():null;r.push({id:p,name:m||void 0,index:u,isDefault:v,binding:y})}),r.length===0&&r.push(t),{defaultBinding:s,agents:r}}function Lv(e){const t=!!e.connected,n=!!e.paired,i=typeof e.displayName=="string"&&e.displayName.trim()||(typeof e.nodeId=="string"?e.nodeId:"unknown"),s=Array.isArray(e.caps)?e.caps:[],a=Array.isArray(e.commands)?e.commands:[];return l`
    <div class="list-item">
      <div class="list-main">
        <div class="list-title">${i}</div>
        <div class="list-sub">
          ${typeof e.nodeId=="string"?e.nodeId:""}
          ${typeof e.remoteIp=="string"?` · ${e.remoteIp}`:""}
          ${typeof e.version=="string"?` · ${e.version}`:""}
        </div>
        <div class="chip-row" style="margin-top: 6px;">
          <span class="chip">${n?"paired":"unpaired"}</span>
          <span class="chip ${t?"chip-ok":"chip-warn"}">
            ${t?"connected":"offline"}
          </span>
          ${s.slice(0,12).map(o=>l`<span class="chip">${String(o)}</span>`)}
          ${a.slice(0,8).map(o=>l`<span class="chip">${String(o)}</span>`)}
        </div>
      </div>
    </div>
  `}function Iv(e){const t=e.hello?.snapshot,n=t?.uptimeMs?jo(t.uptimeMs):"n/a",i=t?.policy?.tickIntervalMs?`${t.policy.tickIntervalMs}ms`:"n/a",s=(()=>{if(e.connected||!e.lastError)return null;const o=e.lastError.toLowerCase();if(!(o.includes("unauthorized")||o.includes("connect failed")))return null;const c=!!e.settings.token.trim(),u=!!e.password.trim();return!c&&!u?l`
        <div class="muted" style="margin-top: 8px">
          This gateway requires auth. Add a token or password, then click Connect.
          <div style="margin-top: 6px">
            <span class="mono">openclaw dashboard --no-open</span> → tokenized URL<br />
            <span class="mono">openclaw doctor --generate-gateway-token</span> → set token
          </div>
          <div style="margin-top: 6px">
            <a
              class="session-link"
              href="https://docs.openclaw.ai/web/dashboard"
              target="_blank"
              rel="noreferrer"
              title="Control UI auth docs (opens in new tab)"
              >Docs: Control UI auth</a
            >
          </div>
        </div>
      `:l`
      <div class="muted" style="margin-top: 8px">
        Auth failed. Re-copy a tokenized URL with
        <span class="mono">openclaw dashboard --no-open</span>, or update the token, then click Connect.
        <div style="margin-top: 6px">
          <a
            class="session-link"
            href="https://docs.openclaw.ai/web/dashboard"
            target="_blank"
            rel="noreferrer"
            title="Control UI auth docs (opens in new tab)"
            >Docs: Control UI auth</a
          >
        </div>
      </div>
    `})(),a=(()=>{if(e.connected||!e.lastError||(typeof window<"u"?window.isSecureContext:!0))return null;const r=e.lastError.toLowerCase();return!r.includes("secure context")&&!r.includes("device identity required")?null:l`
      <div class="muted" style="margin-top: 8px">
        This page is HTTP, so the browser blocks device identity. Use HTTPS (Tailscale Serve) or open
        <span class="mono">http://127.0.0.1:18789</span> on the gateway host.
        <div style="margin-top: 6px">
          If you must stay on HTTP, set
          <span class="mono">gateway.controlUi.allowInsecureAuth: true</span> (token-only).
        </div>
        <div style="margin-top: 6px">
          <a
            class="session-link"
            href="https://docs.openclaw.ai/gateway/tailscale"
            target="_blank"
            rel="noreferrer"
            title="Tailscale Serve docs (opens in new tab)"
            >Docs: Tailscale Serve</a
          >
          <span class="muted"> · </span>
          <a
            class="session-link"
            href="https://docs.openclaw.ai/web/control-ui#insecure-http"
            target="_blank"
            rel="noreferrer"
            title="Insecure HTTP docs (opens in new tab)"
            >Docs: Insecure HTTP</a
          >
        </div>
      </div>
    `})();return l`
    <section class="grid grid-cols-2">
      <div class="card">
        <div class="card-title">Gateway Access</div>
        <div class="card-sub">Where the dashboard connects and how it authenticates.</div>
        <div class="form-grid" style="margin-top: 16px;">
          <label class="field">
            <span>WebSocket URL</span>
            <input
              .value=${e.settings.gatewayUrl}
              @input=${o=>{const r=o.target.value;e.onSettingsChange({...e.settings,gatewayUrl:r})}}
              placeholder="ws://100.x.y.z:18789"
            />
          </label>
          <label class="field">
            <span>Gateway Token</span>
            <input
              .value=${e.settings.token}
              @input=${o=>{const r=o.target.value;e.onSettingsChange({...e.settings,token:r})}}
              placeholder="OPENCLAW_GATEWAY_TOKEN"
            />
          </label>
          <label class="field">
            <span>Password (not stored)</span>
            <input
              type="password"
              .value=${e.password}
              @input=${o=>{const r=o.target.value;e.onPasswordChange(r)}}
              placeholder="system or shared password"
            />
          </label>
          <label class="field">
            <span>Default Session Key</span>
            <input
              .value=${e.settings.sessionKey}
              @input=${o=>{const r=o.target.value;e.onSessionKeyChange(r)}}
            />
          </label>
        </div>
        <div class="row" style="margin-top: 14px;">
          <button class="btn" @click=${()=>e.onConnect()}>Connect</button>
          <button class="btn" @click=${()=>e.onRefresh()}>Refresh</button>
          <span class="muted">Click Connect to apply connection changes.</span>
        </div>
      </div>

      <div class="card">
        <div class="card-title">Snapshot</div>
        <div class="card-sub">Latest gateway handshake information.</div>
        <div class="stat-grid" style="margin-top: 16px;">
          <div class="stat">
            <div class="stat-label">Status</div>
            <div class="stat-value ${e.connected?"ok":"warn"}">
              ${e.connected?"Connected":"Disconnected"}
            </div>
          </div>
          <div class="stat">
            <div class="stat-label">Uptime</div>
            <div class="stat-value">${n}</div>
          </div>
          <div class="stat">
            <div class="stat-label">Tick Interval</div>
            <div class="stat-value">${i}</div>
          </div>
          <div class="stat">
            <div class="stat-label">Last Channels Refresh</div>
            <div class="stat-value">
              ${e.lastChannelsRefresh?O(e.lastChannelsRefresh):"n/a"}
            </div>
          </div>
        </div>
        ${e.lastError?l`<div class="callout danger" style="margin-top: 14px;">
              <div>${e.lastError}</div>
              ${s??""}
              ${a??""}
            </div>`:l`
                <div class="callout" style="margin-top: 14px">
                  Use Channels to link WhatsApp, Telegram, Discord, Signal, or iMessage.
                </div>
              `}
      </div>
    </section>

    <section class="grid grid-cols-3" style="margin-top: 18px;">
      <div class="card stat-card">
        <div class="stat-label">Instances</div>
        <div class="stat-value">${e.presenceCount}</div>
        <div class="muted">Presence beacons in the last 5 minutes.</div>
      </div>
      <div class="card stat-card">
        <div class="stat-label">Sessions</div>
        <div class="stat-value">${e.sessionsCount??"n/a"}</div>
        <div class="muted">Recent session keys tracked by the gateway.</div>
      </div>
      <div class="card stat-card">
        <div class="stat-label">Cron</div>
        <div class="stat-value">
          ${e.cronEnabled==null?"n/a":e.cronEnabled?"Enabled":"Disabled"}
        </div>
        <div class="muted">Next wake ${As(e.cronNext)}</div>
      </div>
    </section>

    <section class="card" style="margin-top: 18px;">
      <div class="card-title">Notes</div>
      <div class="card-sub">Quick reminders for remote control setups.</div>
      <div class="note-grid" style="margin-top: 14px;">
        <div>
          <div class="note-title">Tailscale serve</div>
          <div class="muted">
            Prefer serve mode to keep the gateway on loopback with tailnet auth.
          </div>
        </div>
        <div>
          <div class="note-title">Session hygiene</div>
          <div class="muted">Use /new or sessions.patch to reset context.</div>
        </div>
        <div>
          <div class="note-title">Cron reminders</div>
          <div class="muted">Use isolated sessions for recurring runs.</div>
        </div>
      </div>
    </section>
  `}const Rv=["","off","minimal","low","medium","high"],Mv=["","off","on"],Pv=[{value:"",label:"inherit"},{value:"off",label:"off (explicit)"},{value:"on",label:"on"}],Fv=["","off","on","stream"];function Nv(e){if(!e)return"";const t=e.trim().toLowerCase();return t==="z.ai"||t==="z-ai"?"zai":t}function ur(e){return Nv(e)==="zai"}function Dv(e){return ur(e)?Mv:Rv}function Ov(e,t){return!t||!e||e==="off"?e:"on"}function Bv(e,t){return e?t&&e==="on"?"low":e:null}function Uv(e){const t=e.result?.sessions??[];return l`
    <section class="card">
      <div class="row" style="justify-content: space-between;">
        <div>
          <div class="card-title">Sessions</div>
          <div class="card-sub">Active session keys and per-session overrides.</div>
        </div>
        <button class="btn" ?disabled=${e.loading} @click=${e.onRefresh}>
          ${e.loading?"Loading…":"Refresh"}
        </button>
      </div>

      <div class="filters" style="margin-top: 14px;">
        <label class="field">
          <span>Active within (minutes)</span>
          <input
            .value=${e.activeMinutes}
            @input=${n=>e.onFiltersChange({activeMinutes:n.target.value,limit:e.limit,includeGlobal:e.includeGlobal,includeUnknown:e.includeUnknown})}
          />
        </label>
        <label class="field">
          <span>Limit</span>
          <input
            .value=${e.limit}
            @input=${n=>e.onFiltersChange({activeMinutes:e.activeMinutes,limit:n.target.value,includeGlobal:e.includeGlobal,includeUnknown:e.includeUnknown})}
          />
        </label>
        <label class="field checkbox">
          <span>Include global</span>
          <input
            type="checkbox"
            .checked=${e.includeGlobal}
            @change=${n=>e.onFiltersChange({activeMinutes:e.activeMinutes,limit:e.limit,includeGlobal:n.target.checked,includeUnknown:e.includeUnknown})}
          />
        </label>
        <label class="field checkbox">
          <span>Include unknown</span>
          <input
            type="checkbox"
            .checked=${e.includeUnknown}
            @change=${n=>e.onFiltersChange({activeMinutes:e.activeMinutes,limit:e.limit,includeGlobal:e.includeGlobal,includeUnknown:n.target.checked})}
          />
        </label>
      </div>

      ${e.error?l`<div class="callout danger" style="margin-top: 12px;">${e.error}</div>`:g}

      <div class="muted" style="margin-top: 12px;">
        ${e.result?`Store: ${e.result.path}`:""}
      </div>

      <div class="table" style="margin-top: 16px;">
        <div class="table-head">
          <div>Key</div>
          <div>Label</div>
          <div>Kind</div>
          <div>Updated</div>
          <div>Tokens</div>
          <div>Thinking</div>
          <div>Verbose</div>
          <div>Reasoning</div>
          <div>Actions</div>
        </div>
        ${t.length===0?l`
                <div class="muted">No sessions found.</div>
              `:t.map(n=>Kv(n,e.basePath,e.onPatch,e.onDelete,e.loading))}
      </div>
    </section>
  `}function Kv(e,t,n,i,s){const a=e.updatedAt?O(e.updatedAt):"n/a",o=e.thinkingLevel??"",r=ur(e.modelProvider),c=Ov(o,r),u=Dv(e.modelProvider),f=e.verboseLevel??"",p=e.reasoningLevel??"",m=e.displayName??e.key,v=e.kind!=="global",b=v?`${vs("chat",t)}?session=${encodeURIComponent(e.key)}`:null;return l`
    <div class="table-row">
      <div class="mono">${v?l`<a href=${b} class="session-link">${m}</a>`:m}</div>
      <div>
        <input
          .value=${e.label??""}
          ?disabled=${s}
          placeholder="(optional)"
          @change=${d=>{const y=d.target.value.trim();n(e.key,{label:y||null})}}
        />
      </div>
      <div>${e.kind}</div>
      <div>${a}</div>
      <div>${df(e)}</div>
      <div>
        <select
          .value=${c}
          ?disabled=${s}
          @change=${d=>{const y=d.target.value;n(e.key,{thinkingLevel:Bv(y,r)})}}
        >
          ${u.map(d=>l`<option value=${d}>${d||"inherit"}</option>`)}
        </select>
      </div>
      <div>
        <select
          .value=${f}
          ?disabled=${s}
          @change=${d=>{const y=d.target.value;n(e.key,{verboseLevel:y||null})}}
        >
          ${Pv.map(d=>l`<option value=${d.value}>${d.label}</option>`)}
        </select>
      </div>
      <div>
        <select
          .value=${p}
          ?disabled=${s}
          @change=${d=>{const y=d.target.value;n(e.key,{reasoningLevel:y||null})}}
        >
          ${Fv.map(d=>l`<option value=${d}>${d||"inherit"}</option>`)}
        </select>
      </div>
      <div>
        <button class="btn danger" ?disabled=${s} @click=${()=>i(e.key)}>
          Delete
        </button>
      </div>
    </div>
  `}const dn=[{id:"workspace",label:"Workspace Skills",sources:["openclaw-workspace"]},{id:"built-in",label:"Built-in Skills",sources:["openclaw-bundled"]},{id:"installed",label:"Installed Skills",sources:["openclaw-managed"]},{id:"extra",label:"Extra Skills",sources:["openclaw-extra"]}];function zv(e){const t=new Map;for(const a of dn)t.set(a.id,{id:a.id,label:a.label,skills:[]});const n=dn.find(a=>a.id==="built-in"),i={id:"other",label:"Other Skills",skills:[]};for(const a of e){const o=a.bundled?n:dn.find(r=>r.sources.includes(a.source));o?t.get(o.id)?.skills.push(a):i.skills.push(a)}const s=dn.map(a=>t.get(a.id)).filter(a=>!!(a&&a.skills.length>0));return i.skills.length>0&&s.push(i),s}function Hv(e){const t=e.report?.skills??[],n=e.filter.trim().toLowerCase(),i=n?t.filter(a=>[a.name,a.description,a.source].join(" ").toLowerCase().includes(n)):t,s=zv(i);return l`
    <section class="card">
      <div class="row" style="justify-content: space-between;">
        <div>
          <div class="card-title">Skills</div>
          <div class="card-sub">Bundled, managed, and workspace skills.</div>
        </div>
        <button class="btn" ?disabled=${e.loading} @click=${e.onRefresh}>
          ${e.loading?"Loading…":"Refresh"}
        </button>
      </div>

      <div class="filters" style="margin-top: 14px;">
        <label class="field" style="flex: 1;">
          <span>Filter</span>
          <input
            .value=${e.filter}
            @input=${a=>e.onFilterChange(a.target.value)}
            placeholder="Search skills"
          />
        </label>
        <div class="muted">${i.length} shown</div>
      </div>

      ${e.error?l`<div class="callout danger" style="margin-top: 12px;">${e.error}</div>`:g}

      ${i.length===0?l`
              <div class="muted" style="margin-top: 16px">No skills found.</div>
            `:l`
            <div class="agent-skills-groups" style="margin-top: 16px;">
              ${s.map(a=>{const o=a.id==="workspace"||a.id==="built-in";return l`
                  <details class="agent-skills-group" ?open=${!o}>
                    <summary class="agent-skills-header">
                      <span>${a.label}</span>
                      <span class="muted">${a.skills.length}</span>
                    </summary>
                    <div class="list skills-grid">
                      ${a.skills.map(r=>jv(r,e))}
                    </div>
                  </details>
                `})}
            </div>
          `}
    </section>
  `}function jv(e,t){const n=t.busyKey===e.skillKey,i=t.edits[e.skillKey]??"",s=t.messages[e.skillKey]??null,a=e.install.length>0&&e.missing.bins.length>0,o=!!(e.bundled&&e.source!=="openclaw-bundled"),r=[...e.missing.bins.map(u=>`bin:${u}`),...e.missing.env.map(u=>`env:${u}`),...e.missing.config.map(u=>`config:${u}`),...e.missing.os.map(u=>`os:${u}`)],c=[];return e.disabled&&c.push("disabled"),e.blockedByAllowlist&&c.push("blocked by allowlist"),l`
    <div class="list-item">
      <div class="list-main">
        <div class="list-title">
          ${e.emoji?`${e.emoji} `:""}${e.name}
        </div>
        <div class="list-sub">${_i(e.description,140)}</div>
        <div class="chip-row" style="margin-top: 6px;">
          <span class="chip">${e.source}</span>
          ${o?l`
                  <span class="chip">bundled</span>
                `:g}
          <span class="chip ${e.eligible?"chip-ok":"chip-warn"}">
            ${e.eligible?"eligible":"blocked"}
          </span>
          ${e.disabled?l`
                  <span class="chip chip-warn">disabled</span>
                `:g}
        </div>
        ${r.length>0?l`
              <div class="muted" style="margin-top: 6px;">
                Missing: ${r.join(", ")}
              </div>
            `:g}
        ${c.length>0?l`
              <div class="muted" style="margin-top: 6px;">
                Reason: ${c.join(", ")}
              </div>
            `:g}
      </div>
      <div class="list-meta">
        <div class="row" style="justify-content: flex-end; flex-wrap: wrap;">
          <button
            class="btn"
            ?disabled=${n}
            @click=${()=>t.onToggle(e.skillKey,e.disabled)}
          >
            ${e.disabled?"Enable":"Disable"}
          </button>
          ${a?l`<button
                class="btn"
                ?disabled=${n}
                @click=${()=>t.onInstall(e.skillKey,e.name,e.install[0].id)}
              >
                ${n?"Installing…":e.install[0].label}
              </button>`:g}
        </div>
        ${s?l`<div
              class="muted"
              style="margin-top: 8px; color: ${s.kind==="error"?"var(--danger-color, #d14343)":"var(--success-color, #0a7f5a)"};"
            >
              ${s.message}
            </div>`:g}
        ${e.primaryEnv?l`
              <div class="field" style="margin-top: 10px;">
                <span>API key</span>
                <input
                  type="password"
                  .value=${i}
                  @input=${u=>t.onEdit(e.skillKey,u.target.value)}
                />
              </div>
              <button
                class="btn primary"
                style="margin-top: 8px;"
                ?disabled=${n}
                @click=${()=>t.onSaveKey(e.skillKey)}
              >
                Save key
              </button>
            `:g}
      </div>
    </div>
  `}const Gv=/^data:/i,qv=/^https?:\/\//i;function Wv(e){const t=e.agentsList?.agents??[],i=Uo(e.sessionKey)?.agentId??e.agentsList?.defaultId??"main",a=t.find(r=>r.id===i)?.identity,o=a?.avatarUrl??a?.avatar;if(o)return Gv.test(o)||qv.test(o)?o:a?.avatarUrl}function Vv(e){const t=e.presenceEntries.length,n=e.sessionsResult?.count??null,i=e.cronStatus?.nextWakeAtMs??null,s=e.connected?null:"Disconnected from gateway.",a=e.tab==="chat",o=a&&(e.settings.chatFocusMode||e.onboarding),r=e.onboarding?!1:e.settings.chatShowThinking,c=Wv(e),u=e.chatAvatarUrl??c??null,f=jt(e.basePath),p=f?`${f}/favicon.svg`:"/favicon.svg",m=e.configForm??e.configSnapshot?.config,v=e.agentsSelectedId??e.agentsList?.defaultId??e.agentsList?.agents?.[0]?.id??null,b=d=>{const A=(e.configForm??e.configSnapshot?.config)?.agents?.list,x=Array.isArray(A)?A:[];let T=x.findIndex(S=>S&&typeof S=="object"&&"id"in S&&S.id===d);if(T<0){const S=[...x,{id:d}];G(e,["agents","list"],S),T=S.length-1}return T};return l`
    <div class="shell ${a?"shell--chat":""} ${o?"shell--chat-focus":""} ${e.settings.navCollapsed?"shell--nav-collapsed":""} ${e.onboarding?"shell--onboarding":""}">
      <header class="topbar">
        <div class="topbar-left">
          <button
            class="nav-collapse-toggle"
            @click=${()=>e.applySettings({...e.settings,navCollapsed:!e.settings.navCollapsed})}
            title="${e.settings.navCollapsed?"Expand sidebar":"Collapse sidebar"}"
            aria-label="${e.settings.navCollapsed?"Expand sidebar":"Collapse sidebar"}"
          >
            <span class="nav-collapse-toggle__icon">${Y.menu}</span>
          </button>
          <div class="brand">
            <div class="brand-logo">
              <img src="${p}" alt="OpenClaw" />
            </div>
            <div class="brand-text">
              <div class="brand-title">OPENCLAW</div>
              <div class="brand-sub">Gateway Dashboard</div>
            </div>
          </div>
        </div>
        <div class="topbar-status">
          <div class="pill">
            <span class="statusDot ${e.connected?"ok":""}"></span>
            <span>Health</span>
            <span class="mono">${e.connected?"OK":"Offline"}</span>
          </div>
          ${ef(e)}
        </div>
      </header>
      <aside class="nav ${e.settings.navCollapsed?"nav--collapsed":""}">
        ${Sd.map(d=>{const y=e.settings.navGroupsCollapsed[d.label]??!1,A=d.tabs.some(x=>x===e.tab);return l`
            <div class="nav-group ${y&&!A?"nav-group--collapsed":""}">
              <button
                class="nav-label"
                @click=${()=>{const x={...e.settings.navGroupsCollapsed};x[d.label]=!y,e.applySettings({...e.settings,navGroupsCollapsed:x})}}
                aria-expanded=${!y}
              >
                <span class="nav-label__text">${d.label}</span>
                <span class="nav-label__chevron">${y?"+":"−"}</span>
              </button>
              <div class="nav-group__items">
                ${d.tabs.map(x=>Yu(e,x))}
              </div>
            </div>
          `})}
        <div class="nav-group nav-group--links">
          <div class="nav-label nav-label--static">
            <span class="nav-label__text">Resources</span>
          </div>
          <div class="nav-group__items">
            <a
              class="nav-item nav-item--external"
              href="https://docs.openclaw.ai"
              target="_blank"
              rel="noreferrer"
              title="Docs (opens in new tab)"
            >
              <span class="nav-item__icon" aria-hidden="true">${Y.book}</span>
              <span class="nav-item__text">Docs</span>
            </a>
          </div>
        </div>
      </aside>
      <main class="content ${a?"content--chat":""}">
        <section class="content-header">
          <div>
            <div class="page-title">${Ii(e.tab)}</div>
            <div class="page-sub">${Ed(e.tab)}</div>
          </div>
          <div class="page-meta">
            ${e.lastError?l`<div class="pill danger">${e.lastError}</div>`:g}
            ${a?Qu(e):g}
          </div>
        </section>

        ${e.tab==="overview"?Iv({connected:e.connected,hello:e.hello,settings:e.settings,password:e.password,lastError:e.lastError,presenceCount:t,sessionsCount:n,cronEnabled:e.cronStatus?.enabled??null,cronNext:i,lastChannelsRefresh:e.channelsLastSuccess,onSettingsChange:d=>e.applySettings(d),onPasswordChange:d=>e.password=d,onSessionKeyChange:d=>{e.sessionKey=d,e.chatMessage="",e.resetToolStream(),e.applySettings({...e.settings,sessionKey:d,lastActiveSessionKey:d}),e.loadAssistantIdentity()},onConnect:()=>e.connect(),onRefresh:()=>e.loadOverview()}):g}

        ${e.tab==="channels"?mp({connected:e.connected,loading:e.channelsLoading,snapshot:e.channelsSnapshot,lastError:e.channelsError,lastSuccessAt:e.channelsLastSuccess,whatsappMessage:e.whatsappLoginMessage,whatsappQrDataUrl:e.whatsappLoginQrDataUrl,whatsappConnected:e.whatsappLoginConnected,whatsappBusy:e.whatsappBusy,configSchema:e.configSchema,configSchemaLoading:e.configSchemaLoading,configForm:e.configForm,configUiHints:e.configUiHints,configSaving:e.configSaving,configFormDirty:e.configFormDirty,nostrProfileFormState:e.nostrProfileFormState,nostrProfileAccountId:e.nostrProfileAccountId,onRefresh:d=>se(e,d),onWhatsAppStart:d=>e.handleWhatsAppStart(d),onWhatsAppWait:()=>e.handleWhatsAppWait(),onWhatsAppLogout:()=>e.handleWhatsAppLogout(),onConfigPatch:(d,y)=>G(e,d,y),onConfigSave:()=>e.handleChannelConfigSave(),onConfigReload:()=>e.handleChannelConfigReload(),onNostrProfileEdit:(d,y)=>e.handleNostrProfileEdit(d,y),onNostrProfileCancel:()=>e.handleNostrProfileCancel(),onNostrProfileFieldChange:(d,y)=>e.handleNostrProfileFieldChange(d,y),onNostrProfileSave:()=>e.handleNostrProfileSave(),onNostrProfileImport:()=>e.handleNostrProfileImport(),onNostrProfileToggleAdvanced:()=>e.handleNostrProfileToggleAdvanced()}):g}

        ${e.tab==="instances"?tv({loading:e.presenceLoading,entries:e.presenceEntries,lastError:e.presenceError,statusMessage:e.presenceStatus,onRefresh:()=>hs(e)}):g}

        ${e.tab==="sessions"?Uv({loading:e.sessionsLoading,result:e.sessionsResult,error:e.sessionsError,activeMinutes:e.sessionsFilterActive,limit:e.sessionsFilterLimit,includeGlobal:e.sessionsIncludeGlobal,includeUnknown:e.sessionsIncludeUnknown,basePath:e.basePath,onFiltersChange:d=>{e.sessionsFilterActive=d.activeMinutes,e.sessionsFilterLimit=d.limit,e.sessionsIncludeGlobal=d.includeGlobal,e.sessionsIncludeUnknown=d.includeUnknown},onRefresh:()=>Ze(e),onPatch:(d,y)=>bd(e,d,y),onDelete:d=>$d(e,d)}):g}

        ${e.tab==="cron"?Wh({loading:e.cronLoading,status:e.cronStatus,jobs:e.cronJobs,error:e.cronError,busy:e.cronBusy,form:e.cronForm,channels:e.channelsSnapshot?.channelMeta?.length?Array.isArray(e.channelsSnapshot.channelMeta)?e.channelsSnapshot.channelMeta.map(d=>d.id):Object.keys(e.channelsSnapshot.channelMeta):e.channelsSnapshot?.channelOrder??[],channelLabels:e.channelsSnapshot?.channelLabels??{},channelMeta:Array.isArray(e.channelsSnapshot?.channelMeta)?e.channelsSnapshot?.channelMeta??[]:Object.values(e.channelsSnapshot?.channelMeta??{}),runsJobId:e.cronRunsJobId,runs:e.cronRuns,onFormChange:d=>e.cronForm={...e.cronForm,...d},onRefresh:()=>e.loadCron(),onAdd:()=>Rc(e),onToggle:(d,y)=>Mc(e,d,y),onRun:d=>Pc(e,d),onRemove:d=>Fc(e,d),onLoadRuns:d=>qo(e,d)}):g}

        ${e.tab==="agents"?kf({loading:e.agentsLoading,error:e.agentsError,agentsList:e.agentsList,selectedAgentId:v,activePanel:e.agentsPanel,configForm:m,configLoading:e.configLoading,configSaving:e.configSaving,configDirty:e.configFormDirty,channelsLoading:e.channelsLoading,channelsError:e.channelsError,channelsSnapshot:e.channelsSnapshot,channelsLastSuccess:e.channelsLastSuccess,cronLoading:e.cronLoading,cronStatus:e.cronStatus,cronJobs:e.cronJobs,cronError:e.cronError,agentFilesLoading:e.agentFilesLoading,agentFilesError:e.agentFilesError,agentFilesList:e.agentFilesList,agentFileActive:e.agentFileActive,agentFileContents:e.agentFileContents,agentFileDrafts:e.agentFileDrafts,agentFileSaving:e.agentFileSaving,agentIdentityLoading:e.agentIdentityLoading,agentIdentityError:e.agentIdentityError,agentIdentityById:e.agentIdentityById,agentSkillsLoading:e.agentSkillsLoading,agentSkillsReport:e.agentSkillsReport,agentSkillsError:e.agentSkillsError,agentSkillsAgentId:e.agentSkillsAgentId,skillsFilter:e.skillsFilter,onRefresh:async()=>{await ls(e);const d=e.agentsList?.agents?.map(y=>y.id)??[];d.length>0&&Ho(e,d)},onSelectAgent:d=>{e.agentsSelectedId!==d&&(e.agentsSelectedId=d,e.agentFilesList=null,e.agentFilesError=null,e.agentFilesLoading=!1,e.agentFileActive=null,e.agentFileContents={},e.agentFileDrafts={},e.agentSkillsReport=null,e.agentSkillsError=null,e.agentSkillsAgentId=null,zo(e,d),e.agentsPanel==="files"&&gi(e,d),e.agentsPanel==="skills"&&pn(e,d))},onSelectPanel:d=>{e.agentsPanel=d,d==="files"&&v&&e.agentFilesList?.agentId!==v&&(e.agentFilesList=null,e.agentFilesError=null,e.agentFileActive=null,e.agentFileContents={},e.agentFileDrafts={},gi(e,v)),d==="skills"&&v&&pn(e,v),d==="channels"&&se(e,!1),d==="cron"&&e.loadCron()},onLoadFiles:d=>{(async()=>(await gi(e,d),e.agentFileActive&&await Ba(e,d,e.agentFileActive,{force:!0,preserveDraft:!0})))()},onSelectFile:d=>{e.agentFileActive=d,v&&Ba(e,v,d)},onFileDraftChange:(d,y)=>{e.agentFileDrafts={...e.agentFileDrafts,[d]:y}},onFileReset:d=>{const y=e.agentFileContents[d]??"";e.agentFileDrafts={...e.agentFileDrafts,[d]:y}},onFileSave:d=>{if(!v)return;const y=e.agentFileDrafts[d]??e.agentFileContents[d]??"";af(e,v,d,y)},onToolsProfileChange:(d,y,A)=>{if(!m)return;const x=m.agents?.list;if(!Array.isArray(x))return;const T=x.findIndex(E=>E&&typeof E=="object"&&"id"in E&&E.id===d);if(T<0)return;const S=["agents","list",T,"tools"];y?G(e,[...S,"profile"],y):de(e,[...S,"profile"]),A&&de(e,[...S,"allow"])},onToolsOverridesChange:(d,y,A)=>{if(!m)return;const x=m.agents?.list;if(!Array.isArray(x))return;const T=x.findIndex(E=>E&&typeof E=="object"&&"id"in E&&E.id===d);if(T<0)return;const S=["agents","list",T,"tools"];y.length>0?G(e,[...S,"alsoAllow"],y):de(e,[...S,"alsoAllow"]),A.length>0?G(e,[...S,"deny"],A):de(e,[...S,"deny"])},onConfigReload:()=>ge(e),onConfigSave:()=>fn(e),onChannelsRefresh:()=>se(e,!1),onCronRefresh:()=>e.loadCron(),onSkillsFilterChange:d=>e.skillsFilter=d,onSkillsRefresh:()=>{v&&pn(e,v)},onAgentSkillToggle:(d,y,A)=>{if(!m)return;const x=m.agents?.list;if(!Array.isArray(x))return;const T=x.findIndex(Q=>Q&&typeof Q=="object"&&"id"in Q&&Q.id===d);if(T<0)return;const S=x[T],E=y.trim();if(!E)return;const C=e.agentSkillsReport?.skills?.map(Q=>Q.name).filter(Boolean)??[],ce=(Array.isArray(S.skills)?S.skills.map(Q=>String(Q).trim()).filter(Boolean):void 0)??C,H=new Set(ce);A?H.add(E):H.delete(E),G(e,["agents","list",T,"skills"],[...H])},onAgentSkillsClear:d=>{if(!m)return;const y=m.agents?.list;if(!Array.isArray(y))return;const A=y.findIndex(x=>x&&typeof x=="object"&&"id"in x&&x.id===d);A<0||de(e,["agents","list",A,"skills"])},onAgentSkillsDisableAll:d=>{if(!m)return;const y=m.agents?.list;if(!Array.isArray(y))return;const A=y.findIndex(x=>x&&typeof x=="object"&&"id"in x&&x.id===d);A<0||G(e,["agents","list",A,"skills"],[])},onModelChange:(d,y)=>{if(!m)return;const A=e.agentsList?.defaultId??null;if(A&&d===A){const P=["agents","defaults","model"],H=(m.agents?.defaults??{}).model;if(!y){de(e,P);return}if(H&&typeof H=="object"&&!Array.isArray(H)){const Q=H.fallbacks,D={primary:y,...Array.isArray(Q)?{fallbacks:Q}:{}};G(e,P,D)}else G(e,P,{primary:y});return}const x=b(d),T=["agents","list",x,"model"];if(!y){de(e,T);return}const S=(e.configForm??e.configSnapshot?.config)?.agents?.list,C=(Array.isArray(S)&&S[x]?S[x]:null)?.model;if(C&&typeof C=="object"&&!Array.isArray(C)){const P=C.fallbacks,ce={primary:y,...Array.isArray(P)?{fallbacks:P}:{}};G(e,T,ce)}else G(e,T,y)},onModelFallbacksChange:(d,y)=>{if(!m)return;const A=y.map(D=>D.trim()).filter(Boolean),x=e.agentsList?.defaultId??null;if(x&&d===x){const D=["agents","defaults","model"],ae=(m.agents?.defaults??{}).model,he=(()=>{if(typeof ae=="string")return ae.trim()||null;if(ae&&typeof ae=="object"&&!Array.isArray(ae)){const qt=ae.primary;if(typeof qt=="string")return qt.trim()||null}return null})();if(A.length===0){he?G(e,D,{primary:he}):de(e,D);return}G(e,D,he?{primary:he,fallbacks:A}:{fallbacks:A});return}const T=b(d),S=["agents","list",T,"model"],E=(e.configForm??e.configSnapshot?.config)?.agents?.list,P=(Array.isArray(E)&&E[T]?E[T]:null)?.model;if(!P)return;const H=(()=>{if(typeof P=="string")return P.trim()||null;if(P&&typeof P=="object"&&!Array.isArray(P)){const D=P.primary;if(typeof D=="string")return D.trim()||null}return null})();if(A.length===0){H?G(e,S,H):de(e,S);return}G(e,S,H?{primary:H,fallbacks:A}:{fallbacks:A})}}):g}

        ${e.tab==="skills"?Hv({loading:e.skillsLoading,report:e.skillsReport,error:e.skillsError,filter:e.skillsFilter,edits:e.skillEdits,messages:e.skillMessages,busyKey:e.skillsBusyKey,onFilterChange:d=>e.skillsFilter=d,onRefresh:()=>Ht(e,{clearMessages:!0}),onToggle:(d,y)=>kd(e,d,y),onEdit:(d,y)=>wd(e,d,y),onSaveKey:d=>Ad(e,d),onInstall:(d,y,A)=>xd(e,d,y,A)}):g}

        ${e.tab==="nodes"?ov({loading:e.nodesLoading,nodes:e.nodes,devicesLoading:e.devicesLoading,devicesError:e.devicesError,devicesList:e.devicesList,configForm:e.configForm??e.configSnapshot?.config,configLoading:e.configLoading,configSaving:e.configSaving,configDirty:e.configFormDirty,configFormMode:e.configFormMode,execApprovalsLoading:e.execApprovalsLoading,execApprovalsSaving:e.execApprovalsSaving,execApprovalsDirty:e.execApprovalsDirty,execApprovalsSnapshot:e.execApprovalsSnapshot,execApprovalsForm:e.execApprovalsForm,execApprovalsSelectedAgent:e.execApprovalsSelectedAgent,execApprovalsTarget:e.execApprovalsTarget,execApprovalsTargetNodeId:e.execApprovalsTargetNodeId,onRefresh:()=>In(e),onDevicesRefresh:()=>Ne(e),onDeviceApprove:d=>cd(e,d),onDeviceReject:d=>dd(e,d),onDeviceRotate:(d,y,A)=>ud(e,{deviceId:d,role:y,scopes:A}),onDeviceRevoke:(d,y)=>fd(e,{deviceId:d,role:y}),onLoadConfig:()=>ge(e),onLoadExecApprovals:()=>{const d=e.execApprovalsTarget==="node"&&e.execApprovalsTargetNodeId?{kind:"node",nodeId:e.execApprovalsTargetNodeId}:{kind:"gateway"};return gs(e,d)},onBindDefault:d=>{d?G(e,["tools","exec","node"],d):de(e,["tools","exec","node"])},onBindAgent:(d,y)=>{const A=["agents","list",d,"tools","exec","node"];y?G(e,A,y):de(e,A)},onSaveBindings:()=>fn(e),onExecApprovalsTargetChange:(d,y)=>{e.execApprovalsTarget=d,e.execApprovalsTargetNodeId=y,e.execApprovalsSnapshot=null,e.execApprovalsForm=null,e.execApprovalsDirty=!1,e.execApprovalsSelectedAgent=null},onExecApprovalsSelectAgent:d=>{e.execApprovalsSelectedAgent=d},onExecApprovalsPatch:(d,y)=>md(e,d,y),onExecApprovalsRemove:d=>yd(e,d),onSaveExecApprovals:()=>{const d=e.execApprovalsTarget==="node"&&e.execApprovalsTargetNodeId?{kind:"node",nodeId:e.execApprovalsTargetNodeId}:{kind:"gateway"};return vd(e,d)}}):g}

        ${e.tab==="chat"?Oh({sessionKey:e.sessionKey,onSessionKeyChange:d=>{e.sessionKey=d,e.chatMessage="",e.chatAttachments=[],e.chatStream=null,e.chatRunId=null,e.chatStreamStartedAt=null,e.chatQueue=[],e.resetToolStream(),e.resetChatScroll(),e.applySettings({...e.settings,sessionKey:d,lastActiveSessionKey:d}),e.loadAssistantIdentity(),Bt(e),Pi(e)},thinkingLevel:e.chatThinkingLevel,showThinking:r,loading:e.chatLoading,sending:e.chatSending,assistantAvatarUrl:u,messages:e.chatMessages,toolMessages:e.chatToolMessages,stream:e.chatStream,streamStartedAt:null,draft:e.chatMessage,queue:e.chatQueue,connected:e.connected,canSend:e.connected,disabledReason:s,error:e.lastError,sessions:e.sessionsResult,focusMode:o,onRefresh:()=>Promise.all([Bt(e),Pi(e)]),onToggleFocusMode:()=>{e.onboarding||e.applySettings({...e.settings,chatFocusMode:!e.settings.chatFocusMode})},onChatScroll:d=>e.handleChatScroll(d),onDraftChange:d=>e.chatMessage=d,attachments:e.chatAttachments,onAttachmentsChange:d=>e.chatAttachments=d,onSend:()=>e.handleSendChat(),canAbort:!!e.chatRunId,onAbort:()=>{e.handleAbortChat()},onQueueRemove:d=>e.removeQueuedMessage(d),onNewSession:()=>e.handleSendChat("/new",{restoreDraft:!0}),showNewMessages:e.chatNewMessagesBelow,onScrollToBottom:()=>e.scrollToBottom(),sidebarOpen:e.sidebarOpen,sidebarContent:e.sidebarContent,sidebarError:e.sidebarError,splitRatio:e.splitRatio,onOpenSidebar:d=>e.handleOpenSidebar(d),onCloseSidebar:()=>e.handleCloseSidebar(),onSplitRatioChange:d=>e.handleSplitRatioChange(d),assistantName:e.assistantName,assistantAvatar:e.assistantAvatar}):g}

        ${e.tab==="config"?jh({raw:e.configRaw,originalRaw:e.configRawOriginal,valid:e.configValid,issues:e.configIssues,loading:e.configLoading,saving:e.configSaving,applying:e.configApplying,updating:e.updateRunning,connected:e.connected,schema:e.configSchema,schemaLoading:e.configSchemaLoading,uiHints:e.configUiHints,formMode:e.configFormMode,formValue:e.configForm,originalValue:e.configFormOriginal,searchQuery:e.configSearchQuery,activeSection:e.configActiveSection,activeSubsection:e.configActiveSubsection,onRawChange:d=>{e.configRaw=d},onFormModeChange:d=>e.configFormMode=d,onFormPatch:(d,y)=>G(e,d,y),onSearchChange:d=>e.configSearchQuery=d,onSectionChange:d=>{e.configActiveSection=d,e.configActiveSubsection=null},onSubsectionChange:d=>e.configActiveSubsection=d,onReload:()=>ge(e),onSave:()=>fn(e),onApply:()=>Zr(e),onUpdate:()=>Xr(e)}):g}

        ${e.tab==="debug"?Jh({loading:e.debugLoading,status:e.debugStatus,health:e.debugHealth,models:e.debugModels,heartbeat:e.debugHeartbeat,eventLog:e.eventLog,callMethod:e.debugCallMethod,callParams:e.debugCallParams,callResult:e.debugCallResult,callError:e.debugCallError,onCallMethodChange:d=>e.debugCallMethod=d,onCallParamsChange:d=>e.debugCallParams=d,onRefresh:()=>Ln(e),onCall:()=>bc(e)}):g}

        ${e.tab==="logs"?av({loading:e.logsLoading,error:e.logsError,file:e.logsFile,entries:e.logsEntries,filterText:e.logsFilterText,levelFilters:e.logsLevelFilters,autoFollow:e.logsAutoFollow,truncated:e.logsTruncated,onFilterTextChange:d=>e.logsFilterText=d,onLevelToggle:(d,y)=>{e.logsLevelFilters={...e.logsLevelFilters,[d]:y}},onToggleAutoFollow:d=>e.logsAutoFollow=d,onRefresh:()=>ns(e,{reset:!0}),onExport:(d,y)=>e.exportLogs(d,y),onScroll:d=>e.handleLogsScroll(d)}):g}
      </main>
      ${Xh(e)}
      ${ev(e)}
    </div>
  `}var Yv=Object.defineProperty,Qv=Object.getOwnPropertyDescriptor,w=(e,t,n,i)=>{for(var s=i>1?void 0:i?Qv(t,n):t,a=e.length-1,o;a>=0;a--)(o=e[a])&&(s=(i?o(t,n,s):o(s))||s);return i&&s&&Yv(t,n,s),s};const Ai=Eu();function Jv(){if(!window.location.search)return!1;const t=new URLSearchParams(window.location.search).get("onboarding");if(!t)return!1;const n=t.trim().toLowerCase();return n==="1"||n==="true"||n==="yes"||n==="on"}let $=class extends ct{constructor(){super(...arguments),this.settings=Td(),this.password="",this.tab="chat",this.onboarding=Jv(),this.connected=!1,this.theme=this.settings.theme??"system",this.themeResolved="dark",this.hello=null,this.lastError=null,this.eventLog=[],this.eventLogBuffer=[],this.toolStreamSyncTimer=null,this.sidebarCloseTimer=null,this.assistantName=Ai.name,this.assistantAvatar=Ai.avatar,this.assistantAgentId=Ai.agentId??null,this.sessionKey=this.settings.sessionKey,this.chatLoading=!1,this.chatSending=!1,this.chatMessage="",this.chatMessages=[],this.chatToolMessages=[],this.chatStream=null,this.chatStreamStartedAt=null,this.chatRunId=null,this.compactionStatus=null,this.chatAvatarUrl=null,this.chatThinkingLevel=null,this.chatQueue=[],this.chatAttachments=[],this.sidebarOpen=!1,this.sidebarContent=null,this.sidebarError=null,this.splitRatio=this.settings.splitRatio,this.nodesLoading=!1,this.nodes=[],this.devicesLoading=!1,this.devicesError=null,this.devicesList=null,this.execApprovalsLoading=!1,this.execApprovalsSaving=!1,this.execApprovalsDirty=!1,this.execApprovalsSnapshot=null,this.execApprovalsForm=null,this.execApprovalsSelectedAgent=null,this.execApprovalsTarget="gateway",this.execApprovalsTargetNodeId=null,this.execApprovalQueue=[],this.execApprovalBusy=!1,this.execApprovalError=null,this.pendingGatewayUrl=null,this.configLoading=!1,this.configRaw=`{
}
`,this.configRawOriginal="",this.configValid=null,this.configIssues=[],this.configSaving=!1,this.configApplying=!1,this.updateRunning=!1,this.applySessionKey=this.settings.lastActiveSessionKey,this.configSnapshot=null,this.configSchema=null,this.configSchemaVersion=null,this.configSchemaLoading=!1,this.configUiHints={},this.configForm=null,this.configFormOriginal=null,this.configFormDirty=!1,this.configFormMode="form",this.configSearchQuery="",this.configActiveSection=null,this.configActiveSubsection=null,this.channelsLoading=!1,this.channelsSnapshot=null,this.channelsError=null,this.channelsLastSuccess=null,this.whatsappLoginMessage=null,this.whatsappLoginQrDataUrl=null,this.whatsappLoginConnected=null,this.whatsappBusy=!1,this.nostrProfileFormState=null,this.nostrProfileAccountId=null,this.presenceLoading=!1,this.presenceEntries=[],this.presenceError=null,this.presenceStatus=null,this.agentsLoading=!1,this.agentsList=null,this.agentsError=null,this.agentsSelectedId=null,this.agentsPanel="overview",this.agentFilesLoading=!1,this.agentFilesError=null,this.agentFilesList=null,this.agentFileContents={},this.agentFileDrafts={},this.agentFileActive=null,this.agentFileSaving=!1,this.agentIdentityLoading=!1,this.agentIdentityError=null,this.agentIdentityById={},this.agentSkillsLoading=!1,this.agentSkillsError=null,this.agentSkillsReport=null,this.agentSkillsAgentId=null,this.sessionsLoading=!1,this.sessionsResult=null,this.sessionsError=null,this.sessionsFilterActive="",this.sessionsFilterLimit="120",this.sessionsIncludeGlobal=!0,this.sessionsIncludeUnknown=!1,this.cronLoading=!1,this.cronJobs=[],this.cronStatus=null,this.cronError=null,this.cronForm={...xu},this.cronRunsJobId=null,this.cronRuns=[],this.cronBusy=!1,this.skillsLoading=!1,this.skillsReport=null,this.skillsError=null,this.skillsFilter="",this.skillEdits={},this.skillsBusyKey=null,this.skillMessages={},this.debugLoading=!1,this.debugStatus=null,this.debugHealth=null,this.debugModels=[],this.debugHeartbeat=null,this.debugCallMethod="",this.debugCallParams="{}",this.debugCallResult=null,this.debugCallError=null,this.logsLoading=!1,this.logsError=null,this.logsFile=null,this.logsEntries=[],this.logsFilterText="",this.logsLevelFilters={...Au},this.logsAutoFollow=!0,this.logsTruncated=!1,this.logsCursor=null,this.logsLastFetchAt=null,this.logsLimit=500,this.logsMaxBytes=25e4,this.logsAtBottom=!0,this.client=null,this.chatScrollFrame=null,this.chatScrollTimeout=null,this.chatHasAutoScrolled=!1,this.chatUserNearBottom=!0,this.chatNewMessagesBelow=!1,this.nodesPollInterval=null,this.logsPollInterval=null,this.debugPollInterval=null,this.logsScrollFrame=null,this.toolStreamById=new Map,this.toolStreamOrder=[],this.refreshSessionsAfterChat=new Set,this.basePath="",this.popStateHandler=()=>jd(this),this.themeMedia=null,this.themeMediaHandler=null,this.topbarObserver=null}createRenderRoot(){return this}connectedCallback(){super.connectedCallback(),Uu(this)}firstUpdated(){Ku(this)}disconnectedCallback(){zu(this),super.disconnectedCallback()}updated(e){Hu(this,e)}connect(){El(this)}handleChatScroll(e){hc(this,e)}handleLogsScroll(e){vc(this,e)}exportLogs(e,t){mc(e,t)}resetToolStream(){Nn(this)}resetChatScroll(){ma(this)}scrollToBottom(){ma(this),Kt(this,!0)}async loadAssistantIdentity(){await _l(this)}applySettings(e){Pe(this,e)}setTab(e){Dd(this,e)}setTheme(e,t){Od(this,e,t)}async loadOverview(){await yl(this)}async loadCron(){await wn(this)}async handleAbortChat(){await kl(this)}removeQueuedMessage(e){yu(this,e)}async handleSendChat(e,t){await bu(this,e,t)}async handleWhatsAppStart(e){await ic(this,e)}async handleWhatsAppWait(){await sc(this)}async handleWhatsAppLogout(){await ac(this)}async handleChannelConfigSave(){await oc(this)}async handleChannelConfigReload(){await lc(this)}handleNostrProfileEdit(e,t){cc(this,e,t)}handleNostrProfileCancel(){dc(this)}handleNostrProfileFieldChange(e,t){uc(this,e,t)}async handleNostrProfileSave(){await pc(this)}async handleNostrProfileImport(){await gc(this)}handleNostrProfileToggleAdvanced(){fc(this)}async handleExecApprovalDecision(e){const t=this.execApprovalQueue[0];if(!(!t||!this.client||this.execApprovalBusy)){this.execApprovalBusy=!0,this.execApprovalError=null;try{await this.client.request("exec.approval.resolve",{id:t.id,decision:e}),this.execApprovalQueue=this.execApprovalQueue.filter(n=>n.id!==t.id)}catch(n){this.execApprovalError=`Exec approval failed: ${String(n)}`}finally{this.execApprovalBusy=!1}}}handleGatewayUrlConfirm(){const e=this.pendingGatewayUrl;e&&(this.pendingGatewayUrl=null,Pe(this,{...this.settings,gatewayUrl:e}),this.connect())}handleGatewayUrlCancel(){this.pendingGatewayUrl=null}handleOpenSidebar(e){this.sidebarCloseTimer!=null&&(window.clearTimeout(this.sidebarCloseTimer),this.sidebarCloseTimer=null),this.sidebarContent=e,this.sidebarError=null,this.sidebarOpen=!0}handleCloseSidebar(){this.sidebarOpen=!1,this.sidebarCloseTimer!=null&&window.clearTimeout(this.sidebarCloseTimer),this.sidebarCloseTimer=window.setTimeout(()=>{this.sidebarOpen||(this.sidebarContent=null,this.sidebarError=null,this.sidebarCloseTimer=null)},200)}handleSplitRatioChange(e){const t=Math.max(.4,Math.min(.7,e));this.splitRatio=t,this.applySettings({...this.settings,splitRatio:t})}render(){return Vv(this)}};w([k()],$.prototype,"settings",2);w([k()],$.prototype,"password",2);w([k()],$.prototype,"tab",2);w([k()],$.prototype,"onboarding",2);w([k()],$.prototype,"connected",2);w([k()],$.prototype,"theme",2);w([k()],$.prototype,"themeResolved",2);w([k()],$.prototype,"hello",2);w([k()],$.prototype,"lastError",2);w([k()],$.prototype,"eventLog",2);w([k()],$.prototype,"assistantName",2);w([k()],$.prototype,"assistantAvatar",2);w([k()],$.prototype,"assistantAgentId",2);w([k()],$.prototype,"sessionKey",2);w([k()],$.prototype,"chatLoading",2);w([k()],$.prototype,"chatSending",2);w([k()],$.prototype,"chatMessage",2);w([k()],$.prototype,"chatMessages",2);w([k()],$.prototype,"chatToolMessages",2);w([k()],$.prototype,"chatStream",2);w([k()],$.prototype,"chatStreamStartedAt",2);w([k()],$.prototype,"chatRunId",2);w([k()],$.prototype,"compactionStatus",2);w([k()],$.prototype,"chatAvatarUrl",2);w([k()],$.prototype,"chatThinkingLevel",2);w([k()],$.prototype,"chatQueue",2);w([k()],$.prototype,"chatAttachments",2);w([k()],$.prototype,"sidebarOpen",2);w([k()],$.prototype,"sidebarContent",2);w([k()],$.prototype,"sidebarError",2);w([k()],$.prototype,"splitRatio",2);w([k()],$.prototype,"nodesLoading",2);w([k()],$.prototype,"nodes",2);w([k()],$.prototype,"devicesLoading",2);w([k()],$.prototype,"devicesError",2);w([k()],$.prototype,"devicesList",2);w([k()],$.prototype,"execApprovalsLoading",2);w([k()],$.prototype,"execApprovalsSaving",2);w([k()],$.prototype,"execApprovalsDirty",2);w([k()],$.prototype,"execApprovalsSnapshot",2);w([k()],$.prototype,"execApprovalsForm",2);w([k()],$.prototype,"execApprovalsSelectedAgent",2);w([k()],$.prototype,"execApprovalsTarget",2);w([k()],$.prototype,"execApprovalsTargetNodeId",2);w([k()],$.prototype,"execApprovalQueue",2);w([k()],$.prototype,"execApprovalBusy",2);w([k()],$.prototype,"execApprovalError",2);w([k()],$.prototype,"pendingGatewayUrl",2);w([k()],$.prototype,"configLoading",2);w([k()],$.prototype,"configRaw",2);w([k()],$.prototype,"configRawOriginal",2);w([k()],$.prototype,"configValid",2);w([k()],$.prototype,"configIssues",2);w([k()],$.prototype,"configSaving",2);w([k()],$.prototype,"configApplying",2);w([k()],$.prototype,"updateRunning",2);w([k()],$.prototype,"applySessionKey",2);w([k()],$.prototype,"configSnapshot",2);w([k()],$.prototype,"configSchema",2);w([k()],$.prototype,"configSchemaVersion",2);w([k()],$.prototype,"configSchemaLoading",2);w([k()],$.prototype,"configUiHints",2);w([k()],$.prototype,"configForm",2);w([k()],$.prototype,"configFormOriginal",2);w([k()],$.prototype,"configFormDirty",2);w([k()],$.prototype,"configFormMode",2);w([k()],$.prototype,"configSearchQuery",2);w([k()],$.prototype,"configActiveSection",2);w([k()],$.prototype,"configActiveSubsection",2);w([k()],$.prototype,"channelsLoading",2);w([k()],$.prototype,"channelsSnapshot",2);w([k()],$.prototype,"channelsError",2);w([k()],$.prototype,"channelsLastSuccess",2);w([k()],$.prototype,"whatsappLoginMessage",2);w([k()],$.prototype,"whatsappLoginQrDataUrl",2);w([k()],$.prototype,"whatsappLoginConnected",2);w([k()],$.prototype,"whatsappBusy",2);w([k()],$.prototype,"nostrProfileFormState",2);w([k()],$.prototype,"nostrProfileAccountId",2);w([k()],$.prototype,"presenceLoading",2);w([k()],$.prototype,"presenceEntries",2);w([k()],$.prototype,"presenceError",2);w([k()],$.prototype,"presenceStatus",2);w([k()],$.prototype,"agentsLoading",2);w([k()],$.prototype,"agentsList",2);w([k()],$.prototype,"agentsError",2);w([k()],$.prototype,"agentsSelectedId",2);w([k()],$.prototype,"agentsPanel",2);w([k()],$.prototype,"agentFilesLoading",2);w([k()],$.prototype,"agentFilesError",2);w([k()],$.prototype,"agentFilesList",2);w([k()],$.prototype,"agentFileContents",2);w([k()],$.prototype,"agentFileDrafts",2);w([k()],$.prototype,"agentFileActive",2);w([k()],$.prototype,"agentFileSaving",2);w([k()],$.prototype,"agentIdentityLoading",2);w([k()],$.prototype,"agentIdentityError",2);w([k()],$.prototype,"agentIdentityById",2);w([k()],$.prototype,"agentSkillsLoading",2);w([k()],$.prototype,"agentSkillsError",2);w([k()],$.prototype,"agentSkillsReport",2);w([k()],$.prototype,"agentSkillsAgentId",2);w([k()],$.prototype,"sessionsLoading",2);w([k()],$.prototype,"sessionsResult",2);w([k()],$.prototype,"sessionsError",2);w([k()],$.prototype,"sessionsFilterActive",2);w([k()],$.prototype,"sessionsFilterLimit",2);w([k()],$.prototype,"sessionsIncludeGlobal",2);w([k()],$.prototype,"sessionsIncludeUnknown",2);w([k()],$.prototype,"cronLoading",2);w([k()],$.prototype,"cronJobs",2);w([k()],$.prototype,"cronStatus",2);w([k()],$.prototype,"cronError",2);w([k()],$.prototype,"cronForm",2);w([k()],$.prototype,"cronRunsJobId",2);w([k()],$.prototype,"cronRuns",2);w([k()],$.prototype,"cronBusy",2);w([k()],$.prototype,"skillsLoading",2);w([k()],$.prototype,"skillsReport",2);w([k()],$.prototype,"skillsError",2);w([k()],$.prototype,"skillsFilter",2);w([k()],$.prototype,"skillEdits",2);w([k()],$.prototype,"skillsBusyKey",2);w([k()],$.prototype,"skillMessages",2);w([k()],$.prototype,"debugLoading",2);w([k()],$.prototype,"debugStatus",2);w([k()],$.prototype,"debugHealth",2);w([k()],$.prototype,"debugModels",2);w([k()],$.prototype,"debugHeartbeat",2);w([k()],$.prototype,"debugCallMethod",2);w([k()],$.prototype,"debugCallParams",2);w([k()],$.prototype,"debugCallResult",2);w([k()],$.prototype,"debugCallError",2);w([k()],$.prototype,"logsLoading",2);w([k()],$.prototype,"logsError",2);w([k()],$.prototype,"logsFile",2);w([k()],$.prototype,"logsEntries",2);w([k()],$.prototype,"logsFilterText",2);w([k()],$.prototype,"logsLevelFilters",2);w([k()],$.prototype,"logsAutoFollow",2);w([k()],$.prototype,"logsTruncated",2);w([k()],$.prototype,"logsCursor",2);w([k()],$.prototype,"logsLastFetchAt",2);w([k()],$.prototype,"logsLimit",2);w([k()],$.prototype,"logsMaxBytes",2);w([k()],$.prototype,"logsAtBottom",2);w([k()],$.prototype,"chatNewMessagesBelow",2);$=w([Po("openclaw-app")],$);
//# sourceMappingURL=index-rsvqOgBU.js.map
