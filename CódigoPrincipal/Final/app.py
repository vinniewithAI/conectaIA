# -*- coding: utf-8 -*-
"""app.py"""

import streamlit as st
import os
import traceback
from chatbot import QASystem, ProcessamentoDeDocumento
import google.generativeai as genai
from streamlit_agraph import agraph, Node, Edge, Config

from crud import (
    autenticar_usuario, cadastrar_pessoa, validar_forca_senha, armazenar_token,
    listar_pessoas, deletar_pessoa, atualizar_senha,
    cadastrar_ecommerce, listar_ecommerces, atualizar_ecommerce, deletar_ecommerce
)

# Configuração da página
st.set_page_config(page_title="Conecta IA", layout="wide")
print("Iniciando app.py...")

if "GOOGLE_API_KEY" not in os.environ or not os.environ["GOOGLE_API_KEY"]:
    st.error("Chave API GOOGLE_API_KEY não encontrada. Configure-a.")
    st.stop()
else:
    try:
        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    except Exception as e:
        st.error(f"Erro ao re-configurar Gemini em app.py: {e}")

# Inicializar o sistema de QA (uses Gemini via QASystem class)
if "qa_system" not in st.session_state:
    try:
        st.session_state.qa_system = QASystem()
        print("QASystem (com Gemini) inicializado com sucesso.")
    except Exception as e:
        print(f"Erro ao inicializar QASystem com Gemini: {e}")
        st.error(f"Erro ao inicializar QASystem: {e}")
        st.stop()

# Inicializar o processador de documentos
if "processor" not in st.session_state:
    try:
        st.session_state.processor = ProcessamentoDeDocumento()
        print("ProcessamentoDeDocumento inicializado com sucesso.")
    except Exception as e:
        print(f"Erro ao inicializar ProcessamentoDeDocumento: {e}")
        st.error(f"Erro ao inicializar ProcessamentoDeDocumento: {e}")
        st.stop()


