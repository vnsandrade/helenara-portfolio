#!/usr/bin/env python3
"""Gera o site público do portfólio de Helenara Andrade a partir do Database.

Uso:
  python3 tools/build.py --db DIR_DO_SNAPSHOT --media DIR_DAS_FOTOS --out docs [--artifact]

--db     pasta com o snapshot do Database (subpastas obras/, novas/, edicoes/, fotos/, site/,
         cada uma com um JSON por documento). Fica FORA do repositório: contém preço, notas e local.
--media  pasta com as fotos de origem, uma por chave: <chave>.jpg
         (chaves das obras antigas: "01".."33", "f01".."f24", "26-b"; das novas: id do asset)
--out    pasta de saída do site (docs/ no repositório publicado pelo GitHub Pages)

Só sai do Database o que é público: título, ano, série, técnica, materiais, medidas, fotos
e se a obra foi vendida. Preço, notas e local nunca são escritos no site.
"""
import argparse, glob, html, json, os, re, unicodedata
from PIL import Image, ImageOps

ARTISTA = {
    "nome": "Helenara Andrade",
    "local": "Curitiba, Brasil",
    "whats": "5541991652920",
    "fone": "+55 41 99165 2920",
    "email": "helenara3@gmail.com",
    "insta": "helenarandrade",
}
STATEMENT = [
    "Meu trabalho artístico é impulsionado pela investigação das inúmeras possibilidades da tinta. "
    "Desenvolvo minhas próprias tintas e materiais pictóricos, explorando diferentes formulações, e trabalho com "
    "camadas sucessivas, diluições calculadas e cores em constante contraste, buscando criar um diálogo entre o caos e a harmonia.",
    "Espátulas de diferentes tamanhos são minhas ferramentas principais, utilizadas tanto para gerar transições sutis "
    "quanto para formar bordas duras e arestas cortantes que emergem da superfície com intensidade. O resultado são "
    "superfícies expressivas, nas quais o movimento da tinta materializa conflitos e resoluções internas.",
]
CV = [
    ("Formação", [
        "Design de Interiores, Universidade Positivo, Curitiba/PR (2016)",
        "Arte e Mercado, Escola Nano de Art Market (em andamento)",
        "Processo Criativo, com Juliana dos Santos, Instituto Tomie Ohtake",
        "Mentoria Negócios de Arte, Adriana Braga",
    ]),
    ("Exposições individuais", [
        "2025 · Strata, curadoria de João Paulo Carvalho, Curitiba/PR",
        "2023 · Rastros, curadoria de João Paulo Carvalho, Curitiba/PR",
    ]),
    ("Exposições coletivas", [
        "2026 · Beyond Translations, Saphira & Ventura Gallery, Nova York/EUA",
        "2024 · Diálogos para o Planeta G20, Parque Maria da Glória, Rio de Janeiro/RJ",
        "2024 · Empower Her Art Forum, Museu da Civilização Egípcia, Cairo/Egito",
        "2024 · When Art Meets Carnival, Saphira & Ventura Gallery e Espaço BB, Rio de Janeiro/RJ",
        "2023 · Miami Art Week, Saphira & Ventura Gallery, Miami/EUA",
        "2023 · Revival, Saphira & Ventura Gallery, Nova York/EUA",
    ]),
    ("Seleções", ["2022 · 5º Salão de Artes de Pinhais, Pinhais/PR"]),
]
TEC_PUBLICA = {"Acrílica sobre tela": "Acrílica sobre tela", "Tinta Acrílica": "Acrílica sobre tela",
               "Tinta Óleo": "Óleo sobre tela", "Técnica mista": "Técnica mista", "Colagem": "Colagem"}

e = lambda s: html.escape(str(s or ""), quote=True)
fmt = lambda x: (("%g" % float(x)).replace(".", ","))


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "obra"


def load_col(db, name):
    out = {}
    for f in glob.glob(os.path.join(db, name, "*.json")):
        d = json.load(open(f, encoding="utf-8"))
        out[os.path.basename(f)[:-5]] = d.get("data", d) if isinstance(d, dict) else d
    return out


def montar_obras(base, db):
    obras, novas, edic, fotos, site = (load_col(db, n) for n in ("obras", "novas", "edicoes", "fotos", "site"))
    W = []
    for b in base:
        w = dict(b, foto=b["img"], detalhes=["26-b"] if b["id"] == "o26" else [], criado="")
        ed = edic.get(w["id"], {})
        if ed.get("removida"):
            continue
        for k in ("t", "a", "s", "tec", "mat"):
            if ed.get(k) is not None:
                w[k] = str(ed[k])
        if ed.get("alt") and ed.get("larg"):
            w["alt"], w["larg"] = float(ed["alt"]), float(ed["larg"])
            w["dim"] = f'{fmt(ed["alt"])} x {fmt(ed["larg"])}' + (" (cada)" if w["q"] > 1 else "")
        if ed.get("foto"):
            w["foto"] = ed["foto"]
        W.append(w)
    for doc_id, n in sorted(novas.items(), key=lambda kv: str(kv[1].get("criado", ""))):
        W.append({"id": "n_" + doc_id, "ord": 1000, "t": n.get("t") or "Sem título", "a": str(n.get("a") or ""),
                  "s": n.get("s") or "", "tec": n.get("tec") or "", "mat": n.get("mat") or "",
                  "dim": f'{fmt(n["alt"])} x {fmt(n["larg"])}', "q": 1, "foto": n["foto"], "detalhes": [], "alt": float(n["alt"]), "larg": float(n["larg"]),
                  "criado": n.get("criado", "")})
    out = []
    for w in W:
        if site.get(w["id"], {}).get("visivel") is False:
            continue
        w["detalhes"] = w["detalhes"] + [x["id"] for x in fotos.get(w["id"], {}).get("lista", [])]
        w["vendida"] = obras.get(w["id"], {}).get("status") == "Vendida"
        w["tec"] = TEC_PUBLICA.get(w["tec"], w["tec"])
        out.append(w)
    out.sort(key=lambda w: (-(int(w["a"]) if w["a"].isdigit() else 0), w["ord"], w["criado"]))
    usados = set()
    for w in out:
        s = slug(w["t"] + (" " + w["a"] if w["a"] else ""))
        while s in usados:
            s += "-2"
        usados.add(s)
        w["slug"] = s
    return out


