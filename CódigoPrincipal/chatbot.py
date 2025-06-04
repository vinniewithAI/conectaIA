# -*- coding: utf-8 -*-
"""chatbot.py"""

import streamlit as st
import torch 
from pymongo import MongoClient
import gc
import re
import google.generativeai as genai
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_mongodb import MongoDBAtlasVectorSearch 
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain.prompts import PromptTemplate 
import os

# Acessar variáveis de ambiente
try:

    GOOGLE_API_KEY = os.environ["GOOGLE_API_KEY"]
    LANGCHAIN_API_KEY = os.environ.get("LANGCHAIN_API_KEY") 
    LANGCHAIN_TRACING_V2 = os.environ.get("LANGCHAIN_TRACING_V2")
    MONGO_URI = os.environ["MONGO_URI"]
except KeyError as e:
    st.error(f"Erro: Variável de ambiente {e} não encontrada. Configure-a nos Secrets do Space.")
    st.stop()

if not GOOGLE_API_KEY: 
    st.error("Erro: GOOGLE_API_KEY não está definida. Configure-a nos Secrets do Space.")
    st.stop()

if LANGCHAIN_API_KEY and LANGCHAIN_TRACING_V2:
    os.environ["LANGCHAIN_API_KEY"] = LANGCHAIN_API_KEY
    os.environ["LANGCHAIN_TRACING_V2"] = LANGCHAIN_TRACING_V2

# Configure the Gemini API client
try:
    genai.configure(api_key=GOOGLE_API_KEY)
    print("Google Generative AI SDK configurado.")
except Exception as e:
    st.error(f"Erro ao configurar o SDK do Google Generative AI: {str(e)}")
    st.stop()


# Liberar memória
gc.collect()
if torch.cuda.is_available():
    torch.cuda.empty_cache()

# Configurar MongoDB 
try:
    client = MongoClient(MONGO_URI)
    db = client["conecta"]
    print("Conexão com MongoDB estabelecida com sucesso.")
except Exception as e:
    st.error(f"Erro ao conectar ao MongoDB: {str(e)}")
    client = None
    db = None
    st.stop()

# Classe ProcessamentoDeDocumento 
class ProcessamentoDeDocumento:
    def __init__(self):
        try:
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                model_kwargs={'device': 'cpu'}
            )
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=50
            )
            print("ProcessamentoDeDocumento inicializado com sucesso.")
        except Exception as e:
            st.error(f"Erro ao inicializar ProcessamentoDeDocumento: {str(e)}")
            self.embeddings = None
            self.text_splitter = None

    def process_pdf(self, file_path, user_id):
        if not self.embeddings or not self.text_splitter:
            st.error("Erro: Processador de documentos não inicializado corretamente.")
            return None
        try:
            loader = PyPDFLoader(file_path)
            pages = loader.load()
            chunks = self.text_splitter.split_documents(pages)
            for chunk in chunks:
                chunk.metadata["user_id"] = user_id

            doc_id = db.documents.insert_one({
                "user_id": user_id,
                "original_path": file_path
            }).inserted_id

            MongoDBAtlasVectorSearch.from_documents(
                documents=chunks,
                embedding=self.embeddings,
                collection=db.document_vectors,
                index_name="document_search" # Default LangChain index name
            )
            gc.collect()
            print(f"PDF processado com ID: {doc_id}")
            return doc_id
        except Exception as e:
            st.error(f"Erro ao processar o PDF: {str(e)}")
            return None

