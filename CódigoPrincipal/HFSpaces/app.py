# -*- coding: utf-8 -*-
"""app.py"""

import streamlit as st
import os
from chatbot import load_model, QASystem, ProcessamentoDeDocumento
from crud import (
    autenticar_usuario, criar_pessoa, validar_forca_senha, armazenar_token,
    listar_pessoas, atualizar_pessoa, deletar_pessoa, atualizar_senha,
    cadastrar_ecommerce, listar_ecommerces, atualizar_ecommerce, deletar_ecommerce
)

# Configuração da página
st.set_page_config(page_title="Conecta IA", layout="wide")

# Carregar o modelo uma única vez
llm = load_model()
if llm is None:
    st.error("Falha ao carregar o modelo. Verifique os logs.")
    st.stop()

# Inicializar o sistema de QA
if "qa_system" not in st.session_state:
    try:
        st.session_state.qa_system = QASystem(llm)
        print("QASystem inicializado com sucesso.")  # Depuração
    except Exception as e:
        print(f"Erro ao inicializar QASystem: {e}")
        st.error(f"Erro ao inicializar QASystem: {e}")
        st.stop()

# Inicializar o processador de documentos
if "processor" not in st.session_state:
    try:
        st.session_state.processor = ProcessamentoDeDocumento()
        print("ProcessamentoDeDocumento inicializado com sucesso.")  # Depuração
    except Exception as e:
        print(f"Erro ao inicializar ProcessamentoDeDocumento: {e}")
        st.error(f"Erro ao inicializar ProcessamentoDeDocumento: {e}")
        st.stop()

# Abas
tab1, tab2, tab3, tab4 = st.tabs(["Chatbot", "Gerenciar Usuários", "Gerenciar E-commerce", "Configurações"])

# 1. Chatbot
with tab1:
    if "user_id" not in st.session_state:
        st.title("Login")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Senha", type="password", key="login_password")

        if st.button("Entrar"):
            print(f"Tentando login com email: {email}")  # Depuração
            try:
                user = autenticar_usuario(email, password)
                if user:
                    st.session_state.user_id = str(user["_id"])
                    st.session_state.user_name = user.get("nome", "Usuário")
                    st.success("Login bem-sucedido!")
                    st.rerun()
                else:
                    st.error("Email ou senha incorretos.")
            except Exception as e:
                print(f"Erro ao autenticar usuário: {e}")
                st.error(f"Erro ao fazer login: {e}")

        st.subheader("Registrar")
        nome = st.text_input("Nome", key="reg_nome")
        email_reg = st.text_input("Email (para registro)", key="reg_email")
        senha_reg = st.text_input("Senha (para registro)", type="password", key="reg_senha")
        if st.button("Registrar"):
            print(f"Tentando registrar usuário: {nome}, {email_reg}")  # Depuração
            try:
                if not validar_forca_senha(senha_reg):
                    st.error("A senha deve ter pelo menos 8 caracteres, uma letra maiúscula e um número.")
                else:
                    user_id = criar_pessoa(nome, email_reg, senha_reg)
                    if user_id:
                        st.success("Usuário registrado com sucesso! Faça login.")
                    else:
                        st.error("Erro ao registrar usuário.")
            except Exception as e:
                print(f"Erro ao registrar usuário: {e}")
                st.error(f"Erro ao registrar usuário: {e}")
    else:
        user_name = st.session_state.get("user_name", "Usuário")
        st.title(f"Chatbot Conecta 🤖 - Bem-vindo, {user_name}")

        uploaded_file = st.file_uploader("Carregue um PDF para análise", type=["pdf"])
        if uploaded_file and st.button("Processar PDF"):
            with open("temp.pdf", "wb") as f:
                f.write(uploaded_file.getbuffer())
            try:
                doc_id = st.session_state.processor.process_pdf("temp.pdf", st.session_state.user_id)
                if doc_id:
                    st.success(f"PDF processado com sucesso! ID: {doc_id}")
                else:
                    st.error("Erro ao processar o PDF. Verifique os logs.")
            except Exception as e:
                print(f"Erro ao processar PDF: {e}")
                st.error(f"Erro ao processar o PDF: {e}")
            finally:
                if os.path.exists("temp.pdf"):
                    os.remove("temp.pdf")

        if "messages" not in st.session_state:
            st.session_state.messages = []

        for msg in st.session_state.messages:
            st.chat_message(msg["role"]).write(msg["content"])
            if "sources" in msg:
                st.write("**Fontes:**", ", ".join(msg["sources"]))

        user_input = st.chat_input("Pergunte algo sobre marketplaces...")
        if user_input:
            st.session_state.messages.append({"role": "user", "content": user_input})
            st.chat_message("user").write(user_input)

            try:
                resposta = st.session_state.qa_system.ask_question(user_input, st.session_state.user_id)
                if resposta:
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": resposta["resposta"],
                        "sources": resposta["fontes"]
                    })
                    st.chat_message("assistant").write(resposta["resposta"])
                    st.write("**Fontes:**", ", ".join(resposta["fontes"]))

                    messages = [
                        {"role": "user", "content": user_input},
                        {"role": "assistant", "content": resposta["resposta"]}
                    ]
                    armazenar_token(st.session_state.user_id, messages)
                else:
                    st.error("Erro ao obter resposta. Verifique os logs.")
            except Exception as e:
                print(f"Erro ao processar pergunta: {e}")
                st.error(f"Erro ao processar pergunta: {e}")

