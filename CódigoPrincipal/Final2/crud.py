# -*- coding: utf-8 -*-
"""crud.py"""

import os
from pymongo import MongoClient
from dotenv import load_dotenv
import datetime
from bson import ObjectId
import bcrypt
from urllib.parse import urlparse

print("Iniciando carregamento do crud.py...")  # Depuração

# Carregar variáveis de ambiente
load_dotenv()
print("Variáveis de ambiente carregadas.")  # Depuração

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    print("Erro: MONGO_URI não encontrado nas variáveis de ambiente.")
    raise ValueError("MONGO_URI não encontrado nas variáveis de ambiente. Configure-o no .env ou nos segredos do Streamlit Cloud.")
print(f"MONGO_URI carregado: {MONGO_URI}")  # Depuração

def conecta_user():
    print("Conectando à coleção 'user'...")  # Depuração
    try:
        client = MongoClient(MONGO_URI)
        db = client["conecta"]
        return db["user"]
    except Exception as e:
        print(f"Erro ao conectar ao MongoDB (user): {e}")
        return None

def conecta_token():
    print("Conectando à coleção 'token'...")  # Depuração
    try:
        client = MongoClient(MONGO_URI)
        db = client["conecta"]
        return db["token"]
    except Exception as e:
        print(f"Erro ao conectar ao MongoDB (token): {e}")
        return None

def conecta_ecommerce():
    print("Conectando à coleção 'ecommerce'...")  # Depuração
    try:
        client = MongoClient(MONGO_URI)
        db = client["conecta"]
        return db["ecommerce"]
    except Exception as e:
        print(f"Erro ao conectar ao MongoDB (ecommerce): {e}")
        return None

# Usuários
def criar_pessoa(nome: str, email: str, senha_plana: str):
    print(f"Tentando criar pessoa: {nome}, {email}")  # Depuração
    colecao = conecta_user()
    try:
        senha_hash = gerar_hash_senha(senha_plana)
        if not senha_hash:
            print("Erro: Falha ao gerar hash da senha.")
            return None

        pessoa = {
            "nome": nome,
            "email": email,
            "senha": senha_hash,
            "created_at": datetime.datetime.utcnow(),
            "updated_at": datetime.datetime.utcnow()
        }

        resultado = colecao.insert_one(pessoa)
        print(f"Usuário criado com ID: {resultado.inserted_id}")
        return resultado.inserted_id

    except Exception as e:
        print(f"Erro ao criar usuário: {e}")
        return None

def listar_pessoas():
    print("Listando pessoas...")  # Depuração
    colecao = conecta_user()
    try:
        return list(colecao.find().sort("_id"))
    except Exception as e:
        print(f"Erro ao listar pessoas: {e}")
        return []

def buscar_por_id(id_str):
    print(f"Buscando pessoa por ID: {id_str}")  # Depuração
    colecao = conecta_user()
    try:
        obj_id = ObjectId(id_str)
        return colecao.find_one({"_id": obj_id})
    except:
        print("ID inválido")
        return None

def atualizar_pessoa(id_str: str, novo_nome: str):
    print(f"Atualizando pessoa ID: {id_str}, Novo nome: {novo_nome}")  # Depuração
    colecao = conecta_user()
    try:
        obj_id = ObjectId(id_str)
        resultado = colecao.update_one(
            {"_id": obj_id},
            {"$set": {"nome": novo_nome, "updated_at": datetime.datetime.utcnow()}}
        )
        return resultado.modified_count > 0
    except Exception as e:
        print(f"Erro ao atualizar pessoa: {e}")
        return False

def deletar_pessoa(id_str: str):
    print(f"Deletando pessoa ID: {id_str}")  # Depuração
    colecao = conecta_user()
    try:
        obj_id = ObjectId(id_str)
        resultado = colecao.delete_one({"_id": obj_id})
        return resultado.deleted_count > 0
    except Exception as e:
        print(f"Erro ao deletar pessoa: {e}")
        return False

def autenticar_usuario(email: str, senha_plana: str) -> dict:
    print(f"Autenticando usuário: {email}")  # Depuração
    colecao_pessoas = conecta_user()
    try:
        usuario = colecao_pessoas.find_one({"email": email})
        if not usuario:
            print("Usuário não encontrado")
            return None

        if verificar_senha(senha_plana, usuario["senha"]):
            print("Autenticação bem-sucedida!")
            return usuario
        else:
            print("Senha incorreta")
            return None

    except Exception as e:
        print(f"Erro ao autenticar usuário: {e}")
        return None

def atualizar_senha(email: str, senha_atual: str, nova_senha: str) -> bool:
    print(f"Atualizando senha para email: {email}")  # Depuração
    colecao = conecta_user()
    try:
        usuario = autenticar_usuario(email, senha_atual)
        if not usuario:
            return False

        novo_hash = gerar_hash_senha(nova_senha)
        if not novo_hash:
            return False

        resultado = colecao.update_one(
            {"_id": usuario["_id"]},
            {"$set": {
                "senha": novo_hash,
                "updated_at": datetime.datetime.utcnow()
            }}
        )

        return resultado.modified_count > 0

    except Exception as e:
        print(f"Erro ao atualizar senha: {e}")
        return False

def validar_forca_senha(senha: str) -> bool:
    print(f"Validando força da senha: {senha}")  # Depuração
    if len(senha) < 8:
        print("A senha deve ter pelo menos 8 caracteres")
        return False
    if not any(c.isupper() for c in senha):
        print("A senha deve conter pelo menos uma letra maiúscula")
        return False
    if not any(c.isdigit() for c in senha):
        print("A senha deve conter pelo menos um número")
        return False
    return True