def gerar_imagens(keys, media, out):
    os.makedirs(os.path.join(out, "img"), exist_ok=True)
    tamanhos = {}
    for k in keys:
        dst, dst_t = os.path.join(out, "img", k + ".jpg"), os.path.join(out, "img", k + "-t.jpg")
        if not (os.path.exists(dst) and os.path.exists(dst_t)):
            src = next((p for p in (os.path.join(media, k + x) for x in (".jpg", ".jpeg", ".png")) if os.path.exists(p)), None)
            if not src:
                raise SystemExit(f"Foto não encontrada para a chave {k} em {media}")
            im = ImageOps.exif_transpose(Image.open(src))
            if im.mode != "RGB":
                bg = Image.new("RGB", im.size, (255, 255, 255))
                bg.paste(im, mask=im.convert("RGBA").split()[3]) if im.mode in ("RGBA", "LA", "P") else bg.paste(im)
                im = bg
            a = im.copy(); a.thumbnail((1800, 1800), Image.LANCZOS); a.save(dst, quality=84, optimize=True, progressive=True)
            b = im.copy(); b.thumbnail((720, 1200), Image.LANCZOS); b.save(dst_t, quality=80, optimize=True, progressive=True)
        with Image.open(dst_t) as t:
            tamanhos[k] = t.size
    return tamanhos


