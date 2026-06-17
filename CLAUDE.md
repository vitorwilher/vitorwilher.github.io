# CLAUDE.md

Site pessoal / portfólio de **Vítor Wilher** (Cientista de Dados & Mestre em Economia), construído com [Quarto](https://quarto.org) e publicado em [vitorwilher.github.io](https://vitorwilher.github.io).

## O que é este repositório

Website estático Quarto (`project: type: website`). Cada seção é uma pasta com um `index.qmd` que gera uma listagem automática; cada `.qmd`/`.Rmd` dentro da pasta vira um item dessa listagem.

```
_quarto.yml          # config global: tema, navbar, output-dir, freeze
index.qmd            # Home
cv.qmd  /  cv.pdf     # CV (fonte .qmd + PDF gerado)
styles.css           # CSS customizado (tema base: cosmo)
images/              # imagens do site
blog/posts/          # cada .qmd/.Rmd = um post
projetos/            # cada .qmd = um projeto no grid
teaching/            # cada .qmd = um curso
research/            # cada .qmd = uma pesquisa (papers em PDF acompanham)
```

## Build e publicação

- **Output**: `_site/` (gerado localmente, no `.gitignore` — nunca commitar).
- **Cache**: `_freeze/` guarda resultados de execução de código R/Python (`execute: freeze: auto`). Não apagar.
- **Publicação**: push para `master` dispara o GitHub Actions ([.github/workflows/publish.yml](.github/workflows/publish.yml)), que renderiza com Quarto + R 4.4 e publica no branch `gh-pages` (~3–5 min). Pacotes R novos usados em posts precisam ser adicionados ao `setup-r-dependencies` desse workflow.

## Convenções

- Cabeçalho YAML padrão de um item de seção:
  ```yaml
  ---
  title: "Título"
  date: "2026-04-19"
  categories: [R, Economia]
  description: "Breve descrição."
  ---
  ```
- Idioma do conteúdo: **português (pt-BR)**.
- `ROI_Diagnostico/` está deliberadamente excluída do repositório via `.gitignore`.

## Regras de trabalho (importante)

- **Render do Quarto só com pedido explícito.** Nunca renderizar (`quarto render`/`quarto preview`) de forma reflexiva após editar. Aguardar o usuário pedir ("renderiza", "manda bala"). Quando solicitado, rodar via terminal integrado.
- **Fluxo de publicação**: o usuário edita localmente e pede ao Claude para fazer `git add`/`commit`/`push origin master`. Só commitar/fazer push quando pedido.
- **Terminologia técnica**: o usuário é economista (política monetária, séries temporais). Usar notação precisa (Δ, p.p., β̂, R²) sem simplificar.

## Notas

- Permissões locais de ferramentas: [.claude/settings.local.json](.claude/settings.local.json).
- Há um `.venv` Python e um `.env` na raiz (não versionados).
