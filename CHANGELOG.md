# Histórico de versões

Todas as mudanças de cada versão do Autocadinho. O formato segue o
[Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/), e as versões seguem o
[Versionamento Semântico](https://semver.org/lang/pt-BR/).

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

[1.0.0]: https://github.com/edvitor13/autocadinho/releases/tag/v1.0.0