CSS = """
:root{--bg:#FFFFFF;--ink:#1F1D1B;--muted:#77726C;--card:#F4F3F1;--pill:#F1F0EE;--line:#E6E4E1;--sold:#A8473B;
--fd:"Clash Grotesk","Helvetica Neue",Helvetica,Arial,sans-serif;--fb:"Satoshi","Helvetica Neue",Helvetica,Arial,sans-serif;
--ease:cubic-bezier(.16,1,.3,1);--side:288px;color-scheme:light}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--fb);font-size:16px;line-height:1.6;-webkit-font-smoothing:antialiased}
a{color:inherit}
img{max-width:100%;display:block}
h1,h2,h3{font-family:var(--fd);font-weight:500;letter-spacing:-.025em;line-height:1.05;margin:0;text-wrap:balance}
.pill{display:inline-flex;align-items:center;justify-content:center;gap:8px;border-radius:0;padding:10px 20px;font:500 14px/1.25 var(--fb);
 text-decoration:none;border:1px solid rgba(31,29,27,.18);background:#fff;color:var(--ink);cursor:pointer;transition:background-color .2s,opacity .2s}
.pill:hover,.pill[aria-current="page"],.pill[aria-pressed="true"]{background:var(--pill)}
.pill.dark{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.pill.dark:hover{opacity:.85}
.ico{width:40px;height:40px;padding:0;border:0;background:var(--pill)}
.ico svg{width:17px;height:17px}
/* barra lateral */
.side{position:fixed;inset:0 auto 0 0;width:var(--side);display:flex;flex-direction:column;padding:40px 32px;z-index:20;background:var(--bg);overflow-y:auto;scrollbar-width:none}
.side .bottom{padding-top:32px}
.brand{text-decoration:none;display:block}
.brand b{display:block;font-family:var(--fd);font-weight:500;font-size:46px;line-height:.98;letter-spacing:-.035em}
.brand span{display:block;margin-top:10px;font-size:14px;color:var(--muted)}
.side nav{display:flex;flex-direction:column;align-items:flex-start;gap:10px;margin-top:48px}
.dd{width:100%;max-width:224px}
.dd summary{list-style:none;user-select:none;position:relative;z-index:1}
.dd summary::-webkit-details-marker{display:none}
.dd[open] summary{border-bottom-color:#fff;background:#fff}
.chev{width:12px;height:12px;transition:transform .35s var(--ease)}
.dd[open] .chev{transform:rotate(180deg)}
.ddp{display:flex;flex-direction:column;margin-top:-1px;border:1px solid rgba(31,29,27,.18);background:#fff;animation:dd .35s var(--ease)}
.ddp>*{border-top:1px solid var(--line)}
.ddp>*:first-child{border-top:0}
.ddp a{display:flex;justify-content:space-between;align-items:baseline;gap:12px;padding:11px 16px;font-size:14px;text-decoration:none;color:var(--ink);transition:background-color .2s,color .2s}
.ddp a.ser{padding-left:30px;color:#4a4642}
.ddp a small{font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums}
.ddp a:hover{background:var(--card);color:var(--ink)}
.ddp a[aria-current="page"]{background:var(--ink);color:#fff}
.ddp a[aria-current="page"] small{color:rgba(255,255,255,.65)}
.ddp .lbl{display:block;padding:14px 16px 8px;font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
@keyframes dd{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:none}}
.shead{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.4fr);gap:24px 48px;align-items:end;padding-bottom:28px;margin-bottom:32px;border-bottom:1px solid var(--line)}
.shead h1{font-size:clamp(34px,4vw,56px)}
.shead .n{font-size:14px;color:var(--muted);margin-top:10px}
.shead p.txt{margin:0;font-size:16.5px;line-height:1.65;color:#46423e;max-width:60ch}
.side .bottom{margin-top:auto;display:flex;flex-direction:column;gap:22px}
.side .row{display:flex;gap:10px;align-items:center}
.copy{font-size:12px;color:var(--muted)}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
.pill svg{width:16px;height:16px}
.mtop{display:none}
.main{margin-left:var(--side);padding:40px clamp(20px,3vw,40px) 64px 0;min-height:100vh}
/* grade de obras */
.filters{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:24px}
.filters .pill{padding:8px 16px;font-size:13px}
.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:36px 24px}
.item[hidden]{display:none}
.item{display:block;text-decoration:none;opacity:0;animation:up .7s var(--ease) forwards}
.frame{position:relative;overflow:hidden;border-radius:0;background:var(--card);aspect-ratio:4/5;transition:transform .6s var(--ease),box-shadow .6s var(--ease)}
.frame img{width:100%;height:100%;object-fit:cover;transition:transform .8s var(--ease),filter .8s var(--ease),opacity .6s var(--ease)}
.item:hover .frame{transform:translateY(-6px);box-shadow:0 24px 48px -16px rgba(0,0,0,.14)}
.item:hover .frame img{transform:scale(1.06)}
.meta{display:flex;justify-content:space-between;gap:12px;margin-top:14px;font-size:14px}
.meta .t{font-weight:500}
.meta .d{color:var(--muted);text-align:right;white-space:nowrap}
.sold{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:var(--muted)}
.sold::before{content:"";width:7px;height:7px;border-radius:0;background:var(--sold)}
.rv{filter:blur(20px);opacity:0;transform:scale(1.05)}
.rv.ok{filter:none;opacity:1;transform:none}
@keyframes up{from{opacity:0;transform:translateY(24px)}to{opacity:1;transform:none}}
/* página da obra */
.modes{display:flex;gap:8px;margin-bottom:16px}
.stage{border-radius:0;background:var(--bg);overflow:hidden}
.view img{width:auto;max-width:100%;height:auto;max-height:82vh;object-fit:contain;cursor:zoom-in;margin:0}
.wall[hidden],.view[hidden],.thumbs[hidden],.zoomcap[hidden],.wallcap[hidden]{display:none}
.wall svg{width:100%;height:auto;max-height:82vh;display:block}
.thumbs{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}
.thumbs button{padding:0;border:2px solid transparent;border-radius:0;overflow:hidden;background:none;cursor:pointer}
.thumbs button[aria-current="true"]{border-color:var(--ink)}
.thumbs img{width:72px;height:72px;object-fit:cover}
.cap{font-size:13px;color:var(--muted);margin:10px 0 0}
.obra{display:grid;grid-template-columns:minmax(0,1fr) minmax(260px,320px);gap:clamp(28px,3.5vw,56px);align-items:start}
.obra-txt{position:sticky;top:40px;display:flex;flex-direction:column;gap:22px;padding-top:56px}
.obra-txt .serie{margin-top:10px}
.obra-txt .serie a{text-decoration:none;border-bottom:1px solid var(--line)}
.ficha{border-top:1px solid var(--line);padding-top:18px}
.obra-txt h1{font-size:clamp(30px,2.8vw,42px)}
.obra-txt .serie{margin-top:14px;color:var(--muted)}
.ficha{margin:0;display:grid;gap:4px;font-size:14px;color:var(--muted)}
.ficha dd{margin:0}
.ficha .k{display:none}
.cta{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
.pn{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;border-top:1px solid var(--line);margin-top:56px;padding-top:32px}
/* sobre */
.sobre{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:clamp(28px,4vw,56px);align-items:start}
.sobre figure{margin:0;position:sticky;top:40px}
.sobre img{width:100%;aspect-ratio:3/4;object-fit:cover;object-position:50% 35%;border-radius:0}
.sobre h1{font-size:clamp(34px,3.6vw,48px)}
.sobre .sub{color:var(--muted);margin:8px 0 0;padding-bottom:24px;border-bottom:1px solid var(--line)}
.sobre .txt>p{margin:22px 0 0;color:#46423e;font-size:15.5px}
.cv{display:grid;gap:26px;margin-top:36px;border-top:1px solid var(--line);padding-top:30px}
.cv h3{font:500 12px/1.3 var(--fb);letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin-bottom:10px}
.cv ul{list-style:none;margin:0;padding:0;display:grid;gap:6px;font-size:14.5px}
.contatos{display:flex;flex-wrap:wrap;gap:10px;margin-top:30px}
/* zoom */
#lb{position:fixed;inset:0;background:rgba(20,18,16,.96);display:none;z-index:50;overflow:hidden;touch-action:none}
#lb.on{display:flex;align-items:center;justify-content:center}
#lb img{max-width:92vw;max-height:90vh;object-fit:contain;transform-origin:center;cursor:zoom-in;user-select:none}
#lb.z img{cursor:grab}
#lb button{position:absolute;top:16px;right:16px;width:44px;height:44px;border-radius:0;border:0;background:rgba(255,255,255,.15);color:#fff;font-size:22px;cursor:pointer}
/* celular */
@media (max-width:900px){
 .side{inset:0;width:auto;padding:84px 20px 28px;opacity:0;visibility:hidden;transition:opacity .35s var(--ease),visibility .35s}
 body.menu-on{overflow:hidden}
 body.menu-on .side{opacity:1;visibility:visible}
 .side .brand{display:none}
 .side nav{margin-top:12px}
 .dd{max-width:none}
 .ddp a{font-size:16px;padding:13px 16px}
 .ddp a.ser{padding-left:30px}
 .shead{grid-template-columns:1fr}
 .filters{flex-wrap:nowrap;overflow-x:auto;margin-inline:-20px;padding-inline:20px;scrollbar-width:none}.filters::-webkit-scrollbar{display:none}.filters .pill{flex:none}.side nav .pill{font-size:18px;padding:12px 24px}
 .mtop{display:flex;position:sticky;top:0;z-index:30;justify-content:space-between;align-items:center;padding:16px 20px;background:var(--bg)}
 .mtop a{font-family:var(--fd);font-weight:500;font-size:22px;letter-spacing:-.02em;text-decoration:none}
 .main{margin:0;padding:8px 20px 56px}
 .grid{gap:32px 14px}
 .obra,.sobre{grid-template-columns:1fr}
 .obra-txt{position:static;padding-top:8px}
 .sobre figure{position:static}
}
@media (max-width:1180px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:560px){.grid{grid-template-columns:1fr}}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}.item{opacity:1}.rv{filter:none;opacity:1;transform:none}}

/* home: abertura e destaques */
.home .main{padding:0;margin-left:var(--side)}
.hero{position:relative;height:100vh;height:100svh;min-height:520px;overflow:hidden;background:#111;color:#fff}
.hero .sl{position:absolute;inset:0;opacity:0;transition:opacity 1.8s ease}
.hero .sl.on{opacity:1}
.hero .sl img{width:100%;height:100%;object-fit:cover;transform:scale(1.02)}
.hero .sl.on img{animation:kb 9s linear forwards}
@keyframes kb{from{transform:scale(1.02)}to{transform:scale(1.09)}}
.hero::after{content:"";position:absolute;inset:auto 0 0 0;height:42%;background:linear-gradient(transparent,rgba(0,0,0,.55));pointer-events:none}
.hcap{position:absolute;left:40px;right:40px;bottom:36px;z-index:2;display:flex;justify-content:space-between;align-items:flex-end;gap:24px}
.hcap .lg{font:500 12px/1.3 var(--fb);letter-spacing:.14em;text-transform:uppercase;opacity:.75;margin:0 0 8px}
.hcap .tt{font-family:var(--fd);font-weight:500;font-size:clamp(26px,3vw,40px);letter-spacing:-.02em;line-height:1.05;margin:0;color:#fff;text-decoration:none;display:block}
.hcap .tt[hidden]{display:none}
.hcap .tt span{display:block;font:400 14px/1.4 var(--fb);letter-spacing:0;opacity:.8;margin-top:6px}
.hctl{display:flex;align-items:center;gap:16px}
.dots{display:flex;gap:6px}
.dots button{width:22px;height:2px;padding:0;border:0;background:rgba(255,255,255,.35);cursor:pointer;position:relative;overflow:hidden}
.dots button.on::after{content:"";position:absolute;inset:0;background:#fff;transform-origin:left;animation:pg 7s linear forwards}
.hero.paused .dots button.on::after{animation-play-state:paused}
@keyframes pg{from{transform:scaleX(0)}to{transform:scaleX(1)}}
.pill.light{background:#fff;color:var(--ink);border-color:#fff}
.sec{padding:96px 40px 0}
.sec:last-child{padding-bottom:96px}
.eyebrow{font:500 12px/1.3 var(--fb);letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin:0 0 14px}
.feat{display:grid;grid-template-columns:minmax(300px,1fr) minmax(0,2fr);gap:48px;align-items:center}
.feat>div:first-child{position:relative;z-index:1;background:var(--bg)}
.feat h2{font-size:clamp(32px,3.2vw,48px);overflow-wrap:anywhere}
.feat p.txt{color:#46423e;font-size:16.5px;line-height:1.65;margin:18px 0 26px;max-width:46ch}
.strip{overflow:hidden;mask-image:linear-gradient(90deg,transparent,#000 6%,#000 94%,transparent)}
.track{display:flex;gap:20px;width:max-content;animation:mq 70s linear infinite}
.strip:hover .track{animation-play-state:paused}
@keyframes mq{to{transform:translateX(-50%)}}
.track a{display:block;text-decoration:none;width:clamp(200px,20vw,280px)}
.track .frame{aspect-ratio:4/5}
.track .meta{font-size:13px}
.shead2{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;margin-bottom:28px}
.shead2 h2{font-size:clamp(30px,3vw,44px)}
.sgrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:32px 24px}
.sc .frame{aspect-ratio:4/3}
.sc{text-decoration:none;display:block}
.sc b{display:block;font-weight:500;margin-top:12px}
.sc small{color:var(--muted);font-size:13px}
.teaser{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.2fr);gap:56px;align-items:center;border-top:1px solid var(--line);padding-top:72px}
.teaser img{width:100%;aspect-ratio:4/3;object-fit:cover;object-position:50% 30%}
.teaser h2{font-size:clamp(30px,3vw,44px)}
.teaser p{color:#46423e;font-size:16px;line-height:1.65;margin:18px 0 26px}
@media (max-width:900px){
 .home .main{margin:0}
 .hero{height:78svh}
 .hcap{left:20px;right:20px;bottom:22px;flex-direction:column;align-items:flex-start}
 .sec{padding:64px 20px 0}.sec:last-child{padding-bottom:64px}
 .feat,.teaser{grid-template-columns:1fr;gap:28px}
 .sgrid{grid-template-columns:repeat(2,minmax(0,1fr))}
}
@media (prefers-reduced-motion:reduce){.track{animation:none}.strip{overflow-x:auto}.hero .sl.on img{animation:none}}
"""

