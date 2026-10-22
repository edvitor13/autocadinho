r"""Gera a página do Autocadinho: um único arquivo HTML, com as capturas de tela embutidas.

Uso:  .venv\Scripts\python tools\make_site.py [saída]   (padrão: docs/site/index.html)

As capturas vêm de docs/img (gere antes com tools\screenshots.py). Cada uma é convertida para WebP e
embutida em Base64 num bloco JSON no fim da página; o navegador só decodifica uma imagem quando ela chega
perto da tela (IntersectionObserver), então a página abre leve. Enquanto isso, aparece uma miniatura
borrada de poucas centenas de bytes no lugar.

O botão de download aponta para a última release no GitHub. Quando o navegador consegue falar com a API
do GitHub, ele troca pelo link direto do .msi, com a versão e o tamanho.
"""

from __future__ import annotations

import base64
import html
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # só converte imagens: nenhuma janela

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication, QImage  # noqa: E402

from autocadinho import APP_NAME, REPO_URL, __date__, __version__  # noqa: E402

IMG = ROOT / "docs" / "img"
QUALITY = 86  # WebP com perda: texto da interface continua nítido e o arquivo fica com metade do PNG
TINY_W = 40  # largura da miniatura borrada que aparece enquanto a imagem carrega

# chave -> (arquivo em docs/img, texto alternativo)
SHOTS = {
    "planta": ("planta.png", "Planta de uma casa no Autocadinho, com portas, janelas, louças, áreas e o painel da porta"),
    "simbolos": ("simbolos.png", "Menu de símbolos aberto: porta, porta dupla, porta de correr, janela, escada, "
                                 "vaso sanitário, pia, chuveiro e norte"),
    "desenho": ("desenho.png", "Planta de um mezanino com vigas, pilares e medidas, com uma viga selecionada"),
    "escuro": ("desenho-escuro.png", "O mesmo desenho no tema escuro"),
    "imprimir": ("imprimir.png", "Janela de impressão com a prévia da folha, o papel e a escala"),
    "inicio": ("inicio.png", "Tela inicial com os botões Novo desenho, Abrir desenho e Ver um exemplo"),
    "atualizar": ("atualizar.png", "Janela de atualização com as novidades da versão nova e o botão Atualizar agora"),
}


def encode(img: QImage, fmt: str, quality: int) -> bytes:
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    if not img.save(buf, fmt, quality):
        raise SystemExit(f"O Qt não conseguiu gravar {fmt} (falta o plugin de imagem?)")
    return bytes(data)


def load_shots() -> tuple[dict[str, str], dict[str, dict]]:
    """Base64 das capturas (WebP) e, para cada uma, tamanho e miniatura."""
    big, meta = {}, {}
    for key, (name, alt) in SHOTS.items():
        path = IMG / name
        img = QImage(str(path))
        if img.isNull():
            raise SystemExit(f"Captura não encontrada: {path} (rode tools\\screenshots.py)")
        big[key] = base64.b64encode(encode(img, "WEBP", QUALITY)).decode("ascii")
        tiny = img.scaledToWidth(TINY_W, Qt.TransformationMode.SmoothTransformation)
        meta[key] = {"w": img.width(), "h": img.height(), "alt": alt,
                     "tiny": base64.b64encode(encode(tiny, "WEBP", 40)).decode("ascii")}
    return big, meta


def shot(meta: dict[str, dict], key: str, cls: str = "") -> str:
    """Figura com a miniatura de fundo; a imagem de verdade entra quando aparece na tela."""
    m = meta[key]
    return (f'<figure class="shot {cls}" style="aspect-ratio:{m["w"]}/{m["h"]};'
            f'background-image:url(data:image/webp;base64,{m["tiny"]})">'
            f'<img data-img="{key}" alt="{html.escape(m["alt"])}" width="{m["w"]}" height="{m["h"]}" '
            f'decoding="async"></figure>')


def logo_svg(size: int) -> str:
    svg = (ROOT / "assets" / "logo.svg").read_text(encoding="utf-8")
    svg = svg[svg.index("<svg"):]
    svg = svg.replace('width="512" height="512"', f'width="{size}" height="{size}" aria-hidden="true"')
    svg = "\n".join(line for line in svg.splitlines() if "<!--" not in line)
    return svg.replace('id="fundo"', f'id="fundo{size}"').replace("url(#fundo)", f"url(#fundo{size})")