def generate_and_display_mental_map(conversation_messages):
    st.subheader("Mapa Mental da Conversa")
    if not conversation_messages:
        st.warning("Não há mensagens na conversa para gerar um mapa mental.")
        return

    conversation_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_messages])
    
    # Using the same prompt structure as before for consistency
    prompt_template_mapa = """Com base na seguinte conversa, identifique os 5 a 7 principais tópicos ou substantivos chave discutidos.
Liste-os separados por vírgulas. Priorize substantivos ou frases nominais curtas.

Conversa:
{text}

Tópicos Principais:"""
    full_prompt_mapa = prompt_template_mapa.format(text=conversation_text)

    try:
        # Initialize a Gemini model instance specifically for this task if preferred,
        # or use a global one if you create one in app.py.
        # It's generally better to instantiate where needed or pass from a central point.
        map_llm = genai.GenerativeModel(
            'gemini-1.5-flash-latest', # or 'gemini-pro' - flash is faster and often sufficient for this
            generation_config={"temperature": 0.6} # Low temp for factual extraction
        )
        
        with st.spinner("Analisando conversa para extrair tópicos com Gemini API..."):
            response = map_llm.generate_content(full_prompt_mapa)
            
            if not response.parts:
                 st.error(f"Geração de mapa mental falhou. Prompt bloqueado ou resposta vazia. Detalhes: {response.prompt_feedback}")
                 return
            
            try:
                response_text = response.text.strip()
            except ValueError as ve:
                st.error(f"Geração de mapa mental falhou. Resposta bloqueada. Detalhes: {response.prompt_feedback}")
                print(f"DEBUG mental_map Gemini response blocked: {response}")
                return


        raw_topics_text = response_text
        if "Tópicos Principais:" in raw_topics_text:
            topics_str = raw_topics_text.split("Tópicos Principais:", 1)[-1].strip()
        else:
            topics_str = raw_topics_text.strip()

        if not topics_str or len(topics_str) < 3 or \
           any(neg in topics_str.lower() for neg in ["não consigo", "não posso", "não foi possível", "não sou capaz", "incapaz de", "não é possível"]):
            st.warning(f"O modelo Gemini não conseguiu extrair tópicos de forma confiável. Resposta: \"{topics_str}\"")
            return

        identified_topics = list(dict.fromkeys([topic.strip() for topic in topics_str.split(',') if topic.strip() and len(topic.strip()) > 1])) 

        if not identified_topics:
            st.warning("Nenhum tópico identificado para o mapa mental via Gemini API.")
            return
        
        nodes = []
        edges = []
        node_ids = set()
        
        # Central node for the conversation
        CONVERSATION_NODE_ID = "Conversa Principal"
        nodes.append(Node(id=CONVERSATION_NODE_ID, label="Conversa", size=25, shape="star", color="#FFC107"))
        node_ids.add(CONVERSATION_NODE_ID)

        for topic in identified_topics:
            if topic not in node_ids: # Ensure unique node IDs
                nodes.append(Node(id=topic, label=topic, size=15, shape="ellipse"))
                node_ids.add(topic)
            # Connect each topic to the central conversation node
            if CONVERSATION_NODE_ID in node_ids and topic in node_ids:
                 edges.append(Edge(source=CONVERSATION_NODE_ID, target=topic, label="contém"))


        if len(nodes) <=1: # Only the central node
            st.write("Nenhum tópico significativo para exibir no mapa.")
            return

        config = Config(width=750, height=600, directed=True, 
                        physics={'enabled': True, 'solver': 'barnesHut', 
                                 'barnesHut': {'gravitationalConstant': -3000, 'centralGravity': 0.1, 'springLength': 150, 'springConstant': 0.05, 'damping': 0.09},
                                 'minVelocity': 0.75},
                        hierarchical=False, collapsible=False,
                        node={'labelProperty': 'label', 'font': {'size': 18}},
                        edge={'labelProperty':'label', 'renderLabel':True, 'font': {'size': 12, 'align': 'top'}},
                        interaction={'hover': True, 'tooltipDelay': 200},
                        layout={'randomSeed': 42}, # For consistent layout for same data
                        manipulation=False,
                        )
        
        agraph(nodes=nodes, edges=edges, config=config)
        st.success("Mapa mental gerado com Gemini API!")

    except Exception as e:
        st.error(f"Erro ao gerar mapa mental com Gemini API: {str(e)}")
        print(f"Detailed error generating mental map with Gemini API: {str(e)}")
        traceback.print_exc()


# Abas
tab1, tab2, tab3, tab4 = st.tabs(["Chatbot", "Gerenciar Usuários", "Gerenciar E-commerce", "Configurações"])