LB_JS = """
(()=>{const lb=document.getElementById('lb');if(!lb)return;const im=lb.querySelector('img');let s=1,x=0,y=0,d=null,m=false;
const ap=()=>{im.style.transform=`translate(${x}px,${y}px) scale(${s})`;lb.classList.toggle('z',s>1)};
const open=src=>{im.src=src;s=1;x=y=0;ap();lb.classList.add('on');document.body.style.overflow='hidden'};
const close=()=>{lb.classList.remove('on');document.body.style.overflow=''};
document.querySelectorAll('[data-zoom]').forEach(el=>el.addEventListener('click',()=>open(el.dataset.zoom||el.src)));
lb.querySelector('button').onclick=close;addEventListener('keydown',e=>{if(e.key==='Escape')close()});
im.addEventListener('pointerdown',e=>{d=[e.clientX,e.clientY];m=false;im.setPointerCapture(e.pointerId)});
im.addEventListener('pointermove',e=>{if(!d||s===1)return;const dx=e.clientX-d[0],dy=e.clientY-d[1];if(Math.abs(dx)+Math.abs(dy)>3)m=true;x+=dx;y+=dy;d=[e.clientX,e.clientY];ap()});
im.addEventListener('pointerup',e=>{d=null;if(m)return;if(s>1){s=1;x=y=0}else{const r=im.getBoundingClientRect();s=2.6;x=(r.left+r.width/2-e.clientX)*(s-1);y=(r.top+r.height/2-e.clientY)*(s-1)}ap()});
lb.addEventListener('click',e=>{if(e.target===lb)close()});
lb.addEventListener('wheel',e=>{e.preventDefault();s=Math.min(5,Math.max(1,s*Math.exp(-e.deltaY*.002)));if(s===1){x=y=0}ap()},{passive:false});
document.querySelectorAll('.thumbs button').forEach(b=>b.onclick=()=>{const v=document.querySelector('.view img');v.src=b.dataset.src;v.dataset.zoom=b.dataset.full;
 document.querySelectorAll('.thumbs button').forEach(o=>o.setAttribute('aria-current',o===b))});
})();
"""