# Ícones de traço (24 × 24), no mesmo espírito dos do app.
ICONS = {
    "ruler": '<path d="M3 17 17 3l4 4L7 21z"/><path d="M7 13l2 2M10 10l2 2M13 7l2 2"/>',
    "edit": '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13.5 6.5l4 4"/>',
    "tag": '<path d="M3 12V4h8l10 10-8 8z"/><circle cx="7.5" cy="8.5" r="1.5"/>',
    "magnet": '<path d="M6 3v9a6 6 0 0 0 12 0V3h-4v9a2 2 0 0 1-4 0V3z"/><path d="M6 7h4M14 7h4"/>',
    "door": '<path d="M3 20h18"/><path d="M6 20V5"/><path d="M6 5a15 15 0 0 1 15 15"/>',
    "shapes": '<rect x="3" y="12" width="8" height="8"/><circle cx="17" cy="7" r="4"/><path d="M13.5 20l3.5-6 3.5 6z"/>',
    "font": '<path d="M3 20 8.5 5h1L15 20M5.5 14h7"/><circle cx="18" cy="16.5" r="2.5"/><path d="M20.5 13v7"/>',
    "print": '<path d="M7 9V3h10v6"/><path d="M7 17H4v-8h16v8h-3"/><path d="M7 14h10v7H7z"/>',
    "file": '<path d="M14 3H6v18h12V7z"/><path d="M14 3v4h4M9 13h6M9 17h4"/>',
    "save": '<path d="M5 3h11l3 3v15H5z"/><path d="M8 3v5h7V3M8 21v-7h8v7"/>',
    "undo": '<path d="M9 14 4 9l5-5"/><path d="M4 9h11a5 5 0 0 1 0 10h-3"/>',
    "moon": '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2'
           'M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
    "download": '<path d="M12 3v12M7 10l5 5 5-5M4 15v5h16v-5"/>',
    "code": '<path d="M8 8l-4 4 4 4M16 8l4 4-4 4M14 4l-4 16"/>',
    "stairs": '<path d="M3 20h5v-4h4v-4h4V8h5"/>',
    "arrow": '<path d="M4 12h15M14 7l5 5-5 5"/>',
    "gift": '<rect x="3" y="8" width="18" height="4" rx="1"/><path d="M5 12v9h14v-9M12 8v13"/>'
            '<path d="M12 8C10.5 4.5 7 3 6.5 5.5S9 8 12 8zM12 8c1.5-3.5 5-5 5.5-2.5S15 8 12 8z"/>',
    "windows": '<path d="M3 5.6 10.5 4.5v7H3zM12.5 4.2 21 3v8.5h-8.5zM3 12.5h7.5v7L3 18.4zM12.5 12.5H21V21l-8.5-1.2z"/>',
    "folder": '<path d="M3 6.5A1.5 1.5 0 0 1 4.5 5H9l2 2.5h8.5A1.5 1.5 0 0 1 21 9v9.5a1.5 1.5 0 0 1-1.5 1.5h-15'
              'A1.5 1.5 0 0 1 3 18.5z"/>',
    "area": '<path d="M4 4h16v16H4z" stroke-dasharray="3 2.4"/><path d="M8 15l3-6 2 4 1.5-2 1.5 4"/>',
    "shield": '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>',
    "github": '<path d="M9 19c-4 1.5-4-2-6-2.5M15 21v-3.5c0-1 .1-1.4-.5-2 2.8-.3 5.5-1.4 5.5-6a4.6 4.6 0 0 0-1.3-3.2 '
              '4.2 4.2 0 0 0-.1-3.2s-1-.3-3.4 1.3a11.6 11.6 0 0 0-6.2 0C6.6 2.8 5.6 3.1 5.6 3.1a4.2 4.2 0 0 0-.1 3.2'
              'A4.6 4.6 0 0 0 4.2 9.5c0 4.6 2.7 5.7 5.5 6-.6.6-.6 1.2-.5 2V21"/>',
}


