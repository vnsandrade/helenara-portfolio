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
            w["dim"] = f'{fmt(ed["alt"])} x {fmt(ed["larg"])}' + (" (cada)" if w["q"] > 1 else "")
        if ed.get("foto"):
            w["foto"] = ed["foto"]
        W.append(w)
    for doc_id, n in sorted(novas.items(), key=lambda kv: str(kv[1].get("criado", ""))):
        W.append({"id": "n_" + doc_id, "ord": 1000, "t": n.get("t") or "Sem título", "a": str(n.get("a") or ""),
                  "s": n.get("s") or "", "tec": n.get("tec") or "", "mat": n.get("mat") or "",
                  "dim": f'{fmt(n["alt"])} x {fmt(n["larg"])}', "q": 1, "foto": n["foto"], "detalhes": [],
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
:root{--bg:#FAFAF8;--ink:#141414;--muted:#6E6E6A;--line:#E4E3DF;--sold:#B23B3B;--btn:#141414;--btn-ink:#fff;
--f:"Helvetica Neue","Neue Haas Grotesk Text Pro",Helvetica,"Inter Tight",Arial,sans-serif;color-scheme:light}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--f);font-size:16px;line-height:1.5;-webkit-font-smoothing:antialiased}
a{color:inherit}
img{max-width:100%;display:block}
.wrap{max-width:1360px;margin:0 auto;padding-inline:max(20px,env(safe-area-inset-left,0px))}
header.top{display:flex;justify-content:space-between;align-items:baseline;gap:16px;flex-wrap:wrap;padding-block:28px}
.brand{font-size:20px;font-weight:500;letter-spacing:-.02em;text-decoration:none}
nav.menu{display:flex;gap:26px;font-size:15px}
nav.menu a{text-decoration:none;color:var(--muted)}
nav.menu a:hover,nav.menu a[aria-current="page"]{color:var(--ink)}
.eyebrow{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
h1,h2,h3{font-weight:500;letter-spacing:-.025em;margin:0;text-wrap:balance}
.hero{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,.85fr);gap:clamp(28px,5vw,80px);align-items:end;padding-block:clamp(24px,6vw,72px) clamp(40px,7vw,96px)}
.hero h1{font-size:clamp(48px,9vw,128px);line-height:.92;letter-spacing:-.05em}
.hero p{font-size:clamp(17px,1.5vw,20px);max-width:38ch;color:#3a3a37;margin:28px 0 0}
.hero figure{margin:0}
.hero img{width:100%;aspect-ratio:3/4;object-fit:cover;object-position:50% 35%}
.hero figcaption,.cap{font-size:13px;color:var(--muted);margin-top:10px}
.sec{padding-block:clamp(40px,6vw,80px);border-top:1px solid var(--line)}
.sechead{display:flex;justify-content:space-between;align-items:baseline;gap:16px;margin-bottom:32px;flex-wrap:wrap}
.sechead h2{font-size:clamp(28px,3.4vw,44px)}
.more{font-size:15px}
.grid{columns:3 320px;column-gap:clamp(20px,3vw,48px)}
.item{break-inside:avoid;display:block;text-decoration:none;margin-bottom:clamp(36px,4vw,56px)}
.item img{width:100%;height:auto;background:var(--line);transition:opacity .25s}
.item:hover img{opacity:.88}
.meta{display:flex;justify-content:space-between;gap:12px;margin-top:12px;font-size:14px}
.meta .t{font-weight:500}
.meta .d{color:var(--muted);text-align:right;white-space:nowrap}
.sold{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:var(--muted)}
.sold::before{content:"";width:7px;height:7px;border-radius:50%;background:var(--sold)}
.filters{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:36px}
.filters button{font:inherit;font-size:14px;border:1px solid var(--line);background:transparent;border-radius:999px;padding:7px 14px;cursor:pointer;color:var(--muted)}
.filters button[aria-pressed="true"]{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.obra{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(280px,.7fr);gap:clamp(28px,5vw,80px);padding-block:clamp(16px,3vw,40px) clamp(48px,6vw,96px);align-items:start}
.view img{width:100%;height:auto;max-height:84vh;object-fit:contain;object-position:left top;cursor:zoom-in}
.thumbs{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}
.thumbs button{padding:0;border:2px solid transparent;background:none;cursor:pointer}
.thumbs button[aria-current="true"]{border-color:var(--ink)}
.thumbs img{width:76px;height:76px;object-fit:cover}
.info{position:sticky;top:24px;display:flex;flex-direction:column;gap:18px}
.info h1{font-size:clamp(30px,3.6vw,48px);line-height:1.05}
.info .yr{color:var(--muted);font-weight:400}
.ficha{margin:0;display:grid;grid-template-columns:auto 1fr;gap:6px 18px;font-size:15px;border-top:1px solid var(--line);padding-top:18px}
.ficha dt{color:var(--muted)}
.ficha dd{margin:0}
.cta{display:flex;flex-direction:column;gap:10px;border-top:1px solid var(--line);padding-top:18px}
.btn{display:inline-flex;justify-content:center;align-items:center;gap:8px;font:inherit;font-size:15px;font-weight:500;padding:13px 20px;border-radius:2px;text-decoration:none;border:1px solid var(--ink)}
.btn.solid{background:var(--btn);color:var(--btn-ink)}
.btn:hover{opacity:.85}
.pn{display:flex;justify-content:space-between;gap:16px;border-top:1px solid var(--line);padding-top:18px;font-size:14px}
.pn a{text-decoration:none;color:var(--muted)}.pn a:hover{color:var(--ink)}
.sobre{display:grid;grid-template-columns:minmax(0,.8fr) minmax(0,1.2fr);gap:clamp(28px,5vw,80px);padding-block:clamp(24px,5vw,64px) clamp(48px,6vw,96px);align-items:start}
.sobre img{width:100%;aspect-ratio:3/4;object-fit:cover;object-position:50% 35%}
.sobre .txt{display:flex;flex-direction:column;gap:22px;max-width:62ch}
.sobre .txt>p{font-size:clamp(17px,1.4vw,20px);margin:0}
.cv{display:grid;gap:28px;margin-top:20px;border-top:1px solid var(--line);padding-top:28px}
.cv h3{font-size:13px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:500;margin-bottom:10px}
.cv ul{list-style:none;margin:0;padding:0;display:grid;gap:6px;font-size:15px}
footer.foot{border-top:1px solid var(--line);padding-block:48px 64px;display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:24px;font-size:15px}
footer.foot a{text-decoration:none}footer.foot a:hover{text-decoration:underline}
footer.foot .big{font-size:clamp(24px,3vw,36px);font-weight:500;letter-spacing:-.025em;grid-column:1/-1}
#lb{position:fixed;inset:0;background:rgba(10,10,10,.96);display:none;z-index:50;overflow:hidden;touch-action:none}
#lb.on{display:flex;align-items:center;justify-content:center}
#lb img{max-width:92vw;max-height:90vh;object-fit:contain;transform-origin:center;cursor:zoom-in;user-select:none}
#lb.z img{cursor:grab}
#lb button{position:absolute;top:16px;right:16px;width:44px;height:44px;border-radius:50%;border:0;background:rgba(255,255,255,.15);color:#fff;font-size:22px;cursor:pointer}
@media (max-width:820px){.hero,.obra,.sobre{grid-template-columns:1fr}.hero figure{order:-1}.info{position:static}nav.menu{gap:18px}}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
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

FILTER_JS = """
(()=>{const bs=[...document.querySelectorAll('.filters button')];bs.forEach(b=>b.onclick=()=>{const v=b.dataset.s;
bs.forEach(o=>o.setAttribute('aria-pressed',o===b));document.querySelectorAll('.grid .item').forEach(it=>{it.hidden=v!=='*'&&it.dataset.s!==v})});})();
"""


def pagina(titulo, desc, corpo, rel, atual, artifact_index=False, og=""):
    head = (f'<title>{e(titulo)}</title>\n<meta name="description" content="{e(desc)}">\n'
            f'<meta property="og:title" content="{e(titulo)}">\n<meta property="og:description" content="{e(desc)}">\n'
            + (f'<meta property="og:image" content="{e(og)}">\n' if og else "")
            + '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
              '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;500;600&display=swap">\n'
            + f'<link rel="stylesheet" href="{rel}estilo.css">\n')
    menu = "".join(f'<a href="{rel}{h}"{" aria-current=\"page\"" if atual == k else ""}>{n}</a>'
                   for k, h, n in (("obras", "obras.html", "Obras"), ("sobre", "sobre.html", "Sobre"), ("contato", "#contato", "Contato")))
    topo = f'<div class="wrap"><header class="top"><a class="brand" href="{rel}index.html">{e(ARTISTA["nome"])}</a><nav class="menu" aria-label="Menu">{menu}</nav></header></div>'
    rodape = (f'<div class="wrap"><footer class="foot" id="contato"><div class="big">Contato</div>'
              f'<div><div class="eyebrow">WhatsApp</div><a href="https://wa.me/{ARTISTA["whats"]}" target="_blank" rel="noopener">{e(ARTISTA["fone"])}</a></div>'
              f'<div><div class="eyebrow">E-mail</div><a href="mailto:{e(ARTISTA["email"])}">{e(ARTISTA["email"])}</a></div>'
              f'<div><div class="eyebrow">Instagram</div><a href="https://instagram.com/{ARTISTA["insta"]}" target="_blank" rel="noopener">@{e(ARTISTA["insta"])}</a></div>'
              f'<div><div class="eyebrow">Ateliê</div>{e(ARTISTA["local"])}</div></footer></div>')
    body = topo + corpo + rodape + f'<div id="lb" role="dialog" aria-label="Foto ampliada"><img alt=""><button aria-label="Fechar">×</button></div><script>{LB_JS}{FILTER_JS}</script>'
    if artifact_index:  # página principal da prévia no Claude: o host envolve com o esqueleto HTML
        return head + f'<style>{CSS}</style>\n' + body
    return ('<!doctype html>\n<html lang="pt-BR"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n' + head + '</head><body>' + body + '</body></html>')


def card(w, rel, tam):
    tw, th = tam.get(w["foto"], (720, 900))
    return (f'<a class="item" href="{rel}obras/{w["slug"]}.html" data-s="{e(w["s"] or "—")}">'
            f'<img src="{rel}img/{w["foto"]}-t.jpg" width="{tw}" height="{th}" alt="{e(w["t"])}" loading="lazy">'
            f'<div class="meta"><span><span class="t">{e(w["t"])}</span>{", " + e(w["a"]) if w["a"] else ""}'
            f'{"<br><span class=sold>Vendida</span>" if w["vendida"] else ""}</span><span class="d">{e(w["dim"])} cm</span></div></a>')


def build(args):
    base = json.load(open(args.base, encoding="utf-8"))
    W = montar_obras(base, args.db)
    keys = ["inicio"] + [w["foto"] for w in W] + [k for w in W for k in w["detalhes"]]
    tam = gerar_imagens(dict.fromkeys(keys), args.media, args.out)
    os.makedirs(os.path.join(args.out, "obras"), exist_ok=True)
    open(os.path.join(args.out, "estilo.css"), "w").write(CSS)
    nome = ARTISTA["nome"]
    recentes = [w for w in W if w["a"] and int(w["a"]) >= max(int(x["a"]) for x in W if x["a"].isdigit()) - 0][:9] or W[:9]
    # início
    corpo = (f'<main class="wrap"><section class="hero"><div><div class="eyebrow">Pintura · {e(ARTISTA["local"])}</div>'
             f'<h1>{e(nome)}</h1><p>{e(STATEMENT[0].split(", buscando")[0])}.</p>'
             f'<p><a class="btn" href="obras.html">Ver obras</a></p></div>'
             f'<figure><img src="img/inicio.jpg" alt="{e(nome)} no ateliê"><figcaption>{e(nome)} no ateliê</figcaption></figure></section>'
             f'<section class="sec"><div class="sechead"><h2>Obras recentes</h2><a class="more" href="obras.html">Todas as obras ({len(W)}) →</a></div>'
             f'<div class="grid">{"".join(card(w, "", tam) for w in recentes)}</div></section></main>')
    open(os.path.join(args.out, "index.html"), "w").write(pagina(f"{nome} · Pintura", "Portfólio da artista visual " + nome + ": pinturas, séries e exposições.", corpo, "", "inicio", args.artifact, "img/inicio.jpg"))
    # obras
    series = sorted({w["s"] for w in W if w["s"]})
    filtros = '<button data-s="*" aria-pressed="true">Todas</button>' + "".join(f'<button data-s="{e(s)}" aria-pressed="false">{e(s)}</button>' for s in series)
    corpo = (f'<main class="wrap"><section class="sec" style="border-top:0;padding-top:16px"><div class="sechead"><h2>Obras</h2><span class="cap">{len(W)} obras</span></div>'
             f'<div class="filters" role="group" aria-label="Filtrar por série">{filtros}</div>'
             f'<div class="grid">{"".join(card(w, "", tam) for w in W)}</div></section></main>')
    open(os.path.join(args.out, "obras.html"), "w").write(pagina(f"Obras · {nome}", f"{len(W)} obras de {nome}.", corpo, "", "obras"))
    # cada obra
    for i, w in enumerate(W):
        fotos = [w["foto"]] + w["detalhes"]
        thumbs = "".join(f'<button data-src="../img/{k}.jpg" data-full="../img/{k}.jpg" aria-current="{"true" if j == 0 else "false"}" aria-label="Foto {j + 1}"><img src="../img/{k}-t.jpg" alt="" loading="lazy"></button>'
                         for j, k in enumerate(fotos)) if len(fotos) > 1 else ""
        ficha = [("Ano", w["a"]), ("Técnica", w["tec"]), ("Materiais", w["mat"] if w["mat"] != "Díptico" else ""),
                 ("Dimensões", f'{w["dim"]} cm'), ("Formato", "Díptico" if w["q"] > 1 else ""), ("Série", w["s"])]
        msg = f'Olá, Helenara! Tenho interesse na obra "{w["t"]}"' + (f' ({w["a"]})' if w["a"] else "") + "."
        from urllib.parse import quote
        cta = ('<div class="cta"><span class="sold">Vendida</span><span class="cap" style="margin:0">Esta obra pertence a uma coleção particular. Para obras disponíveis ou encomendas, fale com a artista.</span>'
               f'<a class="btn" href="https://wa.me/{ARTISTA["whats"]}" target="_blank" rel="noopener">Falar com a artista</a></div>') if w["vendida"] else (
               '<div class="cta"><span class="cap" style="margin:0">Valor sob consulta.</span>'
               f'<a class="btn solid" href="https://wa.me/{ARTISTA["whats"]}?text={quote(msg)}" target="_blank" rel="noopener">Consultar pelo WhatsApp</a>'
               f'<a class="btn" href="mailto:{ARTISTA["email"]}?subject={quote("Obra: " + w["t"])}&body={quote(msg)}">Enviar e-mail</a></div>')
        ant, prox = W[i - 1], W[(i + 1) % len(W)]
        corpo = (f'<main class="wrap"><article class="obra"><div><div class="view"><img src="../img/{w["foto"]}.jpg" data-zoom="../img/{w["foto"]}.jpg" alt="{e(w["t"])}"></div>'
                 f'<div class="thumbs">{thumbs}</div><p class="cap">Toque na imagem para ampliar.</p></div>'
                 f'<div class="info"><a class="cap" href="../obras.html" style="margin:0;text-decoration:none">← Obras</a>'
                 f'<h1>{e(w["t"])}{", <span class=yr>" + e(w["a"]) + "</span>" if w["a"] else ""}</h1>'
                 f'<dl class="ficha">{"".join(f"<dt>{k}</dt><dd>{e(v)}</dd>" for k, v in ficha if v)}</dl>{cta}'
                 f'<nav class="pn" aria-label="Outras obras"><a href="{ant["slug"]}.html">← {e(ant["t"])}</a><a href="{prox["slug"]}.html">{e(prox["t"])} →</a></nav></div></article></main>')
        desc = f'{w["t"]}' + (f', {w["a"]}' if w["a"] else "") + f'. {w["tec"] + ", " if w["tec"] else ""}{w["dim"]} cm. Obra de {nome}.'
        open(os.path.join(args.out, "obras", w["slug"] + ".html"), "w").write(pagina(f'{w["t"]} · {nome}', desc, corpo, "../", "obras", og=f'../img/{w["foto"]}.jpg'))
    # sobre
    cv = "".join(f'<div><h3>{e(t)}</h3><ul>{"".join(f"<li>{e(x)}</li>" for x in L)}</ul></div>' for t, L in CV)
    corpo = (f'<main class="wrap"><section class="sobre"><figure style="margin:0"><img src="img/inicio.jpg" alt="{e(nome)} no ateliê"></figure>'
             f'<div class="txt"><div class="eyebrow">Sobre</div><h1 style="font-size:clamp(34px,4vw,56px)">{e(nome)}</h1>'
             f'<p class="cap" style="margin:0">Nascida em Porto Alegre/RS. Vive e trabalha em Curitiba/PR.</p>'
             + "".join(f"<p>{e(p)}</p>" for p in STATEMENT) + f'<div class="cv">{cv}</div></div></section></main>')
    open(os.path.join(args.out, "sobre.html"), "w").write(pagina(f"Sobre · {nome}", STATEMENT[0][:150], corpo, "", "sobre"))
    # limpa páginas de obras que saíram do site
    validas = {w["slug"] + ".html" for w in W}
    for f in glob.glob(os.path.join(args.out, "obras", "*.html")):
        if os.path.basename(f) not in validas:
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
    build(ap.parse_args())
