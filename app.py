from flask import Flask, render_template, request, redirect, url_for, flash
from sqlalchemy import extract
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
    
    # --- DADOS PARA GRÁFICO DE RECEITA MENSAL ---
    # Lista de todos os meses
    meses_ordem = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
    
    # Calcula receita por mês
    receitas_por_mes = []
    for mes in meses_ordem:
        # Soma todos os pagamentos daquele mês
        valor = db.session.query(db.func.sum(Fee.amount)).filter(
            Fee.month == mes, 
            Fee.status == 'pago'
        ).scalar()
        # Se não houver dados, valor é 0
        receitas_por_mes.append(valor if valor else 0)

    # --- DADOS PARA GRÁFICO DE TURMAS ---
    # Pega as turmas que existem e conta quantos alunos têm (baseado no campo class_name do aluno)
    turmas_distintas = db.session.query(Student.class_name).distinct().all()
    nomes_turmas = [t[0] for t in turmas_distintas]
    
    alunos_por_turma = []
    for nome_turma in nomes_turmas:
        total = Student.query.filter_by(class_name=nome_turma).count()
        alunos_por_turma.append(total)

    # KPIs Financeiros Totais
    receita_total = sum(receitas_por_mes)
    pendente_total = sum([f.amount for f in Fee.query.filter_by(status='pendente').all()])

    return render_template('dashboard.html', 
                           student_count=total_students, 
                           paid=total_fees, 
                           pending=pending_fees,
                           receita_total=receita_total,
                           pendente_total=pendente_total,
                           meses=meses_ordem,
                           valores_receita=receitas_por_mes,
                           nomes_turmas=nomes_turmas,
                           alunos_turma=alunos_por_turma
                           )

@app.route('/students')
@login_required
def students():
    students = Student.query.all()
    # Busca responsáveis e turmas para os Dropdowns
    guardians = Guardian.query.all()
    classes = Class.query.all()
    return render_template('students.html', students=students, guardians=guardians, classes=classes)

@app.route('/students/add', methods=['POST'])
@login_required
def add_student():
    name = request.form.get('name')
    birth = request.form.get('birth')
    
    # Recebe o ID do responsável (selecionado no dropdown) ou cria novo se for "novo"
    guardian_id = request.form.get('guardian_id')
    new_guardian_name = request.form.get('new_guardian_name')

    if new_guardian_name:
        # Se digitou um nome novo, cria o responsável
        guardian = Guardian(name=new_guardian_name, phone='', relation='', cpf='')
        db.session.add(guardian)
        db.session.commit()
        student_guardian_id = guardian.id
    else:
        # Se selecionou no dropdown, usa o ID
        student_guardian_id = guardian_id if guardian_id else None

    # Recebe o nome da turma (dropdown ou texto)
    class_name = request.form.get('class_name')
    
    new_student = Student(name=name, birth_date=datetime.strptime(birth, '%Y-%m-%d'), class_name=class_name, guardian_id=student_guardian_id)
    db.session.add(new_student)
    db.session.commit()
    
    flash(f'Aluno {name} cadastrado com sucesso!')
    return redirect(url_for('students'))
    
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
    students = Student.query.all() # Necessário para o modal de geração
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

@app.route('/finance/bulk', methods=['POST'])
@login_required
def bulk_fees():
    month = request.form.get('month')
    year = request.form.get('year')
    base_value = float(request.form.get('amount'))
    discount = float(request.form.get('discount', 0))
    
    final_amount = base_value - discount
    
    due_date_str = request.form.get('due_date')
    due_date = datetime.strptime(due_date_str, '%Y-%m-%d') if due_date_str else None
    
    students = Student.query.all()
    created_count = 0
    
    for s in students:
        # Verifica se não existe mensalidade para este aluno neste mês
        existing = Fee.query.filter_by(student_id=student.id, month=mes).filter(extract('year', Fee.due_date) == current_year).first()
        if not existing:
            new_fee = Fee(
                student_id=s.id, 
                month=month, 
                amount=final_amount, 
                due_date=due_date, 
                status='pendente'
            )
            db.session.add(new_fee)
            created_count += 1
            
    db.session.commit()
    flash(f'{created_count} mensalidades geradas para {month}!')
    return redirect(url_for('finance'))

@app.route('/finance/edit', methods=['POST'])
@login_required
def edit_fee():
    fee_id = request.form.get('id')
    fee = Fee.query.get_or_404(fee_id)
    
    fee.amount = float(request.form.get('amount'))
    fee.due_date = datetime.strptime(request.form.get('due_date'), '%Y-%m-%d')
    fee.status = request.form.get('status')
    
    if fee.status == 'pago':
        fee.payment_date = datetime.now()
    else:
        fee.payment_date = None # Se voltar para pendente, apaga data pagamento
        
    db.session.commit()
    flash('Mensalidade atualizada!')
    return redirect(url_for('finance'))

# Mapeamento de meses para números (para criar a data correta)
MONTHS_MAP = {
    'Janeiro': 1, 'Fevereiro': 2, 'Março': 3, 'Abril': 4, 'Maio': 5, 'Junho': 6,
    'Julho': 7, 'Agosto': 8, 'Setembro': 9, 'Outubro': 10, 'Novembro': 11, 'Dezembro': 12
}

@app.route('/finance/yearly', methods=['POST'])
@login_required
def generate_yearly_fees():
    student_id = request.form.get('student_id')
    base_value = float(request.form.get('amount'))
    discount = float(request.form.get('discount', 0))
    due_day = int(request.form.get('due_day')) # Dia do mês (ex: dia 10)
    
    student = Student.query.get_or_404(student_id)
    current_year = datetime.now().year
    
    final_amount = base_value - discount
    created_count = 0

    for mes, num_mes in MONTHS_MAP.items():
        # Tenta criar a data. Se o dia for 30/31 e o mês for Fevereiro, ajusta para o dia 28
        try:
            due_date = datetime(current_year, num_mes, due_day).date()
        except ValueError:
            due_date = datetime(current_year, num_mes, 28).date()

        # Verifica se já existe mensalidade para este aluno neste mês
        existing = Fee.query.filter_by(student_id=student.id, month=mes).filter(Fee.due_date.like(f'%{current_year}%')).first()
        
        if not existing:
            new_fee = Fee(
                student_id=student.id, 
                month=mes, 
                amount=final_amount, 
                due_date=due_date, 
                status='pendente'
            )
            db.session.add(new_fee)
            created_count += 1
            
    db.session.commit()
    flash(f'{created_count} mensalidades geradas para {student.name}!')
    return redirect(url_for('finance'))    

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
    pdf.cell(200, 10, remover_acentos('Escola Renascer'), ln=True, align='C')
    
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