# 2. Gerenciar Usuários
with tab2:
    if "user_id" not in st.session_state:
        st.warning("Faça login para acessar esta seção.")
    else:
        st.title("Gerenciar Usuários")
        try:
            users = listar_pessoas()
            if users:
                for user in users:
                    st.write(f"ID: {user['_id']}, Nome: {user['nome']}, Email: {user['email']}")
            else:
                st.write("Nenhum usuário encontrado.")
        except Exception as e:
            print(f"Erro ao listar usuários: {e}")
            st.error(f"Erro ao listar usuários: {e}")

        st.subheader("Atualizar Usuário")
        user_id_to_update = st.text_input("ID do Usuário para Atualizar")
        novo_nome = st.text_input("Novo Nome")
        if st.button("Atualizar Usuário"):
            try:
                if atualizar_pessoa(user_id_to_update, novo_nome):
                    st.success("Usuário atualizado com sucesso!")
                else:
                    st.error("Erro ao atualizar usuário.")
            except Exception as e:
                print(f"Erro ao atualizar usuário: {e}")
                st.error(f"Erro ao atualizar usuário: {e}")

        st.subheader("Deletar Usuário")
        user_id_to_delete = st.text_input("ID do Usuário para Deletar")
        if st.button("Deletar Usuário"):
            try:
                if user_id_to_delete == st.session_state.user_id:
                    st.error("Você não pode deletar seu próprio usuário enquanto estiver logado!")
                elif deletar_pessoa(user_id_to_delete):
                    st.success("Usuário deletado com sucesso!")
                else:
                    st.error("Erro ao deletar usuário.")
            except Exception as e:
                print(f"Erro ao deletar usuário: {e}")
                st.error(f"Erro ao deletar usuário: {e}")