MODES_JS = """
(()=>{const bs=[...document.querySelectorAll('.modes button')];if(!bs.length)return;
bs.forEach(b=>b.onclick=()=>{const p=b.dataset.m==='parede';bs.forEach(o=>o.setAttribute('aria-pressed',o===b));
document.querySelector('.wall').hidden=!p;document.querySelector('.view').hidden=p;
const t=document.querySelector('.thumbs');if(t)t.hidden=p;const c=document.querySelector('.zoomcap');if(c)c.hidden=p;const wc=document.querySelector('.wallcap');if(wc)wc.hidden=!p;})})();
"""
UI_JS = """
(()=>{document.querySelectorAll('img.rv').forEach(i=>{const f=()=>i.classList.add('ok');i.complete&&i.naturalWidth?f():i.addEventListener('load',f)});
const b=document.querySelector('.mbtn');if(b)b.onclick=()=>{const on=document.body.classList.toggle('menu-on');b.textContent=on?'Fechar':'Menu';b.setAttribute('aria-expanded',on)};})();
"""
HERO_JS = """
(()=>{const h=document.querySelector('.hero');if(!h)return;const S=[...h.querySelectorAll('.sl')],D=[...h.querySelectorAll('.dots button')],C=[...h.querySelectorAll('.hcap [data-i]')];
let i=0,t=null;const red=matchMedia('(prefers-reduced-motion: reduce)').matches;
const go=n=>{S[i].classList.remove('on');D[i].classList.remove('on');C[i].hidden=true;i=(n+S.length)%S.length;
 const im=S[i].querySelector('img');if(im.dataset.src){im.src=im.dataset.src;im.removeAttribute('data-src')}
 S[i].classList.add('on');void D[i].offsetWidth;D[i].classList.add('on');C[i].hidden=false;
 const nx=S[(i+1)%S.length].querySelector('img');if(nx.dataset.src){nx.src=nx.dataset.src;nx.removeAttribute('data-src')}};
const run=()=>{clearInterval(t);if(!red)t=setInterval(()=>go(i+1),7000)};
D.forEach((d,k)=>d.onclick=()=>{go(k);run()});
h.addEventListener('mouseenter',()=>{clearInterval(t);h.classList.add('paused')});h.addEventListener('mouseleave',()=>{h.classList.remove('paused');run()});
document.addEventListener('visibilitychange',()=>document.hidden?clearInterval(t):run());go(0);run();})();
"""
FILTER_JS = """
(()=>{const bs=[...document.querySelectorAll('.filters button')];bs.forEach(b=>b.onclick=()=>{const v=b.dataset.s;
bs.forEach(o=>o.setAttribute('aria-pressed',o===b));document.querySelectorAll('.grid .item').forEach(it=>{it.hidden=v!=='*'&&it.dataset.s!==v})});})();
"""


IC_WA = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 11.5a8 8 0 0 1-11.8 7L4 20l1.5-4.1A8 8 0 1 1 20 11.5z"/></svg>'
IC_IG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="3.5" y="3.5" width="17" height="17" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.3" cy="6.7" r="1" fill="currentColor" stroke="none"/></svg>'
IC_EM = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="3"/><path d="m4 7 8 6 8-6"/></svg>'


SERIES_NAV, SERIES_TXT = [], {}


def pagina(titulo, desc, corpo, rel, atual, artifact_index=False, og="", classe=""):
    head = (f'<title>{e(titulo)}</title>\n<meta name="description" content="{e(desc)}">\n'
            f'<meta property="og:title" content="{e(titulo)}">\n<meta property="og:description" content="{e(desc)}">\n'
            + (f'<meta property="og:image" content="{e(og)}">\n' if og else "")
            + '<meta name="theme-color" content="#FFFFFF">\n'
              '<link rel="preconnect" href="https://api.fontshare.com" crossorigin>\n'
              '<link rel="stylesheet" href="https://api.fontshare.com/v2/css?f[]=clash-grotesk@500,600&f[]=satoshi@400,500&display=swap">\n'
            + f'<link rel="stylesheet" href="{rel}estilo.css">\n')
    cur = lambda k: ' aria-current="page"' if atual == k else ""
    sub = "".join(f'<a class="ser" href="{rel}series/{sl}.html"{cur("s:" + sl)}><span>{e(n)}</span><small>{c}</small></a>' for n, sl, c in SERIES_NAV)
    aberto = " open" if atual == "obras" or atual.startswith("s:") else ""
    menu = (f'<details class="dd"{aberto}><summary class="pill">Obras'
            '<svg class="chev" viewBox="0 0 12 12" aria-hidden="true"><path d="M2.5 4.5 6 8l3.5-3.5" fill="none" stroke="currentColor" stroke-width="1.4"/></svg></summary>'
            f'<div class="ddp"><a class="top" href="{rel}obras.html"{cur("obras")}><span>Todas as obras</span><small>{sum(c for _, _, c in SERIES_NAV)}</small></a>'
            f'<span class="lbl">Séries</span>{sub}</div></details>'
            f'<a class="pill" href="{rel}sobre.html"{cur("sobre")}>Sobre</a>')
    wa = f'https://wa.me/{ARTISTA["whats"]}'
    side = (f'<aside class="side" id="menu"><a class="brand" href="{rel}index.html"><b>Helenara<br>Andrade</b><span>Artista visual · {e(ARTISTA["local"])}</span></a>'
            f'<nav aria-label="Menu">{menu}</nav>'
            f'<div class="bottom"><div class="row"><a class="pill" href="{wa}" target="_blank" rel="noopener">Fale comigo</a>'
            f'<a class="pill ico" href="https://instagram.com/{ARTISTA["insta"]}" target="_blank" rel="noopener" aria-label="Instagram @{e(ARTISTA["insta"])}">{IC_IG}</a>'
            f'<a class="pill ico" href="mailto:{e(ARTISTA["email"])}" aria-label="E-mail {e(ARTISTA["email"])}">{IC_EM}</a></div>'
            f'<div class="copy">© 2026 {e(ARTISTA["nome"])}</div></div></aside>')
    mtop = f'<div class="mtop"><a href="{rel}index.html">Helenara Andrade</a><button class="pill mbtn" aria-controls="menu" aria-expanded="false">Menu</button></div>'
    body = (mtop + side + f'<main class="main">{corpo}</main>'
            + f'<div id="lb" role="dialog" aria-label="Foto ampliada"><img alt=""><button aria-label="Fechar">×</button></div><script>{LB_JS}{MODES_JS}{UI_JS}{FILTER_JS}{HERO_JS}</script>')
    if artifact_index:  # página principal da prévia no Claude: o host envolve com o esqueleto HTML
        return head + f'<style>{CSS}</style>\n' + body
    return ('<!doctype html>\n<html lang="pt-BR"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n' + head + f'</head><body class="{classe}">' + body + '</body></html>')


