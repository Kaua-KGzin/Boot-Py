# Padrao de Commits PT_BR

## Formato
```text
tipo(escopo): descricao em pt_br
```

## Regras
- Use verbos no presente: `adiciona`, `corrige`, `melhora`.
- Escopo curto e tecnico: `cli`, `docs`, `backup`, `retencao`, `ci`.
- Mensagem objetiva, sem pontuacao final.

## Tipos sugeridos
- `feat`: nova funcionalidade
- `fix`: correcao de bug
- `docs`: documentacao
- `test`: testes
- `chore`: tarefas de manutencao
- `refactor`: refatoracao sem alterar regra de negocio
- `perf`: melhoria de desempenho
- `ci`: mudancas no pipeline
- `build`: mudancas de empacotamento/dependencias

## Exemplos
- `feat(backup): adiciona suporte a exclusao por padroes`
- `fix(retencao): corrige remocao de relatorio antigo`
- `docs(readme): detalha fluxo de deploy no github`
- `test(cli): cobre validacao de config invalida`
- `chore(ci): executa testes em multiplas versoes de python`
