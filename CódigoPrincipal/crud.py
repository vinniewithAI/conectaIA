# -*- coding: utf-8 -*-
"""crud.py""" # Docstring do módulo - Isso está correto

# 1. Imports
# Imports relacionados ao MongoDB e dados
from pymongo import MongoClient
import datetime
from bson import ObjectId

# Imports para hashing de senha
import bcrypt

# Imports para operações de string/regex
import re


# 1.1 Conectar

def conecta_user():
  STRING = "mongodb+srv://conecta-ia:O1r3VIK4X35CzEfL@conecta-cluster.hgjlsdc.mongodb.net/"
  try:
    client = MongoClient(STRING)
    db = client["conecta"]
    return db["user"]
  except Exception as e:
    print(f"Erro ao conectar ao MongoDB: {e}")
    return None

def conecta_token():
  STRING = "mongodb+srv://conecta-ia:O1r3VIK4X35CzEfL@conecta-cluster.hgjlsdc.mongodb.net/"
  try:
    client = MongoClient(STRING)
    db = client["conecta"]
    return db["token"]
  except Exception as e:
    print(f"Erro ao conectar ao MongoDB: {e}")
    return None

def conecta_ecommerce():
  STRING = "mongodb+srv://conecta-ia:O1r3VIK4X35CzEfL@conecta-cluster.hgjlsdc.mongodb.net/"
  try:
    client = MongoClient(STRING)
    db = client["conecta"]
    return db["ecommerce"]
  except Exception as e:
    print(f"Erro ao conectar ao MongoDB: {e}")
    return None

"""#2. Pessoas

##2.1 Usuário
"""

def cadastrar_pessoa(nome: str, telefone: str, email: str, data_nascimento,  senha_plana: str):
    colecao = conecta_user()

    try:
        # Validar formato do email
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email):
            print(f"❌ Email inválido: {email}")
            return None

        # Verificar se o email já está registrado
        if colecao.find_one({"email": email}):
            print(f"❌ Email já registrado: {email}")
            return None

        # Gerar hash da senha
        senha_hash = gerar_hash_senha(senha_plana)
        if not senha_hash:
            print("❌ Falha ao gerar hash da senha")
            return None

        # Criar documento do usuário
        pessoa = {
            "nome": nome,
            "telefone": telefone,
            "email": email,
            "data_nascimento": data_nascimento,
            "senha": senha_hash,
            "created_at": datetime.datetime.now(datetime.timezone.utc),
            "updated_at": datetime.datetime.now(datetime.timezone.utc)
        }

        # Inserir no banco de dados
        resultado = colecao.insert_one(pessoa)
        print(f"✅ Usuário criado com id: {resultado.inserted_id}")
        return resultado.inserted_id

    except Exception as e:
        print(f"❌ Erro ao criar usuário: {e}")
        return None

def autenticar_usuario(email: str, senha_plana: str) -> dict:

    colecao_pessoas = conecta_user()

    try:
        # Buscar usuário pelo email
        usuario = colecao_pessoas.find_one({"email": email})
        if not usuario:
            print("❌ Usuário não encontrado")
            return None

        # Verificar senha
        if verificar_senha(senha_plana, usuario["senha"]):
            print("✅ Autenticação bem-sucedida!")
            return usuario
        else:
            print("❌ Senha incorreta")
            return None

    except Exception as e:
        print(f"❌ Erro ao autenticar usuário: {e}")
        return None


def listar_pessoas():

    colecao = conecta_user()
    if colecao is None:
        print("❌ Erro ao listar pessoas: Falha na conexão com o banco de dados.")
        return None 

    lista_de_pessoas = []
    try:
        for pessoa_doc in colecao.find().sort("nome"): 
            lista_de_pessoas.append(pessoa_doc)
        
        print("\n✅ Pessoas listadas do banco:")
        for p in lista_de_pessoas:
            print(f"  ID: {p['_id']}, Nome: {p['nome']}, Email: {p['email']}")
            
        return lista_de_pessoas
    except Exception as e:
        print(f"❌ Erro ao buscar ou processar lista de pessoas: {e}")
        return None


def buscar_pessoa(id):

  colecao = conecta_user()
  obj_id = ObjectId(id)

  try:
    pessoa = colecao.find_one({"_id": obj_id})
    if (pessoa):
      print("ID encontrado")
      print("\n🔍 Pessoa encontrada:")
      print(f"ID: {pessoa['_id']}")
      print(f"Nome: {pessoa['nome']}")
      print(f"Telefone: {pessoa['telefone']}")
      print(f"E-mail: {pessoa['email']}")
      print(f"Data de nascimento: {pessoa['data_nascimento']}")
      print(f"Criado em: {pessoa['created_at']}")
      print(f"Atualizado em: {pessoa['updated_at']}")
      return pessoa
    else:
      print("❌ Nenhuma pessoa com esse id")
      return None
  except:
    print("❌ Erro ao buscar pessoa")
    return None