# 1. Chatbot
with tab1:
    if "user_id" not in st.session_state:
        st.title("Login")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Senha", type="password", key="login_password")

        if st.button("Entrar"):
            print(f"Tentando login com email: {email}")
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
        nome_reg = st.text_input("Nome", key="reg_nome") 
        telefone_reg = st.text_input("Telefone (XX)XXXXX-XXXX", key="reg_telefone")
        email_reg = st.text_input("Email", key="reg_email")
        data_nascimento_reg = st.date_input("Data nascimento", key="reg_data_nascimento", value=None, format="YYYY-MM-DD") 
        senha_reg = st.text_input("Senha", type="password", key="reg_senha")
        if st.button("Registrar"):
            print(f"Tentando registrar usuário: {nome_reg}, {telefone_reg}, {email_reg}, {data_nascimento_reg}") 
            try:
                if not validar_forca_senha(senha_reg):
                    st.error("A senha deve ter pelo menos 8 caracteres, uma letra maiúscula e um número.")
                elif not all([nome_reg, telefone_reg, email_reg, data_nascimento_reg, senha_reg]):
                    st.error("Todos os campos de registro são obrigatórios.")
                else:
                    # Convert date object to string if needed by your CRUD function
                    data_nascimento_str = data_nascimento_reg.strftime("%Y-%m-%d") if data_nascimento_reg else None
                    user_id = cadastrar_pessoa(nome_reg, telefone_reg, email_reg, data_nascimento_str, senha_reg) 
                    if user_id:
                        st.success("Usuário registrado com sucesso! Faça login.")
                    else:
                        st.error("Erro ao registrar usuário. O email pode já estar em uso ou dados inválidos.") 
            except Exception as e:
                print(f"Erro ao registrar usuário: {e}")
                st.error(f"Erro ao registrar usuário: {e}")
    else:
        user_name = st.session_state.get("user_name", "Usuário")
        st.title(f"Chatbot Conecta 🤖 - Bem-vindo, {user_name}")

        uploaded_file = st.file_uploader("Carregue um PDF para análise", type=["pdf"])
        if uploaded_file: # Processar imediatamente após o upload, se um novo arquivo for carregado
            # Adicionar um botão explícito para processar, ou usar uma lógica para processar apenas uma vez
            if "last_uploaded_filename" not in st.session_state or st.session_state.last_uploaded_filename != uploaded_file.name:
                if st.button("Processar PDF Carregado"):
                    with st.spinner("Processando PDF..."):
                        temp_file_path = os.path.join(".", uploaded_file.name) 
                        with open(temp_file_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        try:
                            doc_id = st.session_state.processor.process_pdf(temp_file_path, st.session_state.user_id)
                            if doc_id:
                                st.success(f"PDF '{uploaded_file.name}' processado com sucesso!")
                                st.session_state.last_uploaded_filename = uploaded_file.name # Marcar como processado
                            else:
                                st.error("Erro ao processar o PDF. Verifique os logs.")
                        except Exception as e:
                            print(f"Erro ao processar PDF: {e}")
                            st.error(f"Erro ao processar o PDF: {e}")
                        finally:
                            if os.path.exists(temp_file_path):
                                os.remove(temp_file_path)
            elif st.session_state.last_uploaded_filename == uploaded_file.name:
                st.info(f"PDF '{uploaded_file.name}' já foi processado ou está pronto para ser processado. Faça uma pergunta.")


        if "messages" not in st.session_state:
            st.session_state.messages = []

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"]) # Use markdown para melhor formatação
                if "sources" in msg and msg["sources"]:
                    st.caption("Fontes: " + ", ".join(msg["sources"]))


        user_input = st.chat_input("Pergunte algo sobre marketplaces...")
        if user_input:
            st.session_state.messages.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)

            with st.spinner("Consultando a IA..."):
                try:
                    resposta = st.session_state.qa_system.ask_question(user_input, st.session_state.user_id)
                    if resposta and resposta.get("resposta"):
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": resposta["resposta"],
                            "sources": resposta.get("fontes", [])
                        })
                        with st.chat_message("assistant"):
                            st.markdown(resposta["resposta"])
                            if resposta.get("fontes"):
                                st.caption("Fontes: " + ", ".join(resposta["fontes"]))


                        # Preparar mensagens para armazenar_token (apenas o último par user/assistant)
                        messages_to_store = [
                            {"role": "user", "content": user_input},
                            {"role": "assistant", "content": resposta["resposta"]}
                        ]
                        # Certifique-se que crud.armazenar_token aceita esta estrutura
                        armazenar_token(st.session_state.user_id, messages_to_store)
                    elif resposta: # Resposta existe mas não tem "resposta" (pode ser um erro tratado)
                        st.error("Não foi possível obter uma resposta formatada do assistente.")
                        print(f"DEBUG: Resposta recebida do QASystem sem conteúdo 'resposta': {resposta}")
                    else:
                        st.error("Erro ao obter resposta. Verifique os logs do servidor.")
                        # Adicionar mensagem de erro ao chat para o usuário
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": "Desculpe, não consegui processar sua pergunta no momento."
                        })
                        with st.chat_message("assistant"):
                            st.markdown("Desculpe, não consegui processar sua pergunta no momento.")

                except Exception as e:
                    print(f"Erro ao processar pergunta: {e}\n{traceback.format_exc()}")
                    st.error(f"Erro crítico ao processar pergunta: {e}")
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": f"Ocorreu um erro técnico: {e}"
                    })
                    with st.chat_message("assistant"):
                        st.markdown(f"Ocorreu um erro técnico: {e}")
           

        if st.session_state.messages:
            st.markdown("---")
            if st.button("Encerrar Conversa e Gerar Mapa Mental"):
                generate_and_display_mental_map(st.session_state.messages)


