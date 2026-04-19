# Portfólio do VW

Site pessoal construído com [Quarto](https://quarto.org) e publicado em [vitorwilher.github.io](https://vitorwilher.github.io).

---

## Estrutura de arquivos

```
Github_Portfolio/
│
├── _quarto.yml          # cérebro do site: tema, navbar, configurações globais
├── index.qmd            # página inicial (Home)
├── cv.qmd               # página do CV
├── styles.css           # customizações visuais
│
├── images/              # fotos e imagens
│
├── blog/
│   └── posts/           # cada arquivo .qmd ou .Rmd aqui = um post
│
├── projects/            # cada arquivo .qmd aqui = um projeto no grid
│
├── teaching/            # cada arquivo .qmd aqui = um curso na lista
│
└── research/            # cada arquivo .qmd aqui = uma pesquisa na lista
```

---

## Como adicionar conteúdo

Qualquer seção funciona igual — crie um arquivo `.qmd` na pasta certa com este cabeçalho:

```yaml
---
title: "Título do item"
date: "2026-04-19"
categories: [R, Economia]
description: "Breve descrição."
---

Conteúdo em markdown ou com código R/Python aqui.
```

O Quarto automaticamente inclui o arquivo na listagem da seção correspondente.

Para posts do blog, você pode usar `.Rmd` também — o código R é executado normalmente.

---

## Fluxo de trabalho

1. **Editar** — crie ou edite arquivos `.qmd` / `.Rmd` nas pastas acima
2. **Visualizar localmente** — rode no terminal:
   ```bash
   quarto preview
   ```
   O site abre no browser com live reload automático.
3. **Publicar** — faça commit e push para o branch `master`:
   ```bash
   git add .
   git commit -m "descrição da mudança"
   git push origin master
   ```
   O GitHub Actions detecta o push, renderiza o site e publica em `vitorwilher.github.io` automaticamente (~3-5 min).

---

## Observações

- `_freeze/` — cache de execução de código R/Python; não apagar
- `_site/` — site renderizado localmente; não commitar (já está no `.gitignore`)
- Para adicionar pacotes R usados nos posts, incluir em `.github/workflows/publish.yml`