def deletar_pessoa(id):

  colecao = conecta_user()
  obj_id = ObjectId(id)

  try:
    resultado = colecao.delete_one({"_id": obj_id})
    if resultado.deleted_count > 0:
      print(f"✅ Pessoa com id {id} removida com sucesso!")
      return True
    else:
      print(f"❌ Nenhuma pessoa encontrada com id {id}")
      return False
  except Exception as e:
    print(f"❌ Erro ao deletar pessoa: {e}")
    return False

"""##2.2 Senha:"""

def atualizar_senha(email: str, senha_atual: str, nova_senha: str) -> bool:

    colecao = conecta_user()

    try:
        # Primeiro autentica o usuário
        usuario = autenticar_usuario(email, senha_atual)
        if not usuario:
            return False

        # Gera novo hash
        novo_hash = gerar_hash_senha(nova_senha)
        if not novo_hash:
            return False

        # Atualiza no banco de dados
        resultado = colecao.update_one(
            {"_id": usuario["_id"]},
            {"$set": {
                "senha": novo_hash,
                "updated_at": datetime.datetime.now(datetime.timezone.utc)
            }}
        )

        return resultado.modified_count > 0

    except Exception as e:
        print(f"Erro ao atualizar senha: {e}")
        return False

def validar_forca_senha(senha: str) -> bool:
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
    try:
        # Gera um salt aleatório
        salt = bcrypt.gensalt(rounds=12)  # rounds define o custo computacional (padrão é 12)

        # Cria o hash da senha
        hash_senha = bcrypt.hashpw(senha_plana.encode('utf-8'), salt)

        return hash_senha.decode('utf-8')  # Converte bytes para string

    except Exception as e:
        print(f"❌ Erro ao gerar hash da senha: {e}")
        return None

def verificar_senha(senha_plana: str, hash_armazenado: str) -> bool:
    try:
        # Converte a string hash de volta para bytes
        hash_bytes = hash_armazenado.encode('utf-8')

        # Verifica a correspondência
        return bcrypt.checkpw(senha_plana.encode('utf-8'), hash_bytes)

    except Exception as e:
        print(f"❌ Erro ao verificar senha: {e}")
        return False

"""#3. E-commerce"""

def cadastrar_ecommerce(nome: str, categoria: str, descricao: str, faixa_preco: int, url: str, plano: str, pros: str, contras: str):

    colecao = conecta_ecommerce()

    try:
        # Coletar dados do e-commerce
        print("\n--- Cadastro de E-commerce ---")
        ecommerce = {
            "_id": ObjectId(),  # Gerar um ObjectId automaticamente
            "nome": nome,
            "categoria": categoria,
            "descricao": descricao,
            "faixa-preco": faixa_preco,
            "url": url,
            "plano": plano,
            "pros": pros,
            "contras": contras,
            "created_at": datetime.datetime.now(datetime.timezone.utc),
            "updated_at": datetime.datetime.now(datetime.timezone.utc)
        }

        # Inserir no banco de dados
        resultado = colecao.insert_one(ecommerce)
        print(f"\n✅ E-commerce cadastrado com ID: {resultado.inserted_id}")

        return resultado.inserted_id

    except Exception as e:
        print(f"❌ Erro ao cadastrar e-commerce: {e}")
        return None


def listar_ecommerces():

    colecao = conecta_ecommerce()
    if colecao is None:
        print("❌ Erro ao listar e-commerces: Falha na conexão com o banco de dados.")
        return None

    lista_de_ecommerces = []
    try:
        # Ordena por 'nome'.
        for ecom_doc in colecao.find().sort("nome"):
            lista_de_ecommerces.append(ecom_doc)
        
        print(f"\n✅ {len(lista_de_ecommerces)} e-commerces listados do banco.")
            
        return lista_de_ecommerces
    except Exception as e:
        print(f"❌ Erro ao buscar ou processar lista de e-commerces: {e}")
        return None

def buscar_ecommerce_por_id(id):

    colecao = conecta_ecommerce()

    try:
        obj_id = ObjectId(id)

        ecommerce = colecao.find_one({"_id": obj_id})

        if ecommerce:
            print("\n🔍 E-commerce encontrado:")
            print(f"ID: {ecommerce['_id']}")
            print(f"Nome: {ecommerce['nome']}")
            print(f"Categoria: {ecommerce['categoria']}")
            print(f"Descrição: {ecommerce['descricao']}")
            print(f"Faixa de preço: {ecommerce.get('faixa-preco', 'Não informado')}")
            print(f"URL: {ecommerce.get('url', 'Não informada')}")
            print(f"Plano: {ecommerce.get('plano', 'Não informado')}")
            print(f"Pros: {', '.join(ecommerce.get('pros', []))}")
            print(f"Contras: {', '.join(ecommerce.get('contras', []))}")
            print(f"Atualizado em: {ecommerce['updated_at']}")
            return ecommerce
        else:
            print("❌ Nenhum e-commerce encontrado com este id")
            return None

    except Exception as e:
        print(f"❌ Erro ao buscar e-commerce: {e}")
        return None

