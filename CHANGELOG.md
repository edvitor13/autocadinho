# Histórico de versões

Todas as mudanças de cada versão do Autocadinho. O formato segue o
[Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/), e as versões seguem o
[Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não publicado]

### Correções

- Depois de instalar uma atualização, o pacote baixado e a pasta extraída do `.zip` são apagados da pasta
  temporária (ficam só os registros), e as pastas de atualizações anteriores são apagadas no download seguinte.

## [1.1.0] - 2026-10-22

### Novidades

- **Símbolos:** porta, porta dupla, porta de correr, janela, escada, vaso sanitário, pia, chuveiro e o norte.
  Portas e janelas encaixam em cima de uma viga ou linha, seguem a direção dela e abrem o vão na parede; a tecla
  R vira o lado. No painel: largura do vão, espessura da parede, lado da dobradiça, para onde abre, degraus da
  escada e o sentido dela.
- **Formas:** círculo (e elipse), triângulo e polígono ponto a ponto, para terrenos e cômodos tortos. O
  retângulo, o círculo e o polígono mostram a **área** em m², e o polígono, o perímetro e a medida de cada lado.
- **Fontes:** a fonte do desenho (nomes e medidas) e a de cada texto, escolhidas entre as instaladas, com
  prévia na lista; **itálico** nos textos.
- **Setas** no começo e no fim das linhas.
- **Atualização automática:** o app procura uma versão nova ao abrir (no máximo uma vez por dia, sem enviar
  nada), mostra as novidades e instala com um clique. Baixa o `.msi` ou o `.zip`, conforme a instalação,
  confere o SHA-256 e abre de novo sozinho. Dá para pular uma versão ou desligar a busca no menu `⋯`.
- Na coluna de ferramentas, **Formas** e **Símbolos** abrem um menu com as opções; a coluna rola em telas
  baixas.
- Ajuda (F1), guias e capturas de tela com as novidades.

### Mudanças

- O executável agora leva o módulo `ssl` (HTTPS para o atualizador) e um marcador
  `autocadinho-install.json` com o tipo de instalação.
- Novos tipos e campos no arquivo `.cadinho`, sem mudar o `format` (a 1.0 abre os arquivos novos sem os
  elementos novos). Detalhes em `docs/FORMATO.md`.

## [1.0.0] - 2026-10-22

Primeira versão.

### Desenho

- Ferramentas: Viga, Pilar, Linha (tracejada ou não), Retângulo (tracejado, preenchido, com medidas dos lados),
  Medida (calculada sozinha ou com texto próprio), Texto (deitado ou em pé, negrito), Borracha e Mover folha.
- Desenho em centímetros de verdade, com medidas em metros ou centímetros.
- Encaixe nas pontas, nos meios, nos cantos, ao longo das vigas e na grade; retas a 90° (Shift inclina; Alt solta
  o encaixe).
- Nomes automáticos (VIGA 1, P1…) com a palavra escolhida em cada desenho, ou sem nome; nomes arrastáveis e em pé.
- Painel com as medidas exatas, a espessura, sete cores prontas e qualquer outra cor; vários itens de uma vez.
- Selecionar por clique ou por área, mover, esticar pelas alças, girar 90°, copiar, colar, duplicar, trazer para a
  frente e mandar para trás; setas do teclado para ajustes finos.
- Desfazer e refazer até 300 passos.

### Arquivos

- Desenhos em arquivos `.cadinho` (JSON, descrito em `docs/FORMATO.md`) com miniatura, gravados de forma atômica.
- Tela inicial com os desenhos recentes; abrir arrastando o arquivo para a janela ou com dois cliques.
- Cópia de segurança alguns segundos depois de cada mudança, oferecida na abertura se o computador desligou sem salvar.

### Impressão

- Papéis A4, A3, A2, Carta e Ofício; folha automática, deitada ou em pé.
- Ajustar à folha ou escala exata (1:10 a 1:200), com a sugestão da maior escala que cabe.
- Título e data no alto, escala no rodapé, opção tudo em preto; prévia igual ao papel.
- Salvar a folha em PDF ou imagem PNG.

### Interface

- Tema claro (padrão) e escuro, com a barra de título do Windows acompanhando.
- Português do Brasil e inglês, escolhidos na primeira vez e trocáveis a qualquer momento sem perder o desenho.
- Ajuda "Como usar" (F1) com o passo a passo e os atalhos; desenho de exemplo.

### Para Windows

- Instalador `.msi` por usuário (sem administrador), com atalhos e associação dos `.cadinho`, e `.zip` portátil.

[1.1.0]: https://github.com/edvitor13/autocadinho/releases/tag/v1.1.0
[1.0.0]: https://github.com/edvitor13/autocadinho/releases/tag/v1.0.0