# 3. Gerenciar E-commerce
with tab3:
    if "user_id" not in st.session_state:
        st.warning("Faça login para acessar esta seção.")
    else:
        st.title("Gerenciar E-commerce")

        st.subheader("Cadastrar E-commerce")
        nome = st.text_input("Nome do E-commerce")
        categoria = st.text_input("Categoria")
        descricao = st.text_area("Descrição")
        faixa_preco = st.text_input("Faixa de Preço (número)")
        url = st.text_input("URL")
        plano = st.text_input("Plano")
        pros = st.text_input("Prós (separados por vírgula)")
        contras = st.text_input("Contras (separados por vírgula)")
        if st.button("Cadastrar E-commerce"):
            try:
                faixa_preco_int = int(faixa_preco) if faixa_preco else 0
                if cadastrar_ecommerce(nome, categoria, descricao, faixa_preco_int, url, plano, pros, contras):
                    st.success("E-commerce cadastrado com sucesso!")
                else:
                    st.error("Erro ao cadastrar e-commerce.")
            except ValueError:
                st.error("Faixa de preço deve ser um número.")
            except Exception as e:
                print(f"Erro ao cadastrar e-commerce: {e}")
                st.error(f"Erro ao cadastrar e-commerce: {e}")

        st.subheader("Listar E-commerces")
        if st.button("Listar E-commerces"):
            try:
                ecommerces = listar_ecommerces()
                if ecommerces:
                    for ecom in ecommerces:
                        st.write(f"ID: {ecom['_id']}, Nome: {ecom['name']}, Categoria: {ecom['category']}, Descrição: {ecom['description']}, Preço: {ecom.get('faixa-preco', 'Não informado')}, URL: {ecom.get('url', 'Não informada')}, Plano: {ecom.get('plano', 'Não informado')}, Prós: {', '.join(ecom.get('pros', []))}, Contras: {', '.join(ecom.get('contras', []))}")
                else:
                    st.write("Nenhum e-commerce encontrado.")
            except Exception as e:
                print(f"Erro ao listar e-commerces: {e}")
                st.error(f"Erro ao listar e-commerces: {e}")

        st.subheader("Atualizar E-commerce")
        ecom_id = st.text_input("ID do E-commerce para Atualizar")
        ecom_nome = st.text_input("Novo Nome", key="ecom_nome")
        ecom_categoria = st.text_input("Nova Categoria")
        ecom_descricao = st.text_area("Nova Descrição")
        if st.button("Atualizar E-commerce"):
            try:
                updates = {}
                if ecom_nome:
                    updates["name"] = ecom_nome
                if ecom_categoria:
                    updates["category"] = ecom_categoria
                if ecom_descricao:
                    updates["description"] = ecom_descricao
                if updates and atualizar_ecommerce(ecom_id, updates):
                    st.success("E-commerce atualizado com sucesso!")
                else:
                    st.error("Erro ao atualizar e-commerce.")
            except Exception as e:
                print(f"Erro ao atualizar e-commerce: {e}")
                st.error(f"Erro ao atualizar e-commerce: {e}")

        st.subheader("Deletar E-commerce")
        ecom_id_delete = st.text_input("ID do E-commerce para Deletar")
        if st.button("Deletar E-commerce"):
            try:
                if deletar_ecommerce(ecom_id_delete):
                    st.success("E-commerce deletado com sucesso!")
                else:
                    st.error("Erro ao deletar e-commerce.")
            except Exception as e:
                print(f"Erro ao deletar e-commerce: {e}")
                st.error(f"Erro ao deletar e-commerce: {e}")

# 4. Configurações
with tab4:
    if "user_id" not in st.session_state:
        st.warning("Faça login para acessar esta seção.")
    else:
        st.title("Configurações")
        st.subheader("Alterar Senha")
        email = st.text_input("Seu Email", key="change_email")
        senha_atual = st.text_input("Senha Atual", type="password")
        nova_senha = st.text_input("Nova Senha", type="password")
        if st.button("Alterar Senha"):
            try:
                if not validar_forca_senha(nova_senha):
                    st.error("A nova senha deve ter pelo menos 8 caracteres, uma letra maiúscula e um número.")
                elif atualizar_senha(email, senha_atual, nova_senha):
                    st.success("Senha alterada com sucesso!")
                else:
                    st.error("Erro ao alterar senha. Verifique suas credenciais.")
            except Exception as e:
                print(f"Erro ao alterar senha: {e}")
                st.error(f"Erro ao alterar senha: {e}")

        if st.button("Sair"):
            st.session_state.clear()
            st.success("Você saiu da sua conta.")
            st.rerun()