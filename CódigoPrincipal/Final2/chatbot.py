# -*- coding: utf-8 -*-
"""chatbot.py"""

import streamlit as st
import torch
from pymongo import MongoClient
import gc
import re
from langchain_huggingface import HuggingFaceEmbeddings, HuggingFacePipeline
from langchain_mongodb import MongoDBAtlasVectorSearch
from langchain.chains import RetrievalQA
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain.prompts import PromptTemplate
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, pipeline  # Adicionado AutoModelForSeq2SeqLM
import os

# Configuração inicial
st.title("Chatbot de Comércio Eletrônico")

# Acessar variáveis de ambiente (configuradas via secrets.toml no Streamlit Cloud)
try:
    HUGGINGFACEHUB_API_TOKEN = st.secrets["HUGGINGFACEHUB_API_TOKEN"]
    LANGCHAIN_API_KEY = st.secrets["LANGCHAIN_API_KEY"]
    LANGCHAIN_TRACING_V2 = st.secrets["LANGCHAIN_TRACING_V2"]
    MONGO_URI = st.secrets["MONGO_URI"]
except KeyError as e:
    st.error(f"Erro: Variável de ambiente {e} não encontrada no secrets.toml.")
    st.stop()

# Verificar se o token do Hugging Face está definido
if not HUGGINGFACEHUB_API_TOKEN:
    st.error("Erro: HUGGINGFACEHUB_API_TOKEN não está definido. Configure-o no secrets.toml.")
    st.stop()

# Definir variáveis de ambiente
os.environ["HUGGINGFACEHUB_API_TOKEN"] = HUGGINGFACEHUB_API_TOKEN
os.environ["LANGCHAIN_API_KEY"] = LANGCHAIN_API_KEY
os.environ["LANGCHAIN_TRACING_V2"] = LANGCHAIN_TRACING_V2

# Liberar memória antes de carregar o modelo
gc.collect()
torch.cuda.empty_cache() if torch.cuda.is_available() else None

# Inicializar estado da sessão
if "user_id" not in st.session_state:
    st.session_state.user_id = "12345"
if "doc_processed" not in st.session_state:
    st.session_state.doc_processed = False
if "qa_system" not in st.session_state:
    st.session_state.qa_system = None

# Carregar o modelo e pipeline (apenas uma vez)
@st.cache_resource
def load_model():
    print("Inicializando LLM...")
    try:
        model_name = "google/flan-t5-base"  # ~250M parâmetros
        tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            token=HUGGINGFACEHUB_API_TOKEN
        )
        model = AutoModelForSeq2SeqLM.from_pretrained(
            model_name,
            device_map="cpu",
            torch_dtype=torch.float16,
            low_cpu_mem_usage=True,
            token=HUGGINGFACEHUB_API_TOKEN
        )
        pipe = pipeline(
            "text2text-generation",  # Adequado para Flan-T5
            model=model,
            tokenizer=tokenizer,
            max_new_tokens=256,
            temperature=0.7,
            do_sample=True,
            truncation=True
        )
        llm = HuggingFacePipeline(pipeline=pipe)
        print("LLM inicializado com sucesso.")
        gc.collect()
        return llm
    except Exception as e:
        print(f"Erro ao inicializar o modelo: {str(e)}")
        st.error(f"Erro ao inicializar o modelo: {str(e)}")
        return None

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

# Classe para processar documentos
class ProcessamentoDeDocumento:
    def __init__(self):
        try:
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                model_kwargs={'device': 'cpu'}
            )
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=500,
                chunk_overlap=100
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
                index_name="document_search"
            )
            gc.collect()
            print(f"PDF processado com ID: {doc_id}")
            return doc_id
        except Exception as e:
            st.error(f"Erro ao processar o PDF: {str(e)}")
            return None