# 2. Gerenciar Usuários
with tab2:
    if "user_id" not in st.session_state:
        st.warning("Faça login para acessar esta seção.")
    else:
        st.title("Gerenciar Usuários")

        if st.button("Carregar Lista de Usuários", key="btn_load_users_tab2"):
            try:
                users_list = listar_pessoas()
                if users_list is not None:
                    if users_list:
                        st.write(f"Total de usuários: {len(users_list)}")
                        display_data = []
                        for user_item in users_list:
                            display_data.append({
                                "ID": str(user_item.get('_id', 'N/A')),
                                "Nome": user_item.get('nome', 'N/A'),
                                "Email": user_item.get('email', 'N/A'),
                                "Data de Nascimento": user_item.get('data_nascimento', 'N/A'),
                                "Criado em": user_item.get('created_at').strftime('%Y-%m-%d %H:%M:%S') if user_item.get('created_at') else 'N/A',
                                "Atualizado em": user_item.get('updated_at').strftime('%Y-%m-%d %H:%M:%S') if user_item.get('updated_at') else 'N/A'
                            })
                        st.dataframe(display_data)
                    else:
                        st.info("Nenhum usuário encontrado.")
                else:
                    st.error("Falha ao carregar usuários.")
            except Exception as e:
                st.error(f"Erro ao exibir usuários: {e}")

        st.markdown("---")
        st.subheader("Deletar Usuário")
        user_id_to_delete = st.text_input("ID do Usuário para Deletar:", key="input_delete_user_id_tab2")
        if st.button("Deletar Usuário Selecionado", key="btn_delete_user_tab2"):
            if not user_id_to_delete.strip():
                st.warning("Insira o ID do usuário.")
            else:
                try:
                    if "user_id" in st.session_state and user_id_to_delete == st.session_state.user_id:
                        st.error("Você não pode deletar seu próprio usuário.")
                    elif deletar_pessoa(user_id_to_delete):
                        st.success(f"Usuário ID '{user_id_to_delete}' deletado.")
                        st.rerun()
                    else:
                        st.error(f"Erro ao deletar usuário ID '{user_id_to_delete}'.")
                except Exception as e:
                    st.error(f"Erro ao deletar: {e}")