def gerar_hash_senha(senha_plana: str) -> str:
    print(f"Gerando hash para senha.")  # Depuração
    try:
        salt = bcrypt.gensalt(rounds=12)
        hash_senha = bcrypt.hashpw(senha_plana.encode('utf-8'), salt)
        return hash_senha.decode('utf-8')
    except Exception as e:
        print(f"Erro ao gerar hash da senha: {e}")
        return None

def verificar_senha(senha_plana: str, hash_armazenado: str) -> bool:
    print(f"Verificando senha.")  # Depuração
    try:
        hash_bytes = hash_armazenado.encode('utf-8')
        return bcrypt.checkpw(senha_plana.encode('utf-8'), hash_bytes)
    except Exception as e:
        print(f"Erro ao verificar senha: {e}")
        return False

# Token
def armazenar_token(user_id, messages):
    print(f"Armazenando token para user_id: {user_id}")  # Depuração
    try:
        colecao_tokens = conecta_token()
        if colecao_tokens is None:
            return None

        token_data = {
            "user_id": user_id,
            "messages": messages,
            "updated_at": datetime.datetime.utcnow()
        }

        resultado = colecao_tokens.insert_one(token_data)
        print(f"Token armazenado com ID: {resultado.inserted_id}")
        return resultado.inserted_id
    except Exception as e:
        print(f"Erro ao armazenar token: {e}")
        return None

def buscar_tokens_por_usuario(user_id):
    print(f"Buscando tokens para user_id: {user_id}")  # Depuração
    try:
        colecao_tokens = conecta_token()
        if colecao_tokens is None:
            return None

        tokens = list(colecao_tokens.find({"user_id": user_id}).sort("updated_at", -1))
        return tokens
    except Exception as e:
        print(f"Erro ao buscar tokens: {e}")
        return None

# E-commerce
def cadastrar_ecommerce(nome: str, categoria: str, descricao: str, faixa_preco: str, url: str, plano: str, pros: str, contras: str):
    print(f"Cadastrando e-commerce: {nome}")  # Depuração
    colecao = conecta_ecommerce()
    try:
        faixa_preco_int = int(faixa_preco) if faixa_preco else 0
        ecommerce = {
            "_id": ObjectId(),
            "name": nome,
            "category": categoria,
            "description": descricao,
            "faixa-preco": faixa_preco_int,
            "url": url,
            "plano": plano,
            "pros": pros.split(",") if isinstance(pros, str) else pros,
            "contras": contras.split(",") if isinstance(contras, str) else contras,
            "updated_at": datetime.datetime.utcnow()
        }

        def validar_url(url):
            try:
                result = urlparse(url)
                return all([result.scheme, result.netloc])
            except:
                return False

        resultado = colecao.insert_one(ecommerce)
        print(f"\n✅ E-commerce cadastrado com ID: {resultado.inserted_id}")
        return resultado.inserted_id

    except ValueError:
        print("Erro: Faixa de preço deve ser um número")
        return None
    except Exception as e:
        print(f"Erro ao cadastrar e-commerce: {e}")
        return None

def listar_ecommerces():
    print("Listando e-commerces...")  # Depuração
    colecao = conecta_ecommerce()
    try:
        return list(colecao.find().sort("name"))
    except Exception as e:
        print(f"Erro ao listar e-commerces: {e}")
        return []

def buscar_ecommerce_por_id(id_ecommerce):
    print(f"Buscando e-commerce por ID: {id_ecommerce}")  # Depuração
    colecao = conecta_ecommerce()
    try:
        obj_id = ObjectId(id_ecommerce)
        return colecao.find_one({"_id": obj_id})
    except Exception as e:
        print(f"Erro ao buscar e-commerce: {e}")
        return None

def buscar_ecommerces_por_categoria(categoria):
    print(f"Buscando e-commerces por categoria: {categoria}")  # Depuração
    colecao = conecta_ecommerce()
    return list(colecao.find({"category": categoria}))

def atualizar_ecommerce(id_ecommerce, updates):
    print(f"Atualizando e-commerce ID: {id_ecommerce}")  # Depuração
    colecao = conecta_ecommerce()
    try:
        obj_id = ObjectId(id_ecommerce)
        ecommerce = colecao.find_one({"_id": obj_id})
        if not ecommerce:
            print("❌ E-commerce não encontrado")
            return False

        if updates:
            updates['updated_at'] = datetime.datetime.utcnow()
            resultado = colecao.update_one(
                {"_id": obj_id},
                {"$set": updates}
            )
            return resultado.modified_count > 0
        else:
            print("⚠️ Nenhum campo selecionado para atualização")
            return False
    except ValueError:
        print("Erro: Rating deve ser um número")
        return False
    except Exception as e:
        print(f"Erro ao atualizar e-commerce: {e}")
        return False

def deletar_ecommerce(id_ecommerce):
    print(f"Deletando e-commerce ID: {id_ecommerce}")  # Depuração
    colecao = conecta_ecommerce()
    try:
        obj_id = ObjectId(id_ecommerce)
        resultado = colecao.delete_one({"_id": obj_id})
        return resultado.deleted_count > 0
    except Exception as e:
        print(f"Erro ao deletar e-commerce: {e}")
        return False

print("crud.py carregado com sucesso!")  # Depuração