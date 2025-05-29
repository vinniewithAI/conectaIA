import streamlit as st
import os
import torch
from pymongo import MongoClient
import gc
import re
from langchain_huggingface import HuggingFaceEmbeddings, HuggingFacePipeline
from langchain_mongodb import MongoDBAtlasVectorSearch
from langchain.chains import RetrievalQA
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.document_loaders import PyPDFLoader
from langchain.prompts import PromptTemplate
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, pipeline, BitsAndBytesConfig

# Configuração inicial
st.title("Chatbot de Comércio Eletrônico")

# Definir variáveis de ambiente (substitua pelo seu token real)
os.environ["HUGGINGFACEHUB_API_TOKEN"] = "seu_token_aqui"  # Substitua pelo seu token
os.environ["LANGCHAIN_API_KEY"] = "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"
os.environ["LANGCHAIN_TRACING_V2"] = "true"

# Inicializar estado da sessão
if "user_id" not in st.session_state:
    st.session_state.user_id = "12345"
if "doc_processed" not in st.session_state:
    st.session_state.doc_processed = False
if "qa_system" not in st.session_state:
    st.session_state.qa_system = None

# Configuração de quantização
bnb_config = BitsAndBytesConfig(
    load_in_8bit=True,
    bnb_8bit_quant_type="nf4",
    bnb_8bit_compute_dtype=torch.float16,
    bnb_8bit_use_double_quant=True
)


# Carregar o modelo e pipeline (apenas uma vez)
@st.cache_resource
def load_model():
    print("Inicializando LLM...")
    model_name = "google/flan-t5-small"
    tokenizer = AutoTokenizer.from_pretrained(model_name, token=os.environ["HUGGINGFACEHUB_API_TOKEN"])
    model = AutoModelForSeq2SeqLM.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        device_map="cuda" if torch.cuda.is_available() else "cpu",
        token=os.environ["HUGGINGFACEHUB_API_TOKEN"],
        torch_dtype=torch.float16,
        low_cpu_mem_usage=True
    )
    pipe = pipeline(
        "text2text-generation",
        model=model,
        tokenizer=tokenizer,
        max_length=512,  # Limite total de tokens (entrada + saída)
        max_new_tokens=256,  # Reduzido para deixar espaço para a entrada
        temperature=0.7,
        do_sample=True,
        truncation=True
    )
    llm = HuggingFacePipeline(pipeline=pipe)
    print("LLM inicializado com sucesso.")
    return llm


# Configurar MongoDB
client = MongoClient("mongodb+srv://conecta-ia:O1r3VIK4X35CzEfL@conecta-cluster.hgjlsdc.mongodb.net/")
db = client["conecta"]


# Classe para processar documentos
class ProcessamentoDeDocumento:
    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            model_kwargs={'device': 'cuda' if torch.cuda.is_available() else 'cpu'}
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=200,  # Reduzido para evitar sequência longa
            chunk_overlap=50
        )

    def process_pdf(self, file_path, user_id):
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
            return doc_id
        except Exception as e:
            st.error(f"Erro ao processar o PDF: {str(e)}")
            return None


# Classe para o sistema de QA
class QASystem:
    def __init__(self, llm):
        self.llm = llm
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            model_kwargs={'device': 'cuda' if torch.cuda.is_available() else 'cpu'}
        )
        self.vector_store = MongoDBAtlasVectorSearch(
            collection=db.document_vectors,
            embedding=self.embeddings,
            index_name="document_search"
        )

    def ask_question(self, question, user_id):
        try:
            retriever = self.vector_store.as_retriever(
                filter={"user_id": user_id},
                search_kwargs={"k": 3}  # Reduzido para evitar sequência longa
            )
            template = """Com base no contexto, responda em português de forma clara e concisa.
Se não encontrar a resposta, diga: "Não consegui encontrar a resposta no documento."

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

            end_marker_prompt_part = "Resposta:"
            if end_marker_prompt_part in resposta_limpa:
                resposta_limpa = resposta_limpa.split(end_marker_prompt_part, 1)[-1].strip()

            full_prompt_text_start = "Com base no contexto, responda em português de forma clara e concisa."
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

            return {
                "resposta": resposta_limpa,
                "fontes": fontes_unicas
            }
        except Exception as e:
            st.error(f"Erro ao responder a pergunta '{question}': {str(e)}")
            return None


# Interface do Streamlit
llm = load_model()

# Inicializar o QASystem apenas uma vez
if st.session_state.qa_system is None:
    st.session_state.qa_system = QASystem(llm)

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
            st.error("Falha ao processar o PDF.")
            st.session_state.doc_processed = False

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