# 3. Gerenciar E-commerce
with tab3:
    if "user_id" not in st.session_state:
        st.warning("Faça login para acessar esta seção.")
    else:
        st.title("Gerenciar E-commerce")

        with st.expander("Cadastrar Novo E-commerce", expanded=False):
            with st.form(key="form_cadastrar_ecommerce"):
                nome_ecom = st.text_input("Nome do E-commerce")
                categoria_ecom = st.text_input("Categoria")
                descricao_ecom = st.text_area("Descrição")
                faixa_preco_ecom_str = st.text_input("Faixa de Preço (Ex: 100)")
                url_ecom = st.text_input("URL")
                plano_ecom = st.text_input("Plano")
                pros_ecom_str = st.text_input("Prós (separados por vírgula)")
                contras_ecom_str = st.text_input("Contras (separados por vírgula)")
                submit_button_cad_ecom = st.form_submit_button(label="Cadastrar E-commerce")

                if submit_button_cad_ecom:
                    if not all([nome_ecom, categoria_ecom, descricao_ecom, faixa_preco_ecom_str, url_ecom, plano_ecom]):
                        st.error("Todos os campos são obrigatórios para cadastrar e-commerce.")
                    else:
                        try:
                            faixa_preco_int = int(faixa_preco_ecom_str)
                            pros_list = [p.strip() for p in pros_ecom_str.split(',') if p.strip()]
                            contras_list = [c.strip() for c in contras_ecom_str.split(',') if c.strip()]
                            
                            if cadastrar_ecommerce(nome_ecom, categoria_ecom, descricao_ecom, faixa_preco_int, url_ecom, plano_ecom, pros_list, contras_list):
                                st.success("E-commerce cadastrado!")
                               
                            else:
                                st.error("Erro ao cadastrar e-commerce.")
                        except ValueError:
                            st.error("Faixa de preço deve ser um número.")
                        except Exception as e:
                            st.error(f"Erro: {e}")
        
        st.markdown("---")
        st.subheader("Listar E-commerces")
        if st.button("Carregar Lista de E-commerces", key="btn_list_ecom_tab3"):
            try:
                ecommerces_list = listar_ecommerces()
                if ecommerces_list is not None:
                    if ecommerces_list:
                        st.write(f"Total de e-commerces: {len(ecommerces_list)}")
                        display_data_ecom = []
                        for ecom_item in ecommerces_list:
                            pros_list = ecom_item.get('pros', [])
                            contras_list = ecom_item.get('contras', [])
                            item_data = {
                                "ID": str(ecom_item.get('_id', 'N/A')),
                                "Nome": ecom_item.get('nome', 'N/A'),
                                "Categoria": ecom_item.get('categoria', 'N/A'),
                                "Descrição": ecom_item.get('descricao', 'N/A')[:100] + "..." if len(ecom_item.get('descricao', '')) > 100 else ecom_item.get('descricao', 'N/A'),
                                "Faixa de Preço": ecom_item.get('faixa-preco', 'N/A'),
                                "URL": ecom_item.get('url', 'N/A'),
                                "Plano": ecom_item.get('plano', 'N/A'),
                                "Prós": ', '.join(pros_list) if isinstance(pros_list, list) else str(pros_list),
                                "Contras": ', '.join(contras_list) if isinstance(contras_list, list) else str(contras_list),
                                "Criado em": ecom_item.get('created_at').strftime('%Y-%m-%d %H:%M:%S') if ecom_item.get('created_at') and hasattr(ecom_item.get('created_at'), 'strftime') else 'N/A',
                                "Atualizado em": ecom_item.get('updated_at').strftime('%Y-%m-%d %H:%M:%S') if ecom_item.get('updated_at') and hasattr(ecom_item.get('updated_at'), 'strftime') else 'N/A'
                            }
                            display_data_ecom.append(item_data)
                        st.dataframe(display_data_ecom)
                    else:
                        st.info("Nenhum e-commerce encontrado.")
                else:
                    st.error("Falha ao carregar e-commerces.")
            except Exception as e:
                st.error(f"Erro ao exibir e-commerces: {e}")

        st.markdown("---")
        with st.expander("Atualizar E-commerce", expanded=False):
             with st.form(key="form_atualizar_ecommerce"):
                ecom_id_update = st.text_input("ID do E-commerce para Atualizar")
                st.write("Preencha apenas os campos que deseja alterar:")
                ecom_nome_update = st.text_input("Novo Nome", key="ecom_nome_upd")
                ecom_categoria_update = st.text_input("Nova Categoria", key="ecom_cat_upd")
                ecom_descricao_update = st.text_area("Nova Descrição", key="ecom_desc_upd")
                ecom_faixa_preco_nova_str_upd = st.text_input("Nova Faixa de Preço", key="ecom_fp_upd")
                ecom_url_update = st.text_input("Nova URL", key="ecom_url_upd")
                ecom_plano_update = st.text_input("Novo Plano", key="ecom_plano_upd")
                ecom_pros_update_str = st.text_input("Novos Prós (substitui os antigos, separados por vírgula)", key="ecom_pros_upd")
                ecom_contras_update_str = st.text_input("Novos Contras (substitui os antigos, separados por vírgula)", key="ecom_contras_upd")

                submit_button_upd_ecom = st.form_submit_button(label="Atualizar E-commerce")

                if submit_button_upd_ecom:
                    if not ecom_id_update.strip():
                        st.error("O ID do e-commerce é obrigatório para atualização.")
                    else:
                        updates = {}
                        if ecom_nome_update: updates["nome"] = ecom_nome_update
                        if ecom_categoria_update: updates["categoria"] = ecom_categoria_update
                        if ecom_descricao_update: updates["descricao"] = ecom_descricao_update
                        if ecom_url_update: updates["url"] = ecom_url_update
                        if ecom_plano_update: updates["plano"] = ecom_plano_update
                        
                        if ecom_faixa_preco_nova_str_upd:
                            try:
                                updates["faixa-preco"] = int(ecom_faixa_preco_nova_str_upd)
                            except ValueError:
                                st.error("A nova faixa de preço deve ser um número.")
                        
                        if ecom_pros_update_str: # Se string não vazia, processa
                            updates["pros"] = [p.strip() for p in ecom_pros_update_str.split(',') if p.strip()]
                        elif ecom_pros_update_str == "": # Se string vazia, define como lista vazia
                            updates["pros"] = []

                        if ecom_contras_update_str:
                            updates["contras"] = [c.strip() for c in ecom_contras_update_str.split(',') if c.strip()]
                        elif ecom_contras_update_str == "":
                            updates["contras"] = []
                            
                        if updates:
                            try:
                                if atualizar_ecommerce(ecom_id_update, updates):
                                    st.success("E-commerce atualizado!")
                                else:
                                    st.error("Erro ao atualizar. Verifique o ID.")
                            except Exception as e:
                                st.error(f"Erro: {e}")
                        else:
                            st.info("Nenhum campo modificado para atualização.")
        
        st.markdown("---")
        st.subheader("Deletar E-commerce")
        ecom_id_delete_input = st.text_input("ID do E-commerce para Deletar", key="input_id_ecom_delete_tab3")
        confirmado_para_deletar = st.checkbox("Confirmo que desejo deletar o e-commerce.", key="checkbox_confirm_delete_ecom_tab3", disabled=not ecom_id_delete_input.strip())

        if st.button("Deletar E-commerce Confirmado", key="btn_confirm_ecom_delete_tab3"):
            if not ecom_id_delete_input.strip():
                st.warning("Insira o ID do e-commerce.")
            elif not confirmado_para_deletar:
                st.warning("Confirme a deleção marcando a caixa.")
            else:
                try:
                    if deletar_ecommerce(ecom_id_delete_input):
                        st.success(f"E-commerce ID '{ecom_id_delete_input}' deletado.")
                        st.rerun()
                    else:
                        st.error(f"Erro ao deletar e-commerce ID '{ecom_id_delete_input}'.")
                except Exception as e:
                    st.error(f"Erro ao deletar: {e}")