def atualizar_ecommerce(id_ecommerce_str: str, dados_para_atualizar: dict) -> bool:

    colecao = conecta_ecommerce()
    if colecao is None:
        print("❌ Erro ao atualizar e-commerce: Falha na conexão com o banco de dados.")
        return False

    if not id_ecommerce_str or not isinstance(id_ecommerce_str, str):
        print("❌ Erro ao atualizar e-commerce: ID do e-commerce não fornecido ou inválido.")
        return False

    if not dados_para_atualizar or not isinstance(dados_para_atualizar, dict):
        print("⚠️ Nenhum dado fornecido para atualização do e-commerce.")
        return False 

    try:
        obj_id = ObjectId(id_ecommerce_str) # Converte o ID string para ObjectId

        dados_para_atualizar['updated_at'] = datetime.datetime.now(datetime.timezone.utc)

        resultado = colecao.update_one(
            {"_id": obj_id},
            {"$set": dados_para_atualizar}
        )

        if resultado.modified_count > 0:
            print(f"✅ E-commerce com ID {id_ecommerce_str} atualizado com sucesso!")
            return True
        elif resultado.matched_count > 0 and resultado.modified_count == 0:
            # Encontrou o documento, mas nada foi alterado (os novos valores podem ser iguais aos antigos)
            print(f"⚠️ E-commerce com ID {id_ecommerce_str} encontrado, mas nenhum dado foi efetivamente alterado.")
            return True
        else:
            # Não encontrou nenhum documento com o ID fornecido
            print(f"❌ Nenhum e-commerce encontrado com ID {id_ecommerce_str} para atualizar.")
            return False

    except InvalidId:
        print(f"❌ Erro ao atualizar e-commerce: O ID '{id_ecommerce_str}' fornecido é inválido.")
        return False
    except Exception as e:
        print(f"❌ Erro inesperado ao atualizar e-commerce: {e}")
        return False


def deletar_ecommerce(id_ecommerce_str: str) -> bool:

    colecao = conecta_ecommerce()
    if colecao is None:
        print("❌ Erro ao deletar e-commerce: Falha na conexão com o banco de dados.")
        return False

    if not id_ecommerce_str or not isinstance(id_ecommerce_str, str):
        print("❌ Erro ao deletar e-commerce: ID do e-commerce não fornecido ou é inválido.")
        return False

    try:
        obj_id = ObjectId(id_ecommerce_str) # Converte a string do ID para ObjectId

        resultado = colecao.delete_one({"_id": obj_id})

        if resultado.deleted_count > 0:
            print(f"✅ E-commerce com ID {id_ecommerce_str} removido com sucesso do banco!")
            return True
        else:
            # Nenhum documento foi deletado (pode ser que o ID não exista ou já foi deletado).
            print(f"❌ Nenhum e-commerce encontrado com ID {id_ecommerce_str} para deletar.")
            return False

    except InvalidId: # Trata o erro se o formato do ID for inválido para ObjectId
        print(f"❌ Erro ao deletar e-commerce: O ID '{id_ecommerce_str}' fornecido tem um formato inválido.")
        return False
    except Exception as e:
        print(f"❌ Erro inesperado ao tentar deletar e-commerce: {e}")
        return False

"""#4. Token"""

def armazenar_token(user_id, messages):
    try:
        colecao_tokens = conecta_token()
        if colecao_tokens is None:
            return None

        token_data = {
            "user_id": user_id,
            "messages": messages, #Lista de dicionários com as mensagens no formato: [{"role": "user/bot", "content": "texto da mensagem"}, ...]
            "updated_at": datetime.datetime.now(datetime.timezone.utc)
        }

        resultado = colecao_tokens.insert_one(token_data)
        print(f"Token armazenado com ID: {resultado.inserted_id}")
        return resultado.inserted_id #ObjectId do documento inserido ou None em caso de erro
    except Exception as e:
        print(f"❌ Erro ao armazenar token: {e}")
        return None

def buscar_tokens_por_usuario(user_id):
    try:
        colecao_tokens = conecta_token()
        if colecao_tokens is None:
            return None

        tokens = list(colecao_tokens.find({"user_id": user_id}).sort("updated_at", -1))
        if tokens:
          print(f"Tokens encontrados: {tokens}")
        else:
          print("Nenhum token encontrado")
        return tokens  #Lista de tokens ou None em caso de erro
    except Exception as e:
        print(f"❌ Erro ao buscar tokens: {e}")
        return None

