from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
from flask import send_file
import io
from fpdf import FPDF

# Importa as classes de banco de dados do arquivo models.py
from models import db, User, Student, Guardian, Fee, Teacher, Class

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
    
@app.route('/students/edit', methods=['POST'])
@login_required
def edit_student():
    student_id = request.form.get('id')
    student = Student.query.get_or_404(student_id)
    
    student.name = request.form.get('name')
    student.birth_date = datetime.strptime(request.form.get('birth'), '%Y-%m-%d')
    student.class_name = request.form.get('class_name')
    
    # Nota: Se quiser trocar o responsável no futuro, precisaria adicionar a lógica aqui também
    
    db.session.commit()
    flash('Dados do aluno atualizados!')
    return redirect(url_for('students'))
    
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
    # ... código anterior (pay_fee) ...

@app.route('/finance/receipt/<int:id>')
@login_required
def generate_receipt(id):
    fee = Fee.query.get_or_404(id)
    student = fee.student
    
    # 1. Segurança: Verifica se o aluno e responsável existem
    guardian_name = "Não informado"
    if student and student.guardian:
        guardian_name = student.guardian.name

    # 2. Segurança: Verifica se a data de pagamento existe
    pay_date_str = "N/D"
    if fee.payment_date:
        pay_date_str = fee.payment_date.strftime('%d/%m/%Y')

    # Função auxiliar para remover acentos (com segurança)
    def remover_acentos(txt):
        if not txt: return ""
        try:
            return unicodedata.normalize('NFKD', txt).encode('ASCII', 'ignore').decode('ASCII')
        except:
            return txt

    pdf = FPDF()
    pdf.add_page()
    
    # Cabeçalho
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(200, 10, remover_acentos('Escola Renascher'), ln=True, align='C')
    
    pdf.set_font('Arial', 'I', 12)
    pdf.cell(200, 6, remover_acentos('Comprovante de Pagamento'), ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, 40, 200, 40)
    pdf.ln(10)
    
    # Dados do Recibo
    pdf.set_font('Arial', '', 12)
    pdf.cell(200, 8, f'ID do Pagamento: #{fee.id}', ln=True)
    pdf.cell(200, 8, f'Data de Emissao: {datetime.now().strftime("%d/%m/%Y")}', ln=True)
    pdf.cell(200, 8, f'Data do Pagamento: {pay_date_str}', ln=True)
    pdf.ln(5)
    
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(40, 8, remover_acentos('Aluno(a):'), ln=False)
    pdf.set_font('Arial', '', 12)
    pdf.cell(160, 8, remover_acentos(student.name), ln=True)
    
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(40, 8, remover_acentos('Responsavel:'), ln=False)
    pdf.set_font('Arial', '', 12)
    pdf.cell(160, 8, remover_acentos(guardian_name), ln=True)
    
    pdf.ln(10)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(40, 8, remover_acentos('Referencia:'), ln=False)
    pdf.set_font('Arial', '', 12)
    pdf.cell(160, 8, remover_acentos(fee.month), ln=True)
    
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(40, 8, remover_acentos('Valor Pago:'), ln=False)
    pdf.set_font('Arial', '', 12)
    pdf.cell(160, 8, f'R$ {fee.amount:.2f}', ln=True)
    
    pdf.ln(40)
    pdf.line(60, 200, 150, 200)
    pdf.set_font('Arial', 'I', 10)
    pdf.cell(200, 8, remover_acentos('Assinatura da Direcao'), ln=True, align='C')
    pdf.set_font('Arial', '', 8)
    pdf.cell(200, 8, remover_acentos('Documento emitido eletronicamente.'), ln=True, align='C')

    # --- CORREÇÃO DEFINITIVA ---
    # O output() já retorna um bytearray (binário), então passamos direto pro buffer
    pdf_bytes = pdf.output(dest='S')
    buffer = io.BytesIO(pdf_bytes)
    buffer.seek(0)
    # --------------------------

    return send_file(
        buffer, 
        as_attachment=True, 
        download_name=f'recibo_{fee.month}_{student.name}.pdf',
        mimetype='application/pdf'
    )

# --- CRUD PROFESSORES ---

@app.route('/teachers')
@login_required
def teachers():
    teachers = Teacher.query.all()
    return render_template('teachers.html', teachers=teachers)

@app.route('/teachers/add', methods=['POST'])
@login_required
def add_teacher():
    name = request.form.get('name')
    subject = request.form.get('subject')
    phone = request.form.get('phone')
    
    new_teacher = Teacher(name=name, subject=subject, phone=phone)
    db.session.add(new_teacher)
    db.session.commit()
    flash('Professor cadastrado com sucesso!')
    return redirect(url_for('teachers'))

@app.route('/teachers/edit', methods=['POST'])
@login_required
def edit_teacher():
    teacher_id = request.form.get('id') # Recebe ID oculto do formulário
    teacher = Teacher.query.get_or_404(teacher_id)
    
    teacher.name = request.form.get('name')
    teacher.subject = request.form.get('subject')
    teacher.phone = request.form.get('phone')
    
    db.session.commit()
    flash('Dados do professor atualizados!')
    return redirect(url_for('teachers'))

@app.route('/teachers/delete/<int:id>')
@login_required
def delete_teacher(id):
    if current_user.role != 'director':
        flash('Apenas diretores podem excluir.', 'error')
        return redirect(url_for('teachers'))
        
    teacher = Teacher.query.get_or_404(id)
    db.session.delete(teacher)
    db.session.commit()
    flash('Professor removido.')
    return redirect(url_for('teachers'))


# --- CRUD TURMAS ---

@app.route('/classes')
@login_required
def classes_list():
    classes = Class.query.order_by(Class.year.desc(), Class.name).all()
    teachers = Teacher.query.all() # Para o select box
    return render_template('classes.html', classes=classes, teachers=teachers)

@app.route('/classes/add', methods=['POST'])
@login_required
def add_class():
    name = request.form.get('name')
    year = int(request.form.get('year'))
    teacher_id = request.form.get('teacher_id') if request.form.get('teacher_id') else None
    
    new_class = Class(name=name, year=year, teacher_id=teacher_id)
    db.session.add(new_class)
    db.session.commit()
    flash('Turma criada com sucesso!')
    return redirect(url_for('classes_list'))

@app.route('/classes/edit', methods=['POST'])
@login_required
def edit_class():
    class_id = request.form.get('id')
    turma = Class.query.get_or_404(class_id)
    
    turma.name = request.form.get('name')
    turma.year = int(request.form.get('year'))
    turma.teacher_id = request.form.get('teacher_id') if request.form.get('teacher_id') else None
    
    db.session.commit()
    flash('Turma atualizada!')
    return redirect(url_for('classes_list'))

@app.route('/classes/delete/<int:id>')
@login_required
def delete_class(id):
    if current_user.role != 'director':
        flash('Apenas diretores podem excluir.', 'error')
        return redirect(url_for('classes_list'))
        
    turma = Class.query.get_or_404(id)
    db.session.delete(turma)
    db.session.commit()
    flash('Turma removida.')
    return redirect(url_for('classes_list'))

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