# Classe para o sistema de QA
class QASystem:
    def __init__(self, llm):
        try:
            self.llm = llm
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                model_kwargs={'device': 'cpu'}
            )
            self.vector_store = MongoDBAtlasVectorSearch(
                collection=db.document_vectors,
                embedding=self.embeddings,
                index_name="document_search"
            )
            print("QASystem inicializado com sucesso.")
        except Exception as e:
            st.error(f"Erro ao inicializar QASystem: {str(e)}")
            self.llm = None
            self.vector_store = None

    def ask_question(self, question, user_id):
        if not self.llm or not self.vector_store:
            st.error("Erro: Sistema de QA não inicializado corretamente.")
            return None
        try:
            with torch.no_grad():  # Reduz uso de memória
                retriever = self.vector_store.as_retriever(
                    filter={"user_id": user_id},
                    search_kwargs={"k": 5}
                )
                template = """Com base no contexto fornecido, responda à pergunta **em português brasileiro**.
Formule uma resposta **clara, concisa e natural**.
Se a resposta não puder ser encontrada no contexto fornecido, responda **apenas**: "Não consegui encontrar a resposta para esta pergunta no documento fornecido."

Contexto:
{context}

Pergunta: {question}

Resposta:"""
                PROMPT = PromptTemplate(template=template, input_variables=["context", "question"])

                qa = RetrievalQA.from_chain_type(
                    llm=self.llm,
                    chain_type="stuff",
                    retriever=retriever,
                    return_source_documents=True,
                    chain_type_kwargs={"prompt": PROMPT}
                )

                result = qa.invoke({"query": question})

                resposta_bruta = result["result"].strip()
                resposta_limpa = resposta_bruta

                # Limpeza de respostas
                end_marker_prompt_part = "Resposta:"
                if end_marker_prompt_part in resposta_limpa:
                    resposta_limpa = resposta_limpa.split(end_marker_prompt_part, 1)[-1].strip()

                full_prompt_text_start = "Com base **apenas** no contexto fornecido, responda à pergunta **em português**."
                full_prompt_text_fallback = "Com base **exclusivamente** no contexto fornecido, responda à seguinte pergunta."

                if resposta_limpa.startswith(full_prompt_text_start):
                    resposta_limpa = resposta_limpa.replace(full_prompt_text_start, "", 1).strip()
                elif resposta_limpa.startswith(full_prompt_text_fallback):
                    resposta_limpa = resposta_limpa.replace(full_prompt_text_fallback, "", 1).strip()

                if resposta_limpa.lower().startswith("helpful answer:"):
                    resposta_limpa = resposta_limpa[len("helpful answer:"):].strip()
                if resposta_limpa.lower().startswith("a resposta é:"):
                    resposta_limpa = resposta_limpa[len("a resposta é:"):].strip()
                if resposta_limpa.lower().startswith("here's the answer:"):
                    resposta_limpa = resposta_limpa[len("here's the answer:"):].strip()

                if "Contexto:" in resposta_limpa:
                    resposta_limpa = resposta_limpa.split("Contexto:", 1)[0].strip()
                if "Pergunta:" in resposta_limpa:
                    resposta_limpa = resposta_limpa.split("Pergunta:", 1)[0].strip()
                if "Resposta:" in resposta_limpa:
                    resposta_limpa = resposta_limpa.replace("Resposta:", "").strip()

                resposta_limpa = re.sub(r'\S*/[a-zA-Z]\.alt(/[a-zA-Z]\.alt)*l?', '', resposta_limpa)
                resposta_limpa = re.sub(r'\s{2,}', ' ', resposta_limpa).strip()
                resposta_limpa = re.sub(r'\s*([.,;?!])', r'\1', resposta_limpa)
                resposta_limpa = re.sub(r'([.,;?!])\s*(?=[a-zA-Z0-9])', r'\1 ', resposta_limpa)
                resposta_limpa = resposta_limpa.replace('**', '')

                fontes_unicas = list(
                    set([doc.metadata.get("source", doc.metadata.get("file_name", "Desconhecido")) for doc in
                         result["source_documents"]]))

                gc.collect()  # Liberar memória
                return {
                    "resposta": resposta_limpa,
                    "fontes": fontes_unicas
                }
        except Exception as e:
            st.error(f"Erro ao responder a pergunta '{question}': {str(e)}")
            return None

# Interface do Streamlit
llm = load_model()
if llm is None:
    st.error("Falha ao carregar o modelo. Verifique os logs no Streamlit Cloud para mais detalhes.")
    st.stop()

# Inicializar o QASystem apenas uma vez
if st.session_state.qa_system is None:
    st.session_state.qa_system = QASystem(llm)
    if st.session_state.qa_system is None:
        st.error("Falha ao inicializar o sistema de QA. Verifique os logs no Streamlit Cloud.")
        st.stop()

# Upload do PDF
uploaded_file = st.file_uploader("Faça upload do seu PDF", type="pdf")
if uploaded_file is not None and not st.session_state.doc_processed:
    with st.spinner("Processando o PDF..."):
        # Salvar o arquivo temporariamente
        with open("temp.pdf", "wb") as f:
            f.write(uploaded_file.getbuffer())

        processor = ProcessamentoDeDocumento()
        doc_id = processor.process_pdf("temp.pdf", st.session_state.user_id)

        if doc_id:
            st.session_state.doc_processed = True
            st.success("PDF processado com sucesso!")
        else:
            st.session_state.doc_processed = False
            st.error("Falha ao processar o PDF. Verifique os logs no Streamlit Cloud.")

# Campo de entrada para perguntas
if st.session_state.doc_processed:
    question = st.text_input("Digite sua pergunta:", placeholder="Ex.: O que é uma loja online?")
    if question:
        with st.spinner("Gerando resposta..."):
            qa = st.session_state.qa_system
            response = qa.ask_question(question, st.session_state.user_id)
            if response:
                st.write("**Resposta:**", response["resposta"])
                st.write("**Fontes:**", ", ".join(response["fontes"]))
else:
    st.info("Por favor, faça upload de um PDF para começar.")