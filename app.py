from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

# Importa as classes de banco de dados do arquivo models.py
from models import db, User, Student, Guardian, Fee

app = Flask(__name__)

# --- CONFIGURAÇÕES ---
# Chave secreta (Importante para Sessões)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'chave-secreta-dev-local')

# Conexão com Banco de Dados (SQLite local ou PostgreSQL no Render)
db_url = os.environ.get('DATABASE_URL', 'sqlite:///escola.db')
# Correção necessária para o Render/Heroku reconhecer o link do Postgres
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'index'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ROTAS ---

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    
    user = User.query.filter_by(username=username).first()
    
    if user and check_password_hash(user.password, password):
        login_user(user)
        return redirect(url_for('dashboard'))
    else:
        flash('Usuário ou senha incorretos.', 'error')
        return redirect(url_for('index'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    total_students = Student.query.count()
    total_fees = Fee.query.filter_by(status='pago').count()
    pending_fees = Fee.query.filter_by(status='pendente').count()
    
    # Cálculo financeiro simples
    receita = sum([f.amount for f in Fee.query.filter_by(status='pago').all()])
    pendente = sum([f.amount for f in Fee.query.filter_by(status='pendente').all()])

    return render_template('dashboard.html', 
                           student_count=total_students, 
                           paid=total_fees, 
                           pending=pending_fees,
                           receita=receita,
                           pendente_val=pendente)

@app.route('/students')
@login_required
def students():
    students = Student.query.all()
    return render_template('students.html', students=students)

@app.route('/students/add', methods=['POST'])
@login_required
def add_student():
    name = request.form.get('name')
    birth = request.form.get('birth')
    class_name = request.form.get('class_name')
    guardian_name = request.form.get('guardian_name')
    
    # Lógica para buscar ou criar responsável
    guardian = Guardian.query.filter_by(name=guardian_name).first()
    if not guardian:
        guardian = Guardian(name=guardian_name, phone='', relation='', cpf='')
        db.session.add(guardian)
        db.session.commit()
    
    new_student = Student(name=name, birth_date=datetime.strptime(birth, '%Y-%m-%d'), class_name=class_name, guardian_id=guardian.id)
    db.session.add(new_student)
    db.session.commit()
    
    flash(f'Aluno {name} cadastrado com sucesso!')
    return redirect(url_for('students'))

@app.route('/students/delete/<int:id>')
@login_required
def delete_student(id):
    student = Student.query.get_or_404(id)
    db.session.delete(student)
    db.session.commit()
    flash('Aluno removido.')
    return redirect(url_for('students'))

@app.route('/finance')
@login_required
def finance():
    fees = Fee.query.order_by(Fee.due_date.desc()).all()
    # CORREÇÃO IMPORTANTE: Passar a lista 'students' para o template finance.html
    students = Student.query.all() 
    return render_template('finance.html', fees=fees, students=students)

@app.route('/finance/add', methods=['POST'])
@login_required
def add_fee():
    student_id = request.form.get('student_id')
    month = request.form.get('month')
    amount = float(request.form.get('amount'))
    due_date = request.form.get('due_date')
    
    new_fee = Fee(student_id=student_id, month=month, amount=amount, due_date=datetime.strptime(due_date, '%Y-%m-%d'), status='pendente')
    db.session.add(new_fee)
    db.session.commit()
    flash('Mensalidade gerada.')
    return redirect(url_for('finance'))

@app.route('/finance/pay/<int:id>')
@login_required
def pay_fee(id):
    fee = Fee.query.get_or_404(id)
    fee.status = 'pago'
    fee.payment_date = datetime.now()
    db.session.commit()
    flash('Pagamento registrado com sucesso!')
    return redirect(url_for('finance'))

# --- INICIALIZAÇÃO DO BANCO DE DADOS ---
# Este bloco garante que as tabelas sejam criadas assim que o app rodar
# Tanto no seu PC quanto no Render.

with app.app_context():
    db.create_all()
    # Cria o Admin se não existir
# ... Dentro do bloco with app.app_context(): ...

    if not User.query.filter_by(username='admin').first():
        # ADICIONE 'method="pbkdf2:sha256"' conforme abaixo para encurtar a senha:
        admin = User(
            username='admin', 
            password=generate_password_hash('123', method='pbkdf2:sha256'), 
            role='director'
        )
        db.session.add(admin)
        db.session.commit()
        print("Usuário Admin criado automaticamente: admin / 123")

if __name__ == '__main__':
    # Lê a porta definida pelo Render, se não houver usa 5000
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)