"""#5. Menu:"""

def menu():
    while True:
        print("\n--- MENU PRINCIPAL ---")
        print("1. Gerenciar Pessoas")
        print("2. Gerenciar E-commerces")
        print("3. Gerenciar Tokens")
        print("0. Sair")

        opcao = input("Escolha uma opção: ")

        if opcao == "1":
            menu_pessoas()
        elif opcao == "2":
            menu_ecommerces()
        elif opcao == "3":
            menu_tokens()
        elif opcao == "0":
            print("Saindo do sistema...")
            break
        else:
            print("Opção inválida! Tente novamente.")

def menu_pessoas():
    while True:
        print("\n--- GERENCIAR PESSOAS ---")
        print("1. Cadastrar nova pessoa")
        print("2. Login")
        print("3. Listar todas as pessoas")
        print("4. Buscar pessoa")
        print("5. Alterar senha")
        print("6. Deletar pessoa")
        print("0. Voltar")

        opcao = input("Escolha uma opção: ")

        if opcao == "1":
            nome = input("Nome completo: ")
            telefone = input("Telefone: ")
            email = input("Email: ")
            data_nascimento = input("Data de nascimento (YYYY-MM-DD): ")
            while True:
                senha = input("Senha: ")
                if validar_forca_senha(senha):
                    break
                print("Por favor, crie uma senha mais forte.")
            cadastrar_pessoa(nome, telefone, email, data_nascimento, senha)

        elif opcao == "2":
            email = input("Email: ")
            senha = input("Senha: ")
            usuario = autenticar_usuario(email, senha)
            if usuario:
                print(f"Bem-vindo, {usuario['nome']}!")

        elif opcao == "3":
            listar_pessoas()

        elif opcao == "4":
            id = input("Digite o id para buscar: ")
            buscar_pessoa(id)

        elif opcao == "5":
            email = input("Email: ")
            senha_atual = input("Senha atual: ")
            nova_senha = input("Nova senha: ")
            if validar_forca_senha(nova_senha):
                if atualizar_senha(email, senha_atual, nova_senha):
                    print("Senha atualizada com sucesso!")
                else:
                    print("Falha ao atualizar senha. Verifique suas credenciais.")

        elif opcao == "6":
            id = (input("Digite o id da pessoa a deletar: "))
            deletar_pessoa(id)

        elif opcao == "0":
            break

        else:
            print("Opção inválida! Tente novamente.")

def menu_ecommerces():
    while True:
        print("\n--- GERENCIAR E-COMMERCES ---")
        print("1. Cadastrar novo e-commerce")
        print("2. Listar todos e-commerces")
        print("3. Buscar e-commerce")
        print("4. Atualizar e-commerce")
        print("5. Deletar e-commerce")
        print("0. Voltar")

        opcao = input("Escolha uma opção: ")

        if opcao == "1":
          nome = input("Digite o nome do e-commerce: ")
          categoria = input("Digite a categoria do e-commerce: ")
          descricao = input("Digite a descrição do e-commerce: ")
          faixa_preco = input("Digite a faixa de preço do e-commerce: ")
          url = input("Digite a URL do e-commerce: ")
          plano = input("Digite o plano do e-commerce: ")
          pros = input("Digite os pros do e-commerce (separados por vírgula): ").split(',')
          contras = input("Digite os contras do e-commerce (separados por vírgula): ").split(',')
          cadastrar_ecommerce(nome, categoria, descricao, faixa_preco, url, plano, pros, contras)

        elif opcao == "2":
            listar_ecommerces()

        elif opcao == "3":
            id = input("Digite o ID do e-commerce: ")
            buscar_ecommerce_por_id(id)

        elif opcao == "4":
            id = input("Digite o ID do e-commerce: ")
            atualizar_ecommerce(id)

        elif opcao == "5":
            id = input("Digite o ID do e-commerce: ")
            deletar_ecommerce(id)

        elif opcao == "0":
            break

        else:
            print("Opção inválida! Tente novamente.")

def menu_tokens():
    while True:
        print("\n--- GERENCIAR TOKENS ---")
        print("1. Armazenar token")
        print("2. Buscar tokens por usuário")
        print("0. Voltar")

        opcao = input("Escolha uma opção: ")

        if opcao == "1":
            id = input("Digite o ID do usuário: ")
            token = input("Digite o token: ")
            armazenar_token(id, token)

        elif opcao == "2":
            id = input("Digite o ID do usuário: ")
            buscar_tokens_por_usuario(id)

        elif opcao == "0":
            break

        else:
            print("Opção inválida! Tente novamente.")

if __name__ == "__main__":
    menu()