# obras do catálogo/fora em que a artista passa na frente do quadro (ajustado à mão no Acervo)
PESSOA_FRENTE = {"o06", "o07", "o21", "o22", "o26", "o28", "o30", "o33", "x07", "x17", "x18", "x19"}


def parede(w, tam):
    """Simulação em escala na parede do ateliê (mesma régua do Acervo: 6,0935 px por cm)."""
    nums = [float(x.replace(",", ".")) for x in re.findall(r"[\d,]+", w["dim"])][:2]
    L, S = max(nums), min(nums)
    tw, th = tam.get(w["foto"], (1, 1))
    pw, ph = (L, S) if tw >= th else (S, L)
    if w.get("alt") and w.get("larg"):
        pw, ph = w["larg"], w["alt"]
    paineis = [w["foto"]] + (w["detalhes"][:1] if w["q"] > 1 else [])
    PX, CX, CY, gap = 6.0935, 574.5, 760.4, 8
    w2, h2, g2 = pw * PX, ph * PX, gap * PX
    tot = len(paineis) * w2 + (len(paineis) - 1) * g2
    x0, y0 = CX - tot / 2, CY - h2 / 2
    if w["id"].startswith("n_") or w.get("alt"):
        pessoa = CX + pw * PX / 2 >= 860 and ph >= 60
    else:
        pessoa = w["id"] in PESSOA_FRENTE
    imgs = "".join(f'<image href="../img/{k}.jpg" x="{x0 + i * (w2 + g2):.1f}" y="{y0:.1f}" width="{w2:.1f}" height="{h2:.1f}" preserveAspectRatio="none"/>'
                   for i, k in enumerate(paineis))
    return (f'<svg viewBox="0 150 1200 1600" preserveAspectRatio="xMidYMid meet" role="img" aria-label="{e(w["t"])} em escala na parede do ateliê">'
            '<defs><filter id="sh" x="-10%" y="-10%" width="125%" height="125%"><feDropShadow dx="6" dy="9" stdDeviation="9" flood-color="#000" flood-opacity=".26"/></filter></defs>'
            f'<image href="../img/{"parede.jpg" if pessoa else "parede-vazia.jpg"}" x="0" y="0" width="1200" height="1800"/>'
            f'<g filter="url(#sh)">{imgs}</g>'
            + ('<image href="../img/pessoa.png" x="629" y="545.1" width="461" height="1167"/>' if pessoa else "") + '</svg>')


def card(w, rel, tam, i=0):
    tw, th = tam.get(w["foto"], (720, 900))
    return (f'<a class="item" href="{rel}obras/{w["slug"]}.html" data-s="{e(w["s"] or "—")}" style="animation-delay:{min(i, 10) * 60}ms">'
            f'<div class="frame"><img class="rv" src="{rel}img/{w["foto"]}-t.jpg" width="{tw}" height="{th}" alt="{e(w["t"])}" loading="lazy"></div>'
            f'<div class="meta"><span><span class="t">{e(w["t"])}</span>{", " + e(w["a"]) if w["a"] else ""}'
            f'{"<br><span class=sold>Vendida</span>" if w["vendida"] else ""}</span><span class="d">{e(w["dim"])} cm</span></div></a>')


