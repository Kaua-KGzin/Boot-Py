# Changelog

Todas as mudancas relevantes deste projeto sao registradas aqui.

## [1.1.0] - 2026-03-03
### Adicionado
- CLI robusta com comandos `init-config`, `validate-config`, `show-config`, `run` e `schedule`.
- Modelo de configuracao com validacao, defaults e saida normalizada.
- Upload opcional para S3 com relatorio de sucesso/falha.
- Politica de retencao para artefatos e relatorios.
- Modo `dry-run` e suporte a `exclude_patterns`.
- Logging com arquivo rotativo.
- Testes automatizados com `unittest`.
- Pipeline CI para validacao automatica.
- Guias de contribuicao, commits PT_BR e exemplos praticos.

### Alterado
- Mensagens de CLI/log e documentacao convertidas para PT_BR.
- Hash de integridade padrao mantido em `sha256`.
- README reestruturado com foco em operacao real e publicacao.

### Corrigido
- Retencao aplicada apos geracao do relatorio, evitando acumulacao indevida.
