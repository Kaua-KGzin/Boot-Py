# Guia de Contribuicao

Obrigado por contribuir com o Boot-Py.

## Fluxo recomendado
1. Criar branch de trabalho:
   - `git checkout -b feat/minha-melhoria`
2. Implementar mudancas com foco em clareza e testes.
3. Rodar validacoes locais:
   - `python backup_bot.py validate-config`
   - `python -m unittest discover -s tests -v`
4. Fazer commit no padrao PT_BR:
   - `tipo(escopo): descricao em pt_br`
5. Abrir Pull Request com contexto tecnico objetivo.

## Padrao de commits
Consulte: [`docs/PADRAO_COMMITS_PT_BR.md`](docs/PADRAO_COMMITS_PT_BR.md)

## Qualidade minima
- Nao quebrar testes existentes.
- Adicionar testes ao alterar comportamento.
- Atualizar `README.md` e `CHANGELOG.md` quando aplicavel.
- Evitar mudancas sem justificativa tecnica.
