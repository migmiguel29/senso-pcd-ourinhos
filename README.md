# Senso PCD de Ourinhos

Painel administrativo. O deploy demonstrativo inclui somente registros fictícios.
Use repositório privado. Nunca envie a planilha, credenciais ou hashes ao GitHub.

## Contas e publicação

1. Execute `python gerar_conta.py` e informe o usuário e a senha no terminal privado.
2. Cadastre cada bloco gerado em Secrets do Streamlit. Use uma conta por operador.
3. No Community Cloud, selecione o repositório, branch main e app.py.
4. Verifique bloqueio sem login, login válido, senha inválida e saída.

## Dados reais em ambiente institucional

Execute `pip install -r requirements.txt` e `streamlit run app.py` em ambiente institucional controlado.
Crie .streamlit/secrets.toml fora do Git e adicione os blocos das contas. Se o ambiente
estiver autorizado para processar a planilha, adicione `habilitar_importacao_local = true`
no início do TOML. Envie a aba Dados pela interface autenticada. A aplicação usa a planilha
na sessão e apresenta contagens. O login do protótipo tem pausa por sessão e prazo de
30 minutos. Para implantação institucional, adote autenticação gerenciada, proteção contra
tentativas distribuídas, controle de acesso na rede e auditoria. Deixe a importação
desativada no Community Cloud.
