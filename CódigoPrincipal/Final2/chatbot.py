# -*- coding: utf-8 -*-
"""chatbot.py"""

import os
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings, HuggingFaceEndpoint
from langchain_mongodb import MongoDBAtlasVectorSearch
from langchain.chains import RetrievalQA
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain.prompts import PromptTemplate
import re
from pymongo import MongoClient
import gc

# Carregar variáveis de ambiente
load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

# Configuração do LangChain Tracing
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY", "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")
os.environ["LANGCHAIN_TRACING_V2"] = "true"

# Usar um modelo leve via HuggingFaceEndpoint
print("Inicializando LLM...")  # Depuração
llm = HuggingFaceEndpoint(
    repo_id="google/flan-t5-small",
    huggingfacehub_api_token=HF_TOKEN,
    temperature=0.7
)
print("LLM inicializado com sucesso.")  # Depuração

# Configurar o MongoDB
print(f"Conectando ao MongoDB com URI: {MONGO_URI}")  # Depuração
client = MongoClient(MONGO_URI)
db = client["conecta"]

class ProcessamentoDeDocumento:
    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            model_kwargs={'device': 'cpu'}
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=100
        )

    def process_pdf(self, file_path, user_id):
        try:
            print(f"Processando PDF: {file_path} para user_id: {user_id}")  # Depuração
            loader = PyPDFLoader(file_path)
            pages = loader.load()
            chunks = self.text_splitter.split_documents(pages)
            for chunk in chunks:
                chunk.metadata["user_id"] = user_id

            doc_id = db.documents.insert_one({
                "user_id": user_id,
                "original_path": file_path
            }).inserted_id

            print(f"Indexando vetores para documento ID: {doc_id}")  # Depuração
            MongoDBAtlasVectorSearch.from_documents(
                documents=chunks,
                embedding=self.embeddings,
                collection=db.document_vectors,
                index_name="document_search"
            )
            gc.collect()
            return doc_id
        except Exception as e:
            print(f"Erro: {str(e)}")
            return None

class QASystem:
    def __init__(self):
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

    def ask_question(self, question, user_id):
        print(f"Respondendo pergunta: '{question}' para user_id: {user_id}")  # Depuração
        try:
            print("Configurando retriever...")  # Depuração
            retriever = self.vector_store.as_retriever(
                filter={"user_id": user_id},
                search_kwargs={"k": 5}
            )
            print("Retriever configurado com sucesso.")  # Depuração

            template = """Com base **apenas** no contexto fornecido, responda à pergunta **em português**.
                        Formule uma resposta **clara, concisa e natural**, sem introduções, o contexto ou a pergunta.
                        Se a resposta não puder ser encontrada no contexto fornecido, responda **apenas**: "Não consegui encontrar a resposta para esta pergunta no documento fornecido."

            Contexto:
            {context}

            Pergunta: {question}

            Resposta:"""
            PROMPT = PromptTemplate(template=template, input_variables=["context", "question"])

            print("Inicializando RetrievalQA...")  # Depuração
            qa = RetrievalQA.from_chain_type(
                llm=self.llm,
                chain_type="stuff",
                retriever=retriever,
                return_source_documents=True,
                chain_type_kwargs={"prompt": PROMPT}
            )
            print("RetrievalQA inicializado com sucesso.")  # Depuração

            print("Invocando QA com pergunta...")  # Depuração
            result = qa.invoke({"query": question})
            print("Invocação concluída.")  # Depuração

            resposta_bruta = result["result"].strip()
            resposta_limpa = resposta_bruta

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

            fontes_unicas = list(set([doc.metadata.get("source", doc.metadata.get("file_name", "Desconhecido")) for doc in result["source_documents"]]))

            print(f"Resposta gerada: {resposta_limpa}")  # Depuração
            return {
                "resposta": resposta_limpa,
                "fontes": fontes_unicas
            }
        except Exception as e:
            print(f"Erro ao responder a pergunta '{question}': {str(e)}")
            return None