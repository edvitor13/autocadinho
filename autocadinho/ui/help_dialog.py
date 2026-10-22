"""Janela "Como usar": o passo a passo, as ferramentas e os atalhos do teclado (F1)."""

from __future__ import annotations

from html import escape

from PySide6.QtWidgets import QDialog, QHBoxLayout, QPushButton, QTextBrowser, QVBoxLayout, QWidget

from .. import APP_NAME
from ..i18n import N_, _
from . import theme

SECTIONS = [
    (N_("Começando"), [
        N_("Na tela inicial, clique em <b>Novo desenho</b>. A folha quadriculada é a área de desenho: cada "
           "quadradinho vale alguns centímetros da obra, e as medidas saem certas sozinhas."),
        N_("Escolha a ferramenta na coluna da esquerda e desenhe na folha. Para ver como fica um desenho pronto, "
           "abra o <b>exemplo</b> na tela inicial."),
    ]),
    (N_("Desenhando"), [
        N_("<b>Viga</b>: clique onde ela começa e arraste até onde termina. Cada viga ganha um nome (VIGA 1, "
           "VIGA 2…). As vigas ficam retas na horizontal ou na vertical; segure <b>Shift</b> para fazer inclinada."),
        N_("<b>Pilar</b>: clique para colocar. Ele encaixa nas pontas, nos cantos e no meio das vigas. A tecla "
           "<b>R</b> deixa o pilar em pé ou deitado antes de colocar."),
        N_("<b>Medida</b>: arraste do começo ao fim do que quer medir. O valor é calculado e escrito sozinho; "
           "depois, arraste a bolinha do meio para afastar a linha da medida."),
        N_("<b>Texto</b>: clique onde ele vai ficar, escreva e aperte <b>Enter</b>. <b>Linha</b> e "
           "<b>Retângulo</b> servem para escadas, aberturas, lajes e detalhes."),
    ]),
    (N_("Ajustando"), [
        N_("Com a ferramenta <b>Selecionar</b>, clique num desenho para escolher. O painel da direita mostra as "
           "medidas exatas: digite o comprimento certo (por exemplo, 3,50 m) e o desenho acompanha."),
        N_("Arraste para mover. Arraste as bolinhas das pontas para esticar ou encurtar. Arraste o nome de uma "
           "viga ou de um pilar para tirá-lo de cima de outro desenho. Duplo clique muda um nome ou um texto."),
        N_("Errou? <b>Ctrl+Z</b> desfaz (quantas vezes precisar) e <b>Ctrl+Y</b> refaz. A <b>Borracha</b> apaga "
           "o que você clicar."),
    ]),
    (N_("Salvando e imprimindo"), [
        N_("<b>Salvar</b> guarda o desenho num arquivo .cadinho, para continuar depois. Os desenhos salvos "
           "aparecem na tela inicial, com uma miniatura."),
        N_("Enquanto você desenha, o Autocadinho guarda uma cópia de segurança. Se o computador desligar "
           "sem salvar, ele oferece recuperar o desenho na próxima vez que abrir."),
        N_("<b>Imprimir</b> mostra a folha como vai sair. Escolha o papel e a escala: \"Ajustar à folha\" usa a "
           "folha toda; numa escala exata, como 1:50, dá para medir no papel com a régua (1 cm = 50 cm). "
           "Dali também dá para salvar em PDF ou como imagem, para mandar por e-mail ou WhatsApp."),
    ]),
]

SHORTCUTS = [
    ("S · V · P · L · Q · M · T · E · H", N_("Ferramentas: Selecionar, Viga, Pilar, Linha, Retângulo, Medida, "
                                            "Texto, Borracha e Mover a folha")),
    ("Esc", N_("Cancela o que está fazendo e volta para Selecionar")),
    ("Shift", N_("Enquanto desenha: viga ou linha inclinada; no retângulo, um quadrado")),
    ("Alt", N_("Enquanto desenha ou move: solta o encaixe")),
    ("R", N_("Gira o que está selecionado (ou o próximo pilar)")),
    (N_("Setas"), N_("Movem o que está selecionado (com Shift, 10 vezes mais)")),
    ("Delete", N_("Apaga o que está selecionado")),
    ("Ctrl+Z · Ctrl+Y", N_("Desfaz e refaz")),
    ("Ctrl+C · Ctrl+V · Ctrl+D", N_("Copia, cola e duplica")),
    ("Ctrl+S · Ctrl+O · Ctrl+P", N_("Salva, abre e imprime")),
    (N_("Rodinha do mouse"), N_("Aproxima e afasta")),
    (N_("Espaço + arrastar"), N_("Move a folha (o botão do meio do mouse também)")),
    ("Ctrl+0", N_("Mostra o desenho inteiro")),
]


def help_html() -> str:
    t = theme.current()
    parts = [f"<style>h2 {{ color: {t.text}; margin-top: 18px; margin-bottom: 6px; font-size: 13pt; }} "
             f"p {{ color: {t.text}; margin: 0 0 8px 0; line-height: 140%; }} "
             f"td {{ padding: 5px 14px 5px 0; color: {t.text}; vertical-align: top; }} "
             f"td.k {{ color: {t.accent}; font-weight: 600; white-space: nowrap; }}</style>"]
    for title, paragraphs in SECTIONS:
        parts.append(f"<h2>{escape(_(title))}</h2>")
        parts += [f"<p>{_(p)}</p>" for p in paragraphs]
    parts.append(f"<h2>{escape(_('Mouse e teclado'))}</h2><table>")
    for keys, text in SHORTCUTS:
        parts.append(f"<tr><td class='k'>{escape(_(keys))}</td><td>{escape(_(text))}</td></tr>")
    parts.append("</table>")
    return "".join(parts)


class HelpDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("Como usar o {app}").format(app=APP_NAME))
        self.resize(720, 680)
        col = QVBoxLayout(self)
        col.setContentsMargins(18, 18, 18, 14)
        col.setSpacing(12)
        view = QTextBrowser()
        view.setOpenExternalLinks(True)
        view.setHtml(help_html())
        col.addWidget(view, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        ok = QPushButton(_("Fechar"))
        ok.setObjectName("Primary")
        ok.setMinimumWidth(120)
        ok.clicked.connect(self.accept)
        row.addWidget(ok)
        col.addLayout(row)