# Classe para o sistema de QA 
class QASystem:
    def __init__(self):
        try:
            # Choose your Gemini model
            self.llm = genai.GenerativeModel(
                model_name='gemini-1.5-flash-latest',
                 generation_config={
                    "temperature": 0.7,
                    "max_output_tokens": 512, 
                }
            )
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                model_kwargs={'device': 'cpu'}
            )
            self.vector_store = MongoDBAtlasVectorSearch(
                collection=db.document_vectors,
                embedding=self.embeddings,
                index_name="document_search" 
            )
            print("QASystem inicializado com sucesso usando Gemini.")
        except Exception as e:
            st.error(f"Erro ao inicializar QASystem com Gemini: {str(e)}")
            self.llm = None
            self.vector_store = None

    def ask_question(self, question, user_id):
        if not self.llm or not self.vector_store:
            st.error("Erro: Sistema de QA não inicializado corretamente.")
            return None
        try:
            # 1. Retrieve relevant documents using LangChain's vector store
            retriever = self.vector_store.as_retriever(
                filter={"user_id": user_id},
                search_kwargs={"k": 3} # Number of documents to retrieve
            )
            relevant_docs = retriever.get_relevant_documents(question) # LangChain method

            if not relevant_docs:
                return {
                    "resposta": "Não consegui encontrar informações relevantes nos documentos carregados para responder a esta pergunta.",
                    "fontes": []
                }

            # 2. Prepare the context for Gemini
            context_parts = []
            sources_set = set()
            for doc in relevant_docs:
                context_parts.append(doc.page_content)
                sources_set.add(doc.metadata.get("source", doc.metadata.get("file_name", "Desconhecido")))
            
            context_str = "\n\n---\n\n".join(context_parts)

            full_prompt_for_gemini = f"""
Você é um assistente de IA especializado em responder perguntas com base em um contexto fornecido, porém não se prenda apenas a ele.
Responda em **português**.
Formule uma resposta clara, concisa e natural, sem repetir a pergunta ou mencionar explicitamente "o contexto".
Não cite os documentos na resposta.
Se a resposta não puder ser encontrada no contexto, utilize conhecimento externo ao contexto fornecido para responder.

Contexto Fornecido:
---
{context_str}
---

Entrada do Usuário:
{question}

Resposta Concisa:
"""
            print(f"DEBUG: Enviando para Gemini:\n{full_prompt_for_gemini[:500]}...") # Log first 500 chars

            # 4. Call Gemini API
            # For pure text prompts, use generate_content
            gemini_response = self.llm.generate_content(full_prompt_for_gemini)
            
            # Check if response has parts and text
            if not gemini_response.parts:
                print(f"DEBUG: Resposta do Gemini NÃO TEM 'parts'. Resposta completa: {gemini_response}")
                if hasattr(gemini_response, 'text'):
                    resposta_bruta = gemini_response.text.strip()
                elif gemini_response.prompt_feedback and gemini_response.prompt_feedback.block_reason:
                     st.error(f"Prompt bloqueado pela API Gemini. Razão: {gemini_response.prompt_feedback.block_reason_message}")
                     return {"resposta": "A pergunta não pôde ser processada devido a restrições de conteúdo.", "fontes": list(sources_set)}
                else: # Fallback if blocked or unexpected structure
                    st.error("Resposta do Gemini não pôde ser processada (sem 'parts' e sem 'text' direto). Verifique os logs.")
                    print(f"DEBUG: Resposta completa inesperada do Gemini: {gemini_response}")
                    return {"resposta": "Ocorreu um erro ao processar sua pergunta com a API Gemini (estrutura de resposta inesperada).", "fontes": list(sources_set)}

            else: 
                try:
                    resposta_bruta = gemini_response.text.strip() 
                except ValueError as ve: 
                    print(f"DEBUG: ValueError ao acessar gemini_response.text: {ve}")
                    print(f"DEBUG: Resposta completa do Gemini: {gemini_response}")
                    if gemini_response.prompt_feedback and gemini_response.prompt_feedback.block_reason:
                         st.error(f"Prompt bloqueado pela API Gemini. Razão: {gemini_response.prompt_feedback.block_reason_message}")
                         return {"resposta": "A pergunta não pôde ser processada devido a restrições de conteúdo.", "fontes": list(sources_set)}
                    # If blocked for other reasons or unexpected structure
                    st.error("Resposta do Gemini não pôde ser processada (possivelmente bloqueada ou formato inesperado). Verifique os logs.")
                    return {"resposta": "Ocorreu um erro ao processar sua pergunta com a API Gemini.", "fontes": list(sources_set)}


            # 5. Clean the response 
            resposta_limpa = resposta_bruta
          
            end_marker_prompt_part = "Resposta Concisa:" 
            if end_marker_prompt_part in resposta_limpa: 
                resposta_limpa = resposta_limpa.split(end_marker_prompt_part, 1)[-1].strip()

            instructional_phrases_to_remove = [
                "Com base no contexto fornecido,",
                "Com base exclusivamente no contexto fornecido,",
                "Aqui está a resposta:",
                "A resposta é:",
                "Helpful answer:",
                "Here's the answer:",
                "Resposta:",
             
            ]
            for phrase in instructional_phrases_to_remove:
                if resposta_limpa.lower().startswith(phrase.lower()):
                    resposta_limpa = resposta_limpa[len(phrase):].strip()
            
            resposta_limpa = re.sub(r'\S*/[a-zA-Z]\.alt(/[a-zA-Z]\.alt)*l?', '', resposta_limpa)
            resposta_limpa = re.sub(r'\s{2,}', ' ', resposta_limpa).strip()
            resposta_limpa = re.sub(r'\s*([.,;?!])', r'\1', resposta_limpa)
            resposta_limpa = re.sub(r'([.,;?!])\s*(?=[a-zA-Z0-9])', r'\1 ', resposta_limpa)
            resposta_limpa = resposta_limpa.replace('**', '')

            gc.collect()
            return {
                "resposta": resposta_limpa,
                "fontes": list(sources_set) # Convert set to list
            }
        except Exception as e:
            st.error(f"Erro ao responder a pergunta '{question}' com Gemini: {str(e)}")
            import traceback as tb
            print(f"DETALHE DO ERRO em ask_question (Gemini): {tb.format_exc()}")
            return None