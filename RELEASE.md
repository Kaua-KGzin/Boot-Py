# Guia de Release (PT_BR)

Este documento define um processo simples e repetivel para gerar releases com qualidade.

## 1. Checklist pre-release
- Executar testes:
  - `python -m unittest discover -s tests -v`
- Validar configuracao:
  - `python backup_bot.py validate-config`
- Confirmar versao:
  - `backup_bot.py` (`VERSION`)
  - `pyproject.toml` (`project.version`)
- Atualizar changelog:
  - `CHANGELOG.md`

## 2. Padrao de commit PT_BR
Formato recomendado:
```text
tipo(escopo): descricao em pt_br
```

Exemplos:
- `feat(cli): adiciona validacao detalhada de configuracao`
- `fix(retencao): corrige limpeza de relatorios antigos`
- `docs(readme): detalha instalacao e exemplos praticos`
- `test(backup): cobre cenario de dry_run e compressao`
- `chore(ci): atualiza pipeline de testes`

Tipos sugeridos:
- `feat`, `fix`, `docs`, `test`, `chore`, `refactor`, `perf`, `build`, `ci`

## 3. Commit de release
```bash
git add .
git commit -m "chore(release): prepara versao vX.Y.Z"
```

## 4. Tag da release
```bash
git tag -a vX.Y.Z -m "release: boot-py vX.Y.Z"
```

## 5. Push de branch e tag
```bash
git push origin main
git push origin vX.Y.Z
```

## 6. Publicacao no GitHub
- Abrir o repositorio.
- Ir em `Releases` > `Draft a new release`.
- Selecionar a tag `vX.Y.Z`.
- Titulo sugerido: `Boot-Py vX.Y.Z`.
- Copiar os destaques do `CHANGELOG.md`.
- Publicar release.

## 7. (Opcional) Publicar pacote
```bash
python -m pip install --upgrade build twine
python -m build
python -m twine check dist/*
python -m twine upload dist/*
```
