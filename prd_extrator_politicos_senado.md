# PRD: Extrator de Políticos (Senado Federal)

**Labels:** `ready-for-agent`, `etl`, `worker`

---

## Problem Statement

O sistema necessita de uma rotina automatizada e isolada para popular a tabela `senado_politicos` no Supabase com os dados atualizados dos Senadores da República (Legislatura 57). 

Diferentemente da Câmara, a API de Dados Abertos do Senado retorna os dados primariamente em XML e utiliza uma lógica de histórico de mandatos/exercícios mais complexa. 

A ausência de uma rotina adaptada a essas particularidades impossibilitará a expansão da plataforma para cobrir todo o Congresso Nacional.

---

## Solution

Criar um script Python puro (`extrator_senadores.py`), rodando de forma procedimental (padrão Pipe and Filter) via cron no container do Worker.

O script acessará a API do Senado forçando o formato JSON por meio de headers. Em vez de realizar requisições individuais (N+1), ele aproveitará a riqueza do endpoint de lista da legislatura 57 para buscar todos os dados (nome, partido, UF, foto e status) em uma única chamada de rede resiliente (com retries e backoff).

O status do mandato será decodificado a partir da chave `Participacao`. 

Os dados serão limpos, transformados para o schema exato do banco e enviados à tabela `senado_politicos` do Supabase por meio de um Bulk Upsert via SDK Oficial. O status da rotina será persistido na tabela `etl_logs`.

---

## User Stories

1. Como administrador do sistema, quero que o script de extração seja executado em background via agendador do sistema (cron), para manter a arquitetura alinhada com o extrator da Câmara e sem Celery.
2. Como engenheiro de dados, quero que a chamada à API do Senado exija explicitamente o formato JSON (adicionando o sufixo `.json` na URL e o header `Accept: application/json`), para evitar o uso e o overhead de parsers XML pesados.
3. Como engenheiro de dados, quero extrair os dados da rota de legislatura completa (`/senador/lista/legislatura/57.json`), para garantir a captação de titulares, suplentes e afastados em uma única requisição (eliminando o problema N+1).
5. Como engenheiro de dados, quero que a chamada de rede à API do Senado conte com o mesmo mecanismo de repetição (`_fetch_com_retry`) com no máximo 3 tentativas e backoff exponencial, para tolerar falhas temporárias do provedor governamental.
6. Como analista de domínio, quero que o status "Ativo" seja mapeado se o Senador for listado como "Titular" sem data de fim de exercício, para refletir com fidelidade o enum da base de dados.
7. Como analista de domínio, quero que o status "Suplente" seja mapeado se a participação for listada ativamente como suplência em exercício, garantindo a coerência do mandato.
8. Como analista de domínio, quero que termos como "Afastado", "Renúncia" ou "Fora de Exercício" sejam convertidos unicamente para "Inativo", padronizando os registros com o que foi feito na Câmara.
9. Como desenvolvedor, quero que as propriedades recebidas (NomeParlamentar, SiglaPartidoParlamentar, etc.) passem por um mapeamento estrito para o schema padrão (`nome_urna`, `partido`), isolando as chaves nativas do Senado.
10. Como administrador de banco de dados, quero que o script faça um único envio transacional (Bulk Upsert) da lista final validada para a tabela `senado_politicos`, preservando a cota de tráfego do banco.
11. Como desenvolvedor, quero que ao final da execução, os metadados sejam registrados com data_inicio e data_fim (em UTC), status ("Concluído" ou "Erro") e total de `linhas_afetadas` na tabela `etl_logs`.

---

## Implementation Decisions

### Infraestrutura e Reuso
- Criação do módulo `etl/extrator_senadores.py`.
- O código reutilizará os mesmos padrões estruturais do extrator de deputados (isolado, try/except global).

### Conexão de Rede e Otimização
- **Endpoint Principal:** `https://legis.senado.leg.br/dadosabertos/senador/lista/legislatura/57.json`
- **Headers:** `{"Accept": "application/json"}`.
- Ao contrário da Câmara, não faremos paginação sequencial e nem iteração em loop de detalhes individuais, pois o array retornado por esta URL contém todas as informações requeridas. 

### Transform e Mapeamento de Domínio
- O dicionário persistido terá a seguinte estrutura rígida:
  - `id` (ID original da API do Senado)
  - `nome_civil` (NomeCompletoParlamentar)
  - `nome_urna` (NomeParlamentar)
  - `partido` (SiglaPartidoParlamentar)
  - `cargo = 'Senador'` (Hardcoded)
  - `estado` (UfParlamentar)
  - `url_foto` (UrlFotoParlamentar)
  - `status_mandato` (Ativo, Suplente ou Inativo, calculado via chave `Exercicio`)
  - `data_ultima_atualizacao` (datetime.now(timezone.utc).isoformat())

### Load (Supabase)
- A persistência utilizará a SDK do Supabase em Python: `supabase.table('senado_politicos').upsert(lista_senadores).execute()`.
- O registro final ocorrerá em `etl_logs` mapeando o `nome_rotina` como `"extrator_senadores"`.

---

## Testing Decisions

### Princípio do TDD (Tracer Bullet Vertical)
- Os testes seguirão a regra RED-GREEN-REFACTOR construindo fatias de funcionamento que validam o comportamento final da extração, sem focar nos detalhes internos.

### Cobertura Mínima Exigida
1. **Teste de Conversão de Status:** Validar os três ramos da árvore de decisão do Senado (Titular -> Ativo, Suplente em exercício -> Suplente, Afastado -> Inativo).
3. **Teste de Resiliência de Rede:** Simular erro 500 usando `respx`, verificar o sleep e a recuperação na última tentativa.
4. **Teste End-to-End do Pipeline:** Validar a extração em memória e confirmar via `MagicMock` que o Supabase recebeu o método `upsert` e que logou o evento de sucesso na tabela `etl_logs`.

---

## Out of Scope

- Extração de metadados como número de telefone do gabinete ou e-mail.
- Tratamento histórico de mandatos anteriores à Legislatura 57.
- Implementação de filas assíncronas (Celery) para este escopo.

---

## Further Notes

- O processo de teste utilizará `pytest` no diretório `tests/etl/test_extrator_senadores.py`.
- O campo `data_ultima_atualizacao` manterá estritamente o formato ISO8601 em timezone UTC, conforme ajustado anteriormente para evitar quebras no banco de dados.