from decimal import Decimal
from bson import Decimal128
from flask import (
    Flask, render_template, request, redirect, url_for, flash, session
)
from forms import (
    LoginForm, CadastroForm, ContatoForm, BuscaForm, RecoveryPasswordForm
)
from models import Livro, Usuario, Pedido
from bson.objectid import ObjectId
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or 'uma_chave_secreta_muito_segura'


# --- Wrappers seguros para lidar com métodos de modelo não implementados ---
def _safe_list_call(func, *args, default=None, **kwargs):
    try:
        res = func(*args, **kwargs)
        if res is None:
            return default if default is not None else []
        return res
    except Exception:
        return default if default is not None else []


def _safe_tuple_call(func, *args, default_list=None, default_total=0, **kwargs):
    try:
        res = func(*args, **kwargs)
        if res is None:
            return (default_list or [], default_total)
        if isinstance(res, tuple) and len(res) == 2:
            lista, total = res
            if lista is None:
                lista = []
            if total is None:
                total = 0
            return lista, total
        if isinstance(res, list):
            return res, len(res)
        return (default_list or [], default_total)
    except Exception:
        return (default_list or [], default_total)


def _safe_single_call(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception:
        return None

# -------------------------------------------------------------------------

# Rota principal
@app.route('/')
def index():
    busca_form = BuscaForm()
    livros_destaque = _safe_list_call(Livro.buscar_todos)[:4]  # Exemplo: 4 livros em destaque
    return render_template('index.html', livros=livros_destaque, form=busca_form)

# Rota de busca
@app.route('/buscar')
def buscar():
    pagina = int(request.args.get('pagina', 1))
    nome = request.args.get('nome', '')
    preco_min = request.args.get('preco_min', None)
    preco_max = request.args.get('preco_max', None)
    categorias = request.args.getlist('categorias')
    tags_include = request.args.getlist('tags_include')
    tags_exclude = request.args.getlist('tags_exclude')
    
    form = BuscaForm()
    por_pagina = 12

    # Monta os filtros para a busca
    filtros = {}
    if nome:
        filtros['titulo'] = {'$regex': nome, '$options': 'i'}
    if preco_min:
        filtros['preco'] = {'$gte': Decimal128(Decimal(preco_min))}
    if preco_max:
        filtros.setdefault('preco', {})['$lte'] = Decimal128(Decimal(preco_max))
    if categorias:
        filtros['categoria'] = {'$in': categorias}
    if tags_include:
        filtros['tags'] = {'$all': tags_include}
    # Número de autores (exemplo: se for um filtro de igualdade)
    # if form.num_autores.data:
    #     filtros['numero_autores'] = int(form.num_autores.data)

    # Busca paginada via modelo (tratando métodos não implementados)
    livros, total = _safe_tuple_call(Livro.buscar_livros, filtros, pagina, por_pagina, default_list=[], default_total=0)
    total_paginas = (total // por_pagina) + (1 if total % por_pagina > 0 else 0)

    # Preenche o form com os valores dos filtros (para manter estado)
    if request.method == 'POST':
        form.process(request.form)

    return render_template(
        'catalogo.html',
        livros=livros,
        form=form,
        pagina=pagina,
        total_paginas=total_paginas,
        categorias=_safe_list_call(Livro.categorias_disponiveis),
        tags=_safe_list_call(Livro.tags_disponiveis)
    )

# Página do livro
@app.route('/livro/<id_livro>')
def livro(id_livro):
    livro = _safe_single_call(Livro.buscar_por_id, id_livro)
    if not livro:
        flash('Livro não encontrado!', 'error')
        return redirect(url_for('index'))
    return render_template('livro.html', livro=livro)

# Páginas institucionais
@app.route('/sobre')
def sobre():
    return render_template('about.html')

@app.route('/contato', methods=['GET', 'POST'])
def contato():
    form = ContatoForm()
    if request.method == 'POST' and form.validate_on_submit():
        # TODO: Enviar e-mail ou salvar mensagem
        flash('Mensagem enviada com sucesso!', 'success')
        return redirect(url_for('contato'))
    return render_template('contato.html', form=form)

@app.route('/faq')
def faq():
    return render_template('faq.html')

# Autenticação
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if request.method == 'POST' and form.validate_on_submit():
        usuario = _safe_single_call(Usuario.buscar_por_email, form.email.data)
        # TODO: Validar senha (usando bcrypt)
        if usuario:  # Exemplo: sem validação de senha
            session['user_id'] = str(usuario['_id'])
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('index'))
        flash('E-mail ou senha inválidos!', 'error')
    return render_template('login.html', form=form)

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    form = CadastroForm()
    if request.method == 'POST' and form.validate_on_submit():
        if form.senha.data != form.confirmar_senha.data:
            flash('As senhas não coincidem!', 'error')
        else:
            # TODO: Criptografar senha antes de salvar
            usuario = Usuario(
                nome=form.nome.data,
                email=form.email.data,
                senha=form.senha.data
            )
            try:
                usuario.salvar()
            except Exception:
                # Se o método não estiver implementado, notificamos o usuário sem quebrar a rota
                flash('Cadastro não concluído (implementação pendente).', 'warning')
                return redirect(url_for('register'))
            flash('Cadastro realizado com sucesso!', 'success')
            return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('index'))

# Área do cliente
@app.route('/minha-conta')
def minha_conta():
    if 'user_id' not in session:
        flash('Faça login para acessar sua conta.', 'warning')
        return redirect(url_for('login'))
    pedidos = _safe_list_call(Pedido.buscar_por_usuario, session['user_id'])
    return render_template('conta.html', pedidos=pedidos)

@app.route('/recuperar-senha', methods=['GET', 'POST'])
def recuperar_senha():
    form = RecoveryPasswordForm()
    if form.validate_on_submit():
        # Aqui você processa o e-mail, gera o link, envia e-mail, etc.
        flash('Se o e-mail estiver cadastrado, você receberá um link para redefinir sua senha.', 'success')
        return redirect(url_for('login'))
    return render_template('recovery_password.html', form=form)

if __name__ == '__main__':
    app.run(debug=True)