def build(args):
    base = json.load(open(args.base, encoding="utf-8"))
    W = montar_obras(base, args.db)
    keys = ["inicio"] + [w["foto"] for w in W] + [k for w in W for k in w["detalhes"]]
    if args.faltando:
        # lista as fotos que ainda precisam ser baixadas para --media (uma por linha)
        for k in dict.fromkeys(keys):
            pronto = all(os.path.exists(os.path.join(args.out, "img", k + x)) for x in (".jpg", "-t.jpg"))
            if not pronto and not any(os.path.exists(os.path.join(args.media, k + x)) for x in (".jpg", ".jpeg", ".png")):
                print(k)
        return
    tam = gerar_imagens(dict.fromkeys(keys), args.media, args.out)
    os.makedirs(os.path.join(args.out, "obras"), exist_ok=True)
    import shutil
    for f in ("parede.jpg", "parede-vazia.jpg", "pessoa.png"):
        shutil.copyfile(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "parede", f), os.path.join(args.out, "img", f))
    open(os.path.join(args.out, "estilo.css"), "w").write(CSS)
    nome = ARTISTA["nome"]
    global SERIES_NAV, SERIES_TXT
    SERIES_TXT = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "series.json")))
    SERIES_NAV = [(n, slug(n), sum(1 for w in W if w["s"] == n)) for n in sorted({w["s"] for w in W if w["s"]})] + [("Sem série", "sem-serie", sum(1 for w in W if not w["s"]))]
    corpo = (f'<h1 class="sr">Obras de {e(nome)}</h1>'
             f'<div class="grid">{"".join(card(w, "", tam, i) for i, w in enumerate(W))}</div>')
    open(os.path.join(args.out, "obras.html"), "w").write(pagina(f"Obras · {nome}", f"Todas as {len(W)} pinturas da artista visual {nome}.", corpo, "", "obras", og="img/inicio.jpg"))
    # páginas das séries
    os.makedirs(os.path.join(args.out, "series"), exist_ok=True)
    for f in glob.glob(os.path.join(args.out, "series", "*.html")):
        os.remove(f)
    for n, sl, _ in SERIES_NAV:
        ws = [w for w in W if (w["s"] or "") == ("" if sl == "sem-serie" else n)]
        txt = SERIES_TXT.get(n, "")
        corpo = (f'<header class="shead"><div><h1>{e(n)}</h1><p class="n">{len(ws)} obra{"s" if len(ws) != 1 else ""}</p></div>'
                 + (f'<p class="txt">{e(txt)}</p>' if txt else "<span></span>") + '</header>'
                 f'<div class="grid">{"".join(card(w, "../", tam, i) for i, w in enumerate(ws))}</div>')
        titulo = (f"Série {n}" if sl != "sem-serie" else "Obras sem série") + f" · {nome}"
        open(os.path.join(args.out, "series", sl + ".html"), "w").write(pagina(titulo, txt or titulo, corpo, "../", "s:" + sl))
    # cada obra
    for i, w in enumerate(W):
        fotos = [w["foto"]] + w["detalhes"]
        thumbs = "".join(f'<button data-src="../img/{k}.jpg" data-full="../img/{k}.jpg" aria-current="{"true" if j == 0 else "false"}" aria-label="Foto {j + 1}"><img src="../img/{k}-t.jpg" alt="" loading="lazy"></button>'
                         for j, k in enumerate(fotos)) if len(fotos) > 1 else ""
        ficha = [("Técnica", w["tec"]), ("Materiais", w["mat"] if w["mat"] != "Díptico" else ""),
                 ("Dimensões", f'{w["dim"]} cm'.replace(" x ", " × ")), ("Formato", "Díptico" if w["q"] > 1 else ""), ("Ano", w["a"])]
        msg = f'Olá, Helenara! Tenho interesse na obra "{w["t"]}"' + (f' ({w["a"]})' if w["a"] else "") + "."
        from urllib.parse import quote
        cta = ('<div class="cta"><span class="sold">Vendida · coleção particular</span>'
               f'<a class="pill" href="https://wa.me/{ARTISTA["whats"]}" target="_blank" rel="noopener">Falar com a artista</a></div>') if w["vendida"] else (
               f'<div class="cta"><a class="pill dark" href="https://wa.me/{ARTISTA["whats"]}?text={quote(msg)}" target="_blank" rel="noopener">Consultar valor</a>'
               f'<a class="pill ico" href="mailto:{ARTISTA["email"]}?subject={quote("Obra: " + w["t"])}&body={quote(msg)}" aria-label="Consultar por e-mail">{IC_EM}</a></div>')
        ant, prox = W[i - 1], W[(i + 1) % len(W)]
        corpo = (f'<article><div class="obra"><div><div class="modes" role="group" aria-label="Visualização">'
                 f'<button class="pill" type="button" data-m="obra" aria-pressed="true">Obra</button><button class="pill" type="button" data-m="parede" aria-pressed="false">Na parede</button></div>'
                 f'<div class="wall stage" hidden>{parede(w, tam)}</div>'
                 f'<div class="view stage"><img src="../img/{w["foto"]}.jpg" data-zoom="../img/{w["foto"]}.jpg" alt="{e(w["t"])}"></div>'
                 f'<p class="cap wallcap" hidden>Simulação em escala aproximada na parede do ateliê. A artista tem 1,60 m.</p>'
                 f'<div class="thumbs">{thumbs}</div><p class="cap zoomcap">Toque na imagem para ampliar.</p></div>'
                 f'<aside class="obra-txt"><div><h1>{e(w["t"])}</h1>'
                 + (f'<p class="serie"><a href="../series/{slug(w["s"])}.html">Série {e(w["s"])}</a></p>' if w["s"] else "") + '</div>'
                 f'<dl class="ficha">{"".join(f"<dt class=k>{k}</dt><dd>{e(v)}</dd>" for k, v in ficha if v)}</dl>{cta}</aside></div>'
                 f'<nav class="pn" aria-label="Outras obras"><a class="pill" href="{ant["slug"]}.html">← {e(ant["t"])}</a><a class="pill" href="{prox["slug"]}.html">{e(prox["t"])} →</a></nav></article>')
        desc = f'{w["t"]}' + (f', {w["a"]}' if w["a"] else "") + f'. {w["tec"] + ", " if w["tec"] else ""}{w["dim"]} cm. Obra de {nome}.'
        open(os.path.join(args.out, "obras", w["slug"] + ".html"), "w").write(pagina(f'{w["t"]} · {nome}', desc, corpo, "../", "obras", og=f'../img/{w["foto"]}.jpg'))
    # sobre
    cv = "".join(f'<div><h3>{e(t)}</h3><ul>{"".join(f"<li>{e(x)}</li>" for x in L)}</ul></div>' for t, L in CV)
    corpo = (f'<section class="sobre"><figure><img class="rv" src="img/inicio.jpg" alt="{e(nome)} no ateliê"></figure>'
             f'<div class="txt"><h1>Olá, sou a Helenara</h1><p class="sub">Artista visual. Nascida em Porto Alegre/RS, vive e trabalha em Curitiba/PR.</p>'
             + "".join(f"<p>{e(p)}</p>" for p in STATEMENT) + f'<div class="cv">{cv}</div>'
             f'<div class="contatos"><a class="pill dark" href="https://wa.me/{ARTISTA["whats"]}" target="_blank" rel="noopener">{IC_WA} WhatsApp</a>'
             f'<a class="pill" href="mailto:{e(ARTISTA["email"])}">{IC_EM} {e(ARTISTA["email"])}</a>'
             f'<a class="pill" href="https://instagram.com/{ARTISTA["insta"]}" target="_blank" rel="noopener">{IC_IG} @{e(ARTISTA["insta"])}</a></div></div></section>')
    # prévia da nova página inicial (abertura + série em destaque)
    por_id = {w["id"]: w for w in W}
    HERO = [x for x in ("o21", "o08", "o01", "o06", "o30", "o09", "o07", "o02") if x in por_id]
    sl, caps, dots = [], [], []
    for k, wid in enumerate(HERO):
        w = por_id[wid]
        src = f'img/{w["foto"]}.jpg'
        ph = ' src="data:image/gif;base64,R0lGODlhAQABAAAAACw="'
        sl.append(f'<div class="sl"><img {"src" if k < 2 else "data-src"}="{src}" alt="{e(w["t"])}"{"" if k < 2 else ph}></div>')
        caps.append(f'<a class="tt" data-i="{k}" href="obras/{w["slug"]}.html" hidden>{e(w["t"])}<span>{"Série " + e(w["s"]) + " · " if w["s"] else ""}{e(w["a"])}</span></a>')
        dots.append(f'<button aria-label="Obra {k + 1}: {e(w["t"])}"></button>')
    hero = (f'<section class="hero" aria-label="Obras em destaque">{"".join(sl)}'
            f'<div class="hcap"><div><p class="lg">Helenara Andrade · Pintura</p>{"".join(caps)}</div>'
            f'<div class="hctl"><div class="dots">{"".join(dots)}</div><a class="pill light" href="obras.html">Ver obras</a></div></div></section>')
    DEST = "Temporalidades"
    wd = [w for w in W if w["s"] == DEST]
    itens = "".join(f'<a href="obras/{w["slug"]}.html" tabindex="-1"><div class="frame"><img src="img/{w["foto"]}-t.jpg" alt="{e(w["t"])}" loading="lazy"></div>'
                    f'<div class="meta"><span class="t">{e(w["t"])}</span><span class="d">{e(w["dim"])} cm</span></div></a>' for w in wd)
    feat = (f'<section class="sec"><div class="feat"><div><p class="eyebrow">Série em destaque</p><h2>{e(DEST)}</h2>'
            f'<p class="txt">{e(SERIES_TXT.get(DEST, ""))}</p><a class="pill dark" href="series/{slug(DEST)}.html">Ver a série · {len(wd)} obras</a></div>'
            f'<div class="strip"><div class="track">{itens}{itens}</div></div></div></section>')
    scards = ""
    for n, sl_, c in SERIES_NAV:
        if sl_ == "sem-serie":
            continue
        capa = next(w for w in W if w["s"] == n)
        scards += (f'<a class="sc item" href="series/{sl_}.html"><div class="frame"><img class="rv" src="img/{capa["foto"]}-t.jpg" alt="" loading="lazy"></div>'
                   f'<b>{e(n)}</b><small>{c} obra{"s" if c != 1 else ""}</small></a>')
    series_sec = (f'<section class="sec"><div class="shead2"><div><p class="eyebrow">Séries</p><h2>Investigações</h2></div>'
                  f'<a class="pill" href="obras.html">Todas as obras →</a></div><div class="sgrid">{scards}</div></section>')
    teaser = (f'<section class="sec"><div class="teaser"><img src="img/inicio.jpg" alt="{e(nome)} no ateliê" loading="lazy">'
              f'<div><p class="eyebrow">Sobre</p><h2>{e(nome)}</h2><p>{e(STATEMENT[0])}</p><a class="pill" href="sobre.html">Conheça a artista</a></div></div></section>')
    prev = os.path.join(args.out, "previa.html")
    if os.path.exists(prev):
        os.remove(prev)
    open(os.path.join(args.out, "index.html"), "w").write(
        pagina(f"{nome} · Pintura", f"Portfólio da artista visual {nome}.", hero + feat + series_sec + teaser, "", "inicio", og="img/inicio.jpg", classe="home"))
    open(os.path.join(args.out, "sobre.html"), "w").write(pagina(f"Sobre · {nome}", STATEMENT[0][:150], corpo, "", "sobre"))
    # limpa páginas de obras que saíram do site
    validas = {w["slug"] + ".html" for w in W}
    for f in glob.glob(os.path.join(args.out, "obras", "*.html")):
        if os.path.basename(f) not in validas:
            os.remove(f)
    # remove fotos de obras que saíram do site (para não ficarem públicas)
    usadas = {k + x for k in keys for x in (".jpg", "-t.jpg")} | {"parede.jpg", "parede-vazia.jpg"}
    for f in glob.glob(os.path.join(args.out, "img", "*.jpg")):
        if os.path.basename(f) not in usadas:
            os.remove(f)
    json.dump({"obras": len(W), "fotos": len(dict.fromkeys(keys))}, open(os.path.join(args.out, "build.json"), "w"))
    print(f"Site gerado: {len(W)} obras, {len(dict.fromkeys(keys))} fotos → {args.out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.path.join(os.path.dirname(__file__), "..", "data", "base.json"))
    ap.add_argument("--db", required=True)
    ap.add_argument("--media", required=True)
    ap.add_argument("--out", default="docs")
    ap.add_argument("--artifact", action="store_true")
    ap.add_argument("--faltando", action="store_true", help="só lista as fotos que faltam em --media")
    build(ap.parse_args())