# 4. Configurações
with tab4:
    if "user_id" not in st.session_state:
        st.warning("Faça login para acessar esta seção.")
    else:
        st.title("Configurações")
        st.subheader("Alterar Senha")
        
        user_email_from_session = "" 
        if "user_email" in st.session_state: 
            user_email_from_session = st.session_state.user_email
        elif "user_id" in st.session_state:
            pass



        email_for_pw_change = st.text_input("Seu Email (para confirmação)", 
                                            value=user_email_from_session, 
                                            key="change_email_tab4",
                                            disabled=(user_email_from_session != ""))

        senha_atual = st.text_input("Senha Atual", type="password", key="current_password_tab4")
        nova_senha = st.text_input("Nova Senha", type="password", key="new_password_tab4")
        
        if st.button("Alterar Senha", key="btn_change_password_tab4"):
            if not email_for_pw_change or not senha_atual or not nova_senha:
                st.error("Todos os campos são obrigatórios para alterar a senha.")
            elif not validar_forca_senha(nova_senha):
                st.error("A nova senha deve ter pelo menos 8 caracteres, uma letra maiúscula e um número.")
            else:
                try:
                    if atualizar_senha(email_for_pw_change, senha_atual, nova_senha):
                        st.success("Senha alterada com sucesso!")
                    else:
                        st.error("Erro ao alterar senha. Verifique seu email e senha atual.")
                except Exception as e:
                    st.error(f"Erro: {e}")

        st.markdown("---")
        if st.button("Sair", key="btn_logout_tab4"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.success("Você saiu da sua conta.")
            st.rerun()