def icon(name: str, size: int = 22) -> str:
    return (f'<svg class="i" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            f'{ICONS[name]}</svg>')


NEW = [
    ("door", "Portas e janelas na parede",
     "Passe o mouse em cima da viga: a porta segue a direção da parede, fica na espessura certa e abre o vão "
     "sozinha. A tecla <kbd>R</kbd> vira o lado."),
    ("stairs", "Escada, louças e o norte",
     "Escada com os degraus contados sozinhos, vaso sanitário, pia, chuveiro e a seta do norte, prontos para "
     "colocar com um clique."),
    ("shapes", "Círculo, triângulo e polígono",
     "Polígono ponto a ponto para terrenos e cômodos tortos. O painel mostra a área, o perímetro e a medida de "
     "cada lado."),
    ("area", "Área em m²",
     "Retângulos, círculos e polígonos escrevem a área no meio da forma, para marcar o tamanho de cada cômodo."),
    ("font", "Qualquer fonte",
     "Escolha a fonte do desenho e a de cada texto entre as instaladas no computador, com prévia na lista. "
     "Negrito e itálico."),
    ("download", "Atualiza sozinho",
     "Quando sair uma versão nova, um botão mostra as novidades e instala com um clique. O arquivo é conferido "
     "antes de instalar."),
]

FEATURES = [
    ("ruler", "Centímetros de verdade",
     "Uma viga de 6,60 m tem 6,60 m. As medidas são calculadas e escritas sozinhas, em metros ou centímetros."),
    ("edit", "Medida exata no painel",
     "Escolha o desenho e digite 3,50: ele acompanha. Largura, cor, espessura e nome no mesmo lugar."),
    ("tag", "Nomes automáticos",
     "VIGA 1, VIGA 2… P1, P2… Troque a palavra (PAREDE, SAPATA), esconda ou arraste o nome para onde quiser."),
    ("magnet", "Encaixe e retas a 90°",
     "As pontas encaixam nas outras vigas, nos cantos e na grade. <kbd>Shift</kbd> inclina e <kbd>Alt</kbd> solta."),
    ("print", "Imprime em escala",
     "A4, A3, A2, Carta ou Ofício, ajustado à folha ou em 1:50, 1:100… para medir no papel com a régua."),
    ("file", "PDF e imagem",
     "Salve a folha em PDF ou PNG e mande por WhatsApp ou e-mail, do jeito que sairia na impressora."),
    ("save", "Salva e continua depois",
     "Arquivos .cadinho, desenhos recentes com miniatura e uma cópia de segurança se o computador desligar."),
    ("undo", "Desfazer sem medo",
     "<kbd>Ctrl</kbd>+<kbd>Z</kbd> desfaz até 300 passos. Copiar, colar, duplicar e girar como em qualquer programa."),
    ("moon", "Claro ou escuro",
     "Tema claro por padrão e um escuro para descansar a vista. A folha impressa sai sempre branca."),
    ("globe", "Português e inglês",
     "O programa pergunta o idioma na primeira vez, e dá para trocar a qualquer momento sem perder o desenho."),
    ("shield", "Sem cadastro e sem internet",
     "Desenhar, salvar e imprimir funcionam sem internet. A busca de atualizações não envia nada e pode ser desligada."),
    ("code", "Grátis e de código aberto",
     "Sem versão paga e sem anúncios. Licença MIT: use, copie e compartilhe à vontade; o código está no GitHub."),
]

GALLERY = [
    ("planta", "Planta da casa"), ("simbolos", "Símbolos"), ("desenho", "Vigas e pilares"),
    ("escuro", "Tema escuro"), ("imprimir", "Impressão"), ("inicio", "Tela inicial"), ("atualizar", "Atualização"),
]

STEPS = [
    ("Instale", "Baixe o arquivo <b>.msi</b>, abra, marque que aceita a licença e clique em <b>Instalar</b>. Não "
     "pede senha de administrador. Se o Windows mostrar <i>“O Windows protegeu o computador”</i>, clique em "
     "<b>Mais informações</b> e em <b>Executar assim mesmo</b>. Na primeira vez, escolha o idioma.", None),
    ("Comece um desenho", "Na tela inicial, <b>Novo desenho</b> abre uma folha quadriculada com a ferramenta Viga "
     "escolhida. <b>Ver um exemplo</b> abre uma planta pronta para experimentar à vontade. Os desenhos salvos "
     "aparecem ali, com miniatura.", None),
    ("Desenhe vigas, paredes e pilares", "<b>Viga</b> (<kbd>V</kbd>): clique no começo e arraste até o fim; ela "
     "fica reta e encaixa nas outras. <b>Pilar</b> (<kbd>P</kbd>): clique; ele encaixa nas pontas e no meio das "
     "vigas, e <kbd>R</kbd> deixa o próximo em pé ou deitado. <b>Medida</b> (<kbd>M</kbd>): arraste de um ponto a "
     "outro e o valor aparece sozinho.", None),
    ("Acerte as medidas", "Com <b>Selecionar</b> (<kbd>S</kbd>), clique num desenho e digite o comprimento certo no "
     "painel da direita, por exemplo <b>3,50</b>. Arraste as bolinhas para esticar e o nome para tirá-lo do caminho. "
     "Sem nada selecionado, o painel mostra os ajustes do desenho: letras, fonte, metros ou centímetros.", "desenho"),
    ("Ponha portas, janelas e louças", "Clique em <b>Símbolos</b> na coluna da esquerda e escolha. Passe o mouse em "
     "cima de uma viga ou linha: a porta gira junto com a parede e, ao clicar, abre o vão. <kbd>R</kbd> vira o lado. "
     "No painel, mude a largura do vão, o lado da dobradiça e para onde a porta abre.", "simbolos"),
    ("Formas, áreas e textos", "<b>Formas</b> tem retângulo (<kbd>Q</kbd>), círculo (<kbd>C</kbd>), triângulo e "
     "polígono (<kbd>G</kbd>): clique em cada canto e termine no primeiro ponto ou com <kbd>Enter</kbd>. Marque "
     "<b>Escrever a área</b> para ver os m². <b>Texto</b> (<kbd>T</kbd>): clique, escreva e aperte <kbd>Enter</kbd>; "
     "no painel, a fonte, o tamanho, negrito e itálico.", None),
    ("Salve", "<kbd>Ctrl</kbd>+<kbd>S</kbd> grava um arquivo <b>.cadinho</b> para continuar depois; ele abre com "
     "dois cliques. Enquanto você desenha, o programa guarda uma cópia de segurança: se faltar luz, ele oferece "
     "<b>Recuperar</b> na próxima vez.", None),
    ("Imprima ou mande por WhatsApp", "O botão laranja <b>Imprimir</b> (<kbd>Ctrl</kbd>+<kbd>P</kbd>) mostra a "
     "folha como vai sair. Escolha o papel e a escala (<i>Ajustar à folha</i> ou 1:50, 1:100…). <b>PDF…</b> e "
     "<b>Imagem…</b> salvam a folha num arquivo para mandar.", "imprimir"),
]

KEYS = [
    ("S · V · P · L · Q · C · G · M · T · E · H", "Selecionar, Viga, Pilar, Linha, Retângulo, Círculo, Polígono, "
     "Medida, Texto, Borracha e Mover a folha"),
    ("Esc", "Cancela e volta para Selecionar"),
    ("Shift (desenhando)", "Viga ou linha inclinada; quadrado; círculo perfeito"),
    ("Alt (desenhando ou movendo)", "Solta o encaixe"),
    ("R", "Gira o selecionado, o próximo pilar ou símbolo; vira o lado da porta"),
    ("Enter · Backspace", "No polígono: termina a forma e desfaz o último ponto"),
    ("Setas", "Movem o selecionado (com Shift, dez vezes mais)"),
    ("Ctrl+Z · Ctrl+Y", "Desfaz e refaz"),
    ("Ctrl+C · Ctrl+V · Ctrl+D", "Copia, cola e duplica"),
    ("Ctrl+S · Ctrl+P", "Salva e imprime"),
    ("Rodinha · Espaço + arrastar", "Aproxima e afasta · move a folha"),
    ("Ctrl+0", "Mostra o desenho inteiro"),
    ("F1", "Abre o guia dentro do programa"),
]

FAQ = [
    ("O Windows disse que protegeu o computador. É seguro?",
     "O aviso aparece porque o Autocadinho não tem uma assinatura digital paga. Clique em <b>Mais informações</b> e "
     "em <b>Executar assim mesmo</b>. O código é aberto, e cada versão publica o arquivo <b>SHA256SUMS.txt</b> para "
     "quem quiser conferir o download."),
    ("Precisa de internet?",
     "Não para desenhar, salvar ou imprimir. A internet só é usada para procurar versões novas, no máximo uma vez por "
     "dia e sem enviar nada. Dá para desligar no menu <b>⋯</b> › <i>Procurar atualizações sozinho</i>."),
    ("Como atualizo?",
     "A partir da versão 1.1, o botão <b>Atualizar para…</b> aparece sozinho quando sai uma versão nova: um clique "
     "mostra as novidades, baixa, confere e instala. Quem tem a 1.0 instala o .msi novo por cima uma vez; desenhos e "
     "preferências continuam como estavam."),
    ("A viga não fica inclinada.",
     "As retas a 90° estão ligadas. Segure <kbd>Shift</kbd> enquanto desenha, ou desligue <b>Retas 90°</b> na barra "
     "de baixo."),
    ("A porta não abriu o vão na parede.",
     "Ela precisa ser colocada em cima de uma viga ou linha (a prévia gira sozinha quando está em cima). Se já foi "
     "colocada fora, arraste para cima da parede e confira a espessura da <i>Parede</i> no painel: com 0, o vão não "
     "abre."),
    ("Como escrevo a área de um cômodo?",
     "Desenhe um retângulo (ou um polígono, se o cômodo for torto) por cima do cômodo e marque <b>Escrever a "
     "área</b>. Deixe o contorno tracejado ou numa cor clara para não confundir com as paredes."),
    ("O computador desligou e eu não tinha salvado.",
     "Abra o Autocadinho de novo e clique em <b>Recuperar</b>. A cópia de segurança é gravada poucos segundos depois "
     "de cada mudança."),
    ("Funciona no Mac ou no Linux?",
     "Os pacotes prontos são só para Windows. O programa é feito em Python e roda pelo código-fonte em outros "
     "sistemas, para quem souber instalar o Python."),
]

CSS = r"""
:root{--bg:#f6f7f9;--panel:#fff;--panel2:#f1f3f6;--text:#1d2127;--muted:#5b6470;--faint:#8b939e;--border:#e3e6eb;
--accent:#e8722c;--accent-hi:#f2884a;--accent-soft:#fdeee4;--on-accent:#fff;--grid:rgba(29,33,39,.045);
--shadow:0 1px 2px rgba(16,24,40,.06),0 12px 32px rgba(16,24,40,.09);color-scheme:light}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#121418;--panel:#1b1e24;--panel2:#22262d;
--text:#e7e9ec;--muted:#a3aab5;--faint:#6b7380;--border:#2c313a;--accent:#f2894a;--accent-hi:#f7a26b;
--accent-soft:#33241a;--on-accent:#1c1108;--grid:rgba(231,233,236,.04);--shadow:0 1px 2px rgba(0,0,0,.3),
0 12px 32px rgba(0,0,0,.35);color-scheme:dark}}
:root[data-theme=dark]{--bg:#121418;--panel:#1b1e24;--panel2:#22262d;--text:#e7e9ec;--muted:#a3aab5;--faint:#6b7380;
--border:#2c313a;--accent:#f2894a;--accent-hi:#f7a26b;--accent-soft:#33241a;--on-accent:#1c1108;
--grid:rgba(231,233,236,.04);--shadow:0 1px 2px rgba(0,0,0,.3),0 12px 32px rgba(0,0,0,.35);color-scheme:dark}
*{box-sizing:border-box}
html{scroll-behavior:smooth;-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.6 "Segoe UI Variable Text","Segoe UI",system-ui,
-apple-system,Roboto,"Helvetica Neue",Arial,sans-serif;-webkit-font-smoothing:antialiased}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
h1,h2,h3{line-height:1.2;margin:0;font-family:"Segoe UI Variable Display","Segoe UI",system-ui,-apple-system,
Roboto,Arial,sans-serif;letter-spacing:-.01em}
h2{font-size:clamp(1.6rem,3.2vw,2.2rem)}h3{font-size:1.06rem}
p{margin:0}
kbd{font:600 .78em/1 ui-monospace,"Cascadia Mono",Consolas,monospace;padding:.2em .45em;border:1px solid var(--border);
border-bottom-width:2px;border-radius:6px;background:var(--panel);color:var(--text);white-space:nowrap}
.wrap{max-width:1140px;margin:0 auto;padding:0 20px}
.i{flex:none;vertical-align:middle}
.skip{position:absolute;left:-999px}.skip:focus{left:12px;top:12px;z-index:9;background:var(--panel);padding:8px 12px;
border-radius:8px}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:6px}

/* topo */
header{position:sticky;top:0;z-index:5;background:color-mix(in srgb,var(--bg) 82%,transparent);
backdrop-filter:saturate(1.4) blur(10px);-webkit-backdrop-filter:saturate(1.4) blur(10px);
border-bottom:1px solid var(--border)}
.bar{display:flex;align-items:center;gap:22px;height:62px}
.brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:1.12rem;color:var(--text)}
.brand:hover{text-decoration:none}
nav{display:flex;gap:4px;margin-left:auto}
nav a{color:var(--muted);font-weight:600;font-size:.94rem;padding:7px 11px;border-radius:9px}
nav a:hover{color:var(--text);background:var(--panel2);text-decoration:none}
.iconbtn{display:grid;place-items:center;width:38px;height:38px;border-radius:10px;border:1px solid var(--border);
background:var(--panel);color:var(--text);cursor:pointer}
.iconbtn:hover{border-color:var(--accent);color:var(--accent)}
.iconbtn .sun{display:none}:root[data-dark] .iconbtn .sun{display:block}:root[data-dark] .iconbtn .moon{display:none}

/* botões */
.btn{display:inline-flex;align-items:center;gap:10px;padding:13px 20px;border-radius:12px;font-weight:650;
font-size:1rem;border:1px solid var(--border);background:var(--panel);color:var(--text);cursor:pointer;
transition:transform .15s,background .15s,border-color .15s}
.btn:hover{text-decoration:none;border-color:var(--accent);transform:translateY(-1px)}
.btn.primary{background:var(--accent);border-color:var(--accent);color:var(--on-accent);box-shadow:0 6px 18px
color-mix(in srgb,var(--accent) 35%,transparent)}
.btn.primary:hover{background:var(--accent-hi);border-color:var(--accent-hi)}
.btn small{display:block;font-weight:500;font-size:.78rem;opacity:.85;line-height:1.2}
.btn.sm{padding:8px 14px;font-size:.92rem;border-radius:10px}

/* hero */
.hero{position:relative;padding:72px 0 40px;overflow:hidden;
background-image:linear-gradient(var(--grid) 1px,transparent 1px),linear-gradient(90deg,var(--grid) 1px,transparent 1px);
background-size:28px 28px;background-position:center top}
.hero::after{content:"";position:absolute;inset:auto 0 0 0;height:160px;background:linear-gradient(transparent,var(--bg))}
.hero .wrap{position:relative;z-index:1}
.hero-text{max-width:760px;margin:0 auto;text-align:center}
.pill{display:inline-flex;align-items:center;gap:8px;padding:6px 14px 6px 8px;border-radius:999px;background:var(--panel);
border:1px solid var(--border);font-size:.86rem;font-weight:600;color:var(--muted)}
.pill b{background:var(--accent);color:var(--on-accent);border-radius:999px;padding:2px 9px;font-size:.78rem}
.pill:hover{text-decoration:none;border-color:var(--accent)}
.hero h1{font-size:clamp(2.1rem,5.4vw,3.6rem);margin:22px 0 16px}
.hero h1 em{font-style:normal;color:var(--accent)}
.lead{font-size:clamp(1.02rem,1.8vw,1.18rem);color:var(--muted);max-width:640px;margin:0 auto}
.cta{display:flex;flex-wrap:wrap;gap:12px;justify-content:center;margin:30px 0 14px}
.fine{font-size:.86rem;color:var(--faint)}
.badges{list-style:none;display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin:4px 0 0;padding:0}
.badges li{display:inline-flex;align-items:center;gap:7px;padding:6px 13px;border-radius:999px;background:var(--panel);
border:1px solid var(--border);font-size:.88rem;font-weight:600;color:var(--muted)}
.badges li.hi{background:var(--accent-soft);border-color:color-mix(in srgb,var(--accent) 30%,transparent);color:var(--accent)}
.band{padding:8px 0 0}
.open{display:grid;grid-template-columns:1.05fr 1fr;gap:36px;align-items:center;border-radius:24px;padding:46px;
color:#fff;background:radial-gradient(120% 140% at 0% 0%,#e0692a 0%,#c4521b 45%,#9c3d14 100%);
box-shadow:0 18px 40px rgba(156,61,20,.28)}
.open .kicker{color:#ffe0cc}
.open h2{color:#fff}
.open p{color:#fff3eb}
.open .cta{justify-content:flex-start;margin:26px 0 0}
.open ul{list-style:none;margin:0;padding:0;display:grid;gap:12px}
.open li{display:grid;grid-template-columns:44px 1fr;gap:14px;align-items:start;background:rgba(255,255,255,.1);
border:1px solid rgba(255,255,255,.18);border-radius:16px;padding:16px}
.open li .ic{display:grid;place-items:center;width:44px;height:44px;border-radius:12px;background:rgba(255,255,255,.16)}
.open li b{display:block;font-size:1.02rem}
.open li span{display:block;color:#ffe9dc;font-size:.93rem;margin-top:2px}
.btn.light{background:#fff;border-color:#fff;color:#9c3d14}
.btn.light:hover{background:#fff4ec;border-color:#fff4ec}
.btn.ghost{background:transparent;border-color:rgba(255,255,255,.55);color:#fff}
.btn.ghost:hover{border-color:#fff;background:rgba(255,255,255,.08)}
.hero .shot{margin-top:46px}

/* capturas */
.shot{margin:0;position:relative;border-radius:14px;overflow:hidden;border:1px solid var(--border);box-shadow:var(--shadow);
background:var(--panel2) center/cover no-repeat}
.shot img{display:block;width:100%;height:100%;opacity:0;transition:opacity .45s ease;cursor:zoom-in}
.shot img.ok{opacity:1}
.shot.small{border-radius:12px}

/* seções */
section{padding:72px 0}
.head{max-width:680px;margin-bottom:34px}
.head.center{margin-left:auto;margin-right:auto;text-align:center}
.kicker{display:block;font-size:.8rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--accent);
margin-bottom:10px}
.head p{color:var(--muted);margin-top:12px;font-size:1.05rem}
.alt{background:var(--panel);border-top:1px solid var(--border);border-bottom:1px solid var(--border)}
.grid{display:grid;gap:16px;grid-template-columns:repeat(auto-fill,minmax(250px,1fr))}
.card{background:var(--panel);border:1px solid var(--border);border-radius:16px;padding:22px}
.alt .card{background:var(--bg)}
.card .ic{display:grid;place-items:center;width:42px;height:42px;border-radius:12px;background:var(--accent-soft);
color:var(--accent);margin-bottom:14px}
.card p{color:var(--muted);font-size:.95rem;margin-top:6px}
.new{display:grid;grid-template-columns:1fr 1.15fr;gap:34px;align-items:center}
.new .grid{grid-template-columns:1fr 1fr;gap:12px}
.new .card{padding:18px}

/* galeria */
.tabs{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-bottom:22px}
.tabs button{font:inherit;font-size:.92rem;font-weight:600;padding:8px 15px;border-radius:999px;border:1px solid var(--border);
background:var(--panel);color:var(--muted);cursor:pointer}
.tabs button:hover{color:var(--text);border-color:var(--accent)}
.tabs button[aria-selected=true]{background:var(--accent);border-color:var(--accent);color:var(--on-accent)}
.stage{max-width:980px;margin:0 auto}
.stage .shot{display:none}.stage .shot.on{display:block}
.stage .shot.mid{max-width:620px;margin:0 auto}

/* guia */
.steps{list-style:none;margin:0;padding:0;counter-reset:s;display:grid;gap:16px}
.step{counter-increment:s;display:grid;grid-template-columns:52px 1fr;gap:18px;background:var(--panel);
border:1px solid var(--border);border-radius:16px;padding:22px}
.step::before{content:counter(s);display:grid;place-items:center;width:44px;height:44px;border-radius:12px;
background:var(--accent);color:var(--on-accent);font-weight:800;font-size:1.15rem}
.step p{color:var(--muted);margin-top:6px}
.step b{color:var(--text)}
.step.has-shot{grid-template-columns:52px 1fr minmax(0,380px);align-items:start}
.step.has-shot .shot{grid-column:3}

/* atalhos e perguntas */
.two{display:grid;grid-template-columns:1fr 1fr;gap:28px;align-items:start}
table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--border);border-radius:16px;
overflow:hidden;font-size:.93rem}
td{padding:11px 16px;border-top:1px solid var(--border);vertical-align:top}
tr:first-child td{border-top:none}
td:first-child{font-weight:650;white-space:nowrap;color:var(--text)}
td:last-child{color:var(--muted)}
details{background:var(--panel);border:1px solid var(--border);border-radius:14px;padding:0 18px;margin-bottom:10px}
summary{cursor:pointer;font-weight:650;padding:15px 0;list-style:none;display:flex;justify-content:space-between;gap:12px}
summary::-webkit-details-marker{display:none}
summary::after{content:"+";color:var(--accent);font-size:1.3rem;line-height:1}
details[open] summary::after{content:"−"}
details p{color:var(--muted);padding-bottom:16px;font-size:.95rem}

/* download */
.download{text-align:center;background:linear-gradient(135deg,var(--accent-soft),var(--panel));border:1px solid var(--border);
border-radius:24px;padding:56px 24px}
.download .cta{margin-top:26px}
.download ul{list-style:none;padding:0;margin:22px 0 0;display:flex;flex-wrap:wrap;gap:8px 22px;justify-content:center;
color:var(--muted);font-size:.92rem}
.download li{display:flex;align-items:center;gap:7px}
.download li .i{color:var(--accent)}

footer{padding:36px 0 48px;color:var(--faint);font-size:.9rem}
footer .wrap{display:flex;flex-wrap:wrap;gap:12px 24px;align-items:center;justify-content:space-between}
footer a{color:var(--muted)}

/* zoom */
dialog{border:none;padding:0;background:transparent;max-width:min(96vw,1600px);max-height:94vh}
dialog::backdrop{background:rgba(10,12,16,.82)}
dialog img{display:block;max-width:min(96vw,1600px);max-height:94vh;width:auto;height:auto;border-radius:10px;cursor:zoom-out}

@media (max-width:900px){.new,.two,.open{grid-template-columns:1fr}.open{padding:32px 24px}.step.has-shot{grid-template-columns:52px 1fr}
.step.has-shot .shot{grid-column:1/-1}nav a:not(.keep){display:none}}
@media (max-width:560px){.wrap{padding:0 16px}.hero{padding-top:48px}.new .grid{grid-template-columns:1fr}
.step{grid-template-columns:1fr;gap:12px}.step.has-shot{grid-template-columns:1fr}td:first-child{white-space:normal}
section{padding:56px 0}.bar{gap:12px}}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}.shot img,.btn{transition:none}}
"""

JS = r"""
(() => {
  const root = document.documentElement;
  // Tema: o do sistema, ou o escolhido no botão (guardado neste navegador).
  const media = matchMedia('(prefers-color-scheme: dark)');
  const isDark = () => root.dataset.theme ? root.dataset.theme === 'dark' : media.matches;
  const paint = () => isDark() ? root.setAttribute('data-dark', '') : root.removeAttribute('data-dark');
  try { const t = localStorage.getItem('autocadinho-tema'); if (t === 'dark' || t === 'light') root.dataset.theme = t; } catch (e) {}
  paint();
  media.addEventListener?.('change', paint);
  document.getElementById('tema').addEventListener('click', () => {
    root.dataset.theme = isDark() ? 'light' : 'dark';
    try { localStorage.setItem('autocadinho-tema', root.dataset.theme); } catch (e) {}
    paint();
  });

  // Capturas: o Base64 fica num bloco JSON no fim da página e só vira imagem quando é preciso.
  let data = null;
  const urls = {};
  const source = key => {
    if (urls[key]) return urls[key];
    data = data || JSON.parse(document.getElementById('capturas').textContent);
    const b64 = data[key];
    try {
      const bin = atob(b64), bytes = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      urls[key] = URL.createObjectURL(new Blob([bytes], {type: 'image/webp'}));
    } catch (e) {
      urls[key] = 'data:image/webp;base64,' + b64;
    }
    return urls[key];
  };
  const show = img => {
    if (img.dataset.done) return;
    img.dataset.done = '1';
    img.addEventListener('load', () => img.classList.add('ok'), {once: true});
    img.src = source(img.dataset.img);
  };
  const imgs = [...document.querySelectorAll('img[data-img]')];
  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver(entries => entries.forEach(e => {
      if (e.isIntersecting) { io.unobserve(e.target); show(e.target); }
    }), {rootMargin: '400px 0px'});
    imgs.forEach(img => io.observe(img));
  } else {
    imgs.forEach(show);
  }
  // Depois que tudo abriu, prepara as outras sem pressa (uma por vez, quando o navegador está livre).
  const idle = window.requestIdleCallback || (fn => setTimeout(fn, 300));
  addEventListener('load', () => {
    const rest = imgs.filter(img => !img.dataset.done);
    const next = () => { const img = rest.shift(); if (img) { show(img); idle(next); } };
    idle(next);
  });

  // Galeria
  const tabs = [...document.querySelectorAll('.tabs button')];
  tabs.forEach(tab => tab.addEventListener('click', () => {
    tabs.forEach(t => t.setAttribute('aria-selected', t === tab ? 'true' : 'false'));
    document.querySelectorAll('.stage .shot').forEach(f => {
      const on = f.id === tab.getAttribute('aria-controls');
      f.classList.toggle('on', on);
      if (on) show(f.querySelector('img'));
    });
  }));

  // Ver uma captura grande
  const zoom = document.getElementById('zoom'), big = zoom.querySelector('img');
  document.addEventListener('click', e => {
    const img = e.target.closest('.shot img');
    if (img && img.src && zoom.showModal) { big.src = img.src; big.alt = img.alt; zoom.showModal(); }
  });
  zoom.addEventListener('click', () => zoom.close());

  // Download: os links do HTML levam à página da última versão no GitHub (releases/latest), sem número fixo.
  // Se a API responder, viram o download direto do pacote mais novo, com versão e tamanho.
  fetch('https://api.github.com/repos/@@REPO@@/releases/latest', {headers: {Accept: 'application/vnd.github+json'}})
    .then(r => r.ok ? r.json() : Promise.reject(r.status))
    .then(rel => {
      const find = re => (rel.assets || []).find(a => re.test(a.name));
      const msi = find(/-windows-x64\.msi$/), zip = find(/-windows-x64\.zip$/);
      const mb = a => Math.max(1, Math.round(a.size / 1048576)) + ' MB';
      const version = String(rel.tag_name || '').replace(/^v/, '');
      if (version) document.querySelectorAll('[data-version]').forEach(e => e.textContent = 'Versão ' + version);
      if (msi) document.querySelectorAll('[data-dl=msi]').forEach(a => { a.href = msi.browser_download_url; });
      if (zip) document.querySelectorAll('[data-dl=zip]').forEach(a => { a.href = zip.browser_download_url; });
      if (msi) document.querySelectorAll('[data-size=msi]').forEach(e => e.textContent = ' · ' + mb(msi));
      if (zip) document.querySelectorAll('[data-size=zip]').forEach(e => e.textContent = ' · ' + mb(zip));
    })
    .catch(() => {});
})();
"""


def build(out: Path) -> int:
    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841 (os plugins de imagem precisam dele)
    big, meta = load_shots()
    repo = REPO_URL.removeprefix("https://github.com/")
    latest = f"{REPO_URL}/releases/latest"
    v = __version__

    def dl(kind: str, label: str, primary: bool) -> str:
        cls = "btn primary" if primary else "btn"
        return (f'<a class="{cls}" href="{latest}" data-dl="{kind}">{icon("download")}'
                f'<span>{label}<small><span data-version>Última versão</span> · .{kind}'
                f'<span data-size="{kind}"></span></small></span></a>')

    new_cards = "".join(f'<div class="card"><div class="ic">{icon(i)}</div><h3>{t}</h3><p>{d}</p></div>'
                        for i, t, d in NEW)
    features = "".join(f'<div class="card"><div class="ic">{icon(i)}</div><h3>{t}</h3><p>{d}</p></div>'
                       for i, t, d in FEATURES)
    tabs = "".join(f'<button type="button" role="tab" aria-controls="tela-{k}" aria-selected='
                   f'"{"true" if n == 0 else "false"}">{label}</button>' for n, (k, label) in enumerate(GALLERY))
    stage = "".join(shot(meta, k, ("on " if n == 0 else "") + ("mid" if k == "atualizar" else ""))
                    .replace('<figure ', f'<figure id="tela-{k}" role="tabpanel" ', 1)
                    for n, (k, _l) in enumerate(GALLERY))
    steps = []
    for title, text, img in STEPS:
        extra = shot(meta, img, "small") if img else ""
        steps.append(f'<li class="step{" has-shot" if img else ""}"><div><h3>{title}</h3><p>{text}</p></div>'
                     f'{extra}</li>')
    keys = "".join(f"<tr><td>{html.escape(k)}</td><td>{html.escape(d)}</td></tr>" for k, d in KEYS)
    faq = "".join(f"<details><summary>{q}</summary><p>{a}</p></details>" for q, a in FAQ)
    data = json.dumps(big, separators=(",", ":"))

    page = TEMPLATE
    favicon = "data:image/svg+xml;base64," + base64.b64encode(logo_svg(64).encode("utf-8")).decode("ascii")
    for token, value in {
        "@@FAVICON@@": favicon,
        "@@CSS@@": CSS.strip(), "@@JS@@": JS.strip().replace("@@REPO@@", repo), "@@LOGO32@@": logo_svg(32),
        "@@LOGO56@@": logo_svg(56), "@@HERO@@": shot(meta, "planta"), "@@NEWSHOT@@": shot(meta, "simbolos"),
        "@@NEW@@": new_cards, "@@FEATURES@@": features, "@@TABS@@": tabs, "@@STAGE@@": stage,
        "@@STEPS@@": "".join(steps), "@@KEYS@@": keys, "@@FAQ@@": faq, "@@DATA@@": data,
        "@@DL_MSI@@": dl("msi", "Baixar para Windows", True), "@@DL_ZIP@@": dl("zip", "Versão portátil", False),
        "@@DL_MSI_SM@@": f'<a class="btn primary sm" href="{latest}" data-dl="msi">{icon("download", 18)}Baixar</a>',
        "@@REPO_URL@@": REPO_URL, "@@LATEST@@": latest, "@@APP@@": APP_NAME, "@@VERSION@@": v, "@@DATE@@": __date__,
        "@@I_GITHUB@@": icon("github", 18), "@@I_SUN@@": icon("sun", 18).replace('class="i"', 'class="i sun"'),
        "@@I_MOON@@": icon("moon", 18).replace('class="i"', 'class="i moon"'), "@@I_WIN@@": icon("shield", 18),
        "@@I_CODE@@": icon("code", 18), "@@I_GLOBE@@": icon("globe", 18), "@@I_ARROW@@": icon("arrow", 18),
        "@@I_GIFT@@": icon("gift", 18), "@@I_WINDOWS@@": icon("windows", 18), "@@I_FOLDER@@": icon("folder", 18),
    }.items():
        page = page.replace(token, value)
    leftover = [t for t in page.split("@@")[1::2] if t.isupper() and len(t) < 20]
    if leftover:
        raise SystemExit(f"Marcadores sem valor: {leftover}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8", newline="\n")
    kb = len(page.encode("utf-8")) / 1024
    print(f"{out} ({kb:.0f} KB, {len(big)} capturas)")
    return 0


TEMPLATE = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>@@APP@@: desenhos de obra simples, grátis e de código aberto</title>
<meta name="description" content="Programa grátis e de código aberto para Windows para desenhar plantas de obra simples: vigas, pilares,
paredes, portas, janelas e medidas em centímetros de verdade, prontas para imprimir em escala.">
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#e8722c">
<link rel="icon" href="@@FAVICON@@">
<style>
@@CSS@@
</style>
</head>
<body>
<a class="skip" href="#conteudo">Pular para o conteúdo</a>
<header>
  <div class="wrap bar">
    <a class="brand" href="#">@@LOGO32@@<span>@@APP@@</span></a>
    <nav aria-label="Seções">
      <a href="#aberto">Grátis e aberto</a>
      <a href="#novidades">Novidades</a>
      <a href="#recursos">Recursos</a>
      <a href="#telas">Telas</a>
      <a href="#guia">Como usar</a>
      <a href="#perguntas">Perguntas</a>
    </nav>
    @@DL_MSI_SM@@
    <a class="iconbtn" href="@@REPO_URL@@" title="Código no GitHub" aria-label="Código no GitHub">@@I_GITHUB@@</a>
    <button class="iconbtn" id="tema" type="button" title="Tema claro ou escuro" aria-label="Trocar o tema">@@I_MOON@@@@I_SUN@@</button>
  </div>
</header>

<main id="conteudo">
<div class="hero">
  <div class="wrap">
    <div class="hero-text">
      <a class="pill" href="#novidades"><b>Novo</b> Versão @@VERSION@@: portas, janelas, formas e atualização automática</a>
      <h1>Desenhos de obra simples, <em>com as medidas certas</em>.</h1>
      <p class="lead">O @@APP@@ é um programa pequeno e fácil, <b>grátis e de código aberto</b>, para plantas de obra:
      vigas, pilares, paredes, portas, janelas e medidas em centímetros de verdade, prontos para imprimir em escala.
      Feito para quem desenhava no Paint.</p>
      <div class="cta">
        @@DL_MSI@@
        <a class="btn" href="#guia">@@I_ARROW@@<span>Ver como usar<small>Guia passo a passo</small></span></a>
      </div>
      <ul class="badges">
        <li class="hi">@@I_GIFT@@ 100% grátis</li>
        <li class="hi">@@I_CODE@@ Código aberto (MIT)</li>
        <li>@@I_WIN@@ Sem cadastro e sem anúncios</li>
        <li>@@I_WINDOWS@@ Windows 10 e 11</li>
      </ul>
    </div>
    @@HERO@@
  </div>
</div>

<section id="aberto" class="band">
  <div class="wrap">
    <div class="open">
      <div>
        <span class="kicker">Grátis e de código aberto</span>
        <h2>Grátis de verdade, sem pegadinha</h2>
        <p style="margin-top:14px">O @@APP@@ não tem versão paga, período de teste, anúncio nem cadastro. E o código é
        aberto, sob a licença MIT: qualquer pessoa pode ver como ele funciona, usar, copiar, mudar e compartilhar.</p>
        <div class="cta">
          <a class="btn light" href="@@REPO_URL@@">@@I_GITHUB@@<span>Ver o código no GitHub</span></a>
          <a class="btn ghost" href="@@REPO_URL@@/blob/main/LICENSE">@@I_CODE@@<span>Licença MIT</span></a>
        </div>
      </div>
      <ul>
        <li><span class="ic">@@I_GIFT@@</span><div><b>Sem custo nenhum</b><span>Sem versão paga, sem teste de 30 dias e
        sem anúncios. Use quanto quiser, em quantos computadores quiser.</span></div></li>
        <li><span class="ic">@@I_CODE@@</span><div><b>Código aberto</b><span>Todo o código está no GitHub: dá para
        conferir o que o programa faz, sugerir melhorias ou adaptar para o seu uso.</span></div></li>
        <li><span class="ic">@@I_FOLDER@@</span><div><b>Seus desenhos são seus</b><span>Os arquivos ficam no seu
        computador, num formato aberto e documentado. Nada do que você desenha vai para a internet.</span></div></li>
      </ul>
    </div>
  </div>
</section>

<section id="novidades">
  <div class="wrap new">
    <div>
      <div class="head">
        <span class="kicker">Novidades da versão 1.1</span>
        <h2>Portas, janelas e formas, do jeito de uma planta de verdade</h2>
        <p>Os símbolos de sempre entram com um clique, as formas mostram a área e o programa passa a se atualizar sozinho.</p>
      </div>
      <div class="grid">@@NEW@@</div>
    </div>
    @@NEWSHOT@@
  </div>
</section>

<section id="recursos" class="alt">
  <div class="wrap">
    <div class="head center">
      <span class="kicker">Recursos</span>
      <h2>Tudo o que um desenho de obra precisa, e nada que atrapalhe</h2>
      <p>O @@APP@@ não tenta ser um AutoCAD. Ele faz bem o desenho simples: medida certa, nome no lugar e folha
      pronta para a obra.</p>
    </div>
    <div class="grid">@@FEATURES@@</div>
  </div>
</section>

<section id="telas">
  <div class="wrap">
    <div class="head center">
      <span class="kicker">Telas</span>
      <h2>Veja o programa por dentro</h2>
      <p>Clique numa imagem para ver maior.</p>
    </div>
    <div class="tabs" role="tablist" aria-label="Telas do programa">@@TABS@@</div>
    <div class="stage">@@STAGE@@</div>
  </div>
</section>

<section id="guia" class="alt">
  <div class="wrap">
    <div class="head">
      <span class="kicker">Como usar</span>
      <h2>Do primeiro traço à folha impressa</h2>
      <p>O mesmo passo a passo está dentro do programa: aperte <kbd>F1</kbd>. O guia completo, com todas as
      ferramentas, está no <a href="@@REPO_URL@@/blob/main/docs/GUIA.md">GitHub</a>.</p>
    </div>
    <ol class="steps">@@STEPS@@</ol>
  </div>
</section>

<section id="perguntas">
  <div class="wrap two">
    <div>
      <div class="head">
        <span class="kicker">Atalhos</span>
        <h2>Mouse e teclado</h2>
      </div>
      <table><tbody>@@KEYS@@</tbody></table>
    </div>
    <div>
      <div class="head">
        <span class="kicker">Perguntas</span>
        <h2>Dúvidas comuns</h2>
      </div>
      @@FAQ@@
    </div>
  </div>
</section>

<section id="baixar">
  <div class="wrap">
    <div class="download">
      @@LOGO56@@
      <h2 style="margin-top:16px">Baixe o @@APP@@</h2>
      <p class="lead" style="margin-top:10px">O instalador não pede senha de administrador e coloca o programa no Menu
      Iniciar. Prefere sem instalar? Use a versão portátil: é só extrair e abrir.</p>
      <div class="cta">@@DL_MSI@@ @@DL_ZIP@@</div>
      <ul>
        <li>@@I_WIN@@ Windows 10 e 11, 64 bits</li>
        <li>@@I_GLOBE@@ Português e inglês</li>
        <li>@@I_GIFT@@ 100% grátis</li>
        <li>@@I_CODE@@ Código aberto (MIT)</li>
      </ul>
      <p class="fine" style="margin-top:18px">Todas as versões e o SHA256SUMS.txt para conferir os arquivos estão na
      <a href="@@REPO_URL@@/releases">página de versões</a>.</p>
    </div>
  </div>
</section>
</main>

<footer>
  <div class="wrap">
    <span>@@APP@@ @@VERSION@@ · @@DATE@@ · Grátis e de código aberto (licença MIT) · Feito com Python e Qt</span>
    <a href="@@REPO_URL@@">@@I_GITHUB@@ Código no GitHub</a>
  </div>
</footer>

<dialog id="zoom" aria-label="Captura ampliada"><img alt=""></dialog>
<script id="capturas" type="application/json">@@DATA@@</script>
<script>
@@JS@@
</script>
</body>
</html>
"""


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "site" / "index.html"
    return build(out)


if __name__ == "__main__":
    sys.exit(main())
