from flask import Flask, render_template, request, redirect, url_for, flash, send_file, Response
from models import db, Transaction, User
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import pandas as pd
from io import BytesIO

# تهيئة تطبيق Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_very_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///transactions.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        if user:
            flash('اسم المستخدم موجود بالفعل. الرجاء اختيار اسم آخر.')
        else:
            hashed_password = generate_password_hash(password)
            is_admin = not bool(User.query.count())
            new_user = User(username=username, password_hash=hashed_password, is_admin=is_admin)
            db.session.add(new_user)
            db.session.commit()
            flash('تم إنشاء حسابك بنجاح! يمكنك الآن تسجيل الدخول.')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('home'))
        else:
            flash('اسم المستخدم أو كلمة المرور غير صحيحة.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

def get_transactions():
    if current_user.is_admin:
        return Transaction.query.order_by(Transaction.date_added.desc()).all()
    else:
        return Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date_added.desc()).all()

@app.route('/')
@login_required
def home():
    transactions = get_transactions()
    balance = 0
    if not current_user.is_admin:
        for t in transactions:
            if t.type == 'إيراد':
                balance += t.amount
            elif t.type == 'مصروف' or t.type == 'سحب':
                balance -= t.amount
    return render_template('index.html', transactions=transactions, balance=balance, is_admin=current_user.is_admin)

@app.route('/add', methods=['POST'])
@login_required
def add_transaction():
    if request.method == 'POST':
        try:
            amount = float(request.form['amount'])
            description = request.form['description']
            trans_type = request.form['type']
            payment_method = request.form['payment_method']
            
            new_transaction = Transaction(
                amount=amount,
                description=description,
                type=trans_type,
                payment_method=payment_method,
                owner=current_user
            )
            
            db.session.add(new_transaction)
            db.session.commit()
            return redirect(url_for('home'))
        except (ValueError, KeyError) as e:
            flash(f"خطأ في الإدخال: {e}")
            return redirect(url_for('home'))

@app.route('/delete/<int:transaction_id>')
@login_required
def delete_transaction(transaction_id):
    transaction_to_delete = Transaction.query.get_or_404(transaction_id)
    if not current_user.is_admin and transaction_to_delete.owner != current_user:
        flash("غير مصرح لك بحذف هذه المعاملة.")
        return redirect(url_for('home'))

    db.session.delete(transaction_to_delete)
    db.session.commit()
    return redirect(url_for('home'))

# --- دوال التقارير الجديدة ---
@app.route('/reports/monthly')
@login_required
def monthly_report():
    transactions = get_transactions()
    if not transactions:
        flash('لا توجد معاملات لعرض التقرير.')
        return redirect(url_for('home'))
    
    df = pd.DataFrame([t.__dict__ for t in transactions])
    df['date_added'] = pd.to_datetime(df['date_added'])
    df['month_year'] = df['date_added'].dt.to_period('M').astype(str)
    
    report_data = []
    
    for month_year, group in df.groupby('month_year'):
        cash_income = group[(group['type'] == 'إيراد') & (group['payment_method'] == 'كاش')]['amount'].sum()
        card_income = group[(group['type'] == 'إيراد') & (group['payment_method'] == 'شبكة')]['amount'].sum()
        cash_expenses = group[(group['type'] == 'مصروف') & (group['payment_method'] == 'كاش')]['amount'].sum()
        card_expenses = group[(group['type'] == 'مصروف') & (group['payment_method'] == 'شبكة')]['amount'].sum()
        cash_withdrawals = group[(group['type'] == 'سحب') & (group['payment_method'] == 'كاش')]['amount'].sum()
        card_withdrawals = group[(group['type'] == 'سحب') & (group['payment_method'] == 'شبكة')]['amount'].sum()
        report_data.append([month_year, cash_income, card_income, cash_expenses, card_expenses, cash_withdrawals, card_withdrawals])
        
    report_df = pd.DataFrame(report_data, columns=['الشهر', 'إيرادات الكاش', 'إيرادات الشبكة', 'مصروفات الكاش', 'مصروفات الشبكة', 'سحبيات الكاش', 'سحبيات الشبكة'])
    
    return render_template('monthly_report.html', report=report_df.to_dict('records'))

@app.route('/reports/yearly')
@login_required
def yearly_report():
    transactions = get_transactions()
    if not transactions:
        flash('لا توجد معاملات لعرض التقرير.')
        return redirect(url_for('home'))

    df = pd.DataFrame([t.__dict__ for t in transactions])
    df['date_added'] = pd.to_datetime(df['date_added'])
    df['year'] = df['date_added'].dt.year
    
    report_data = []
    
    for year, group in df.groupby('year'):
        cash_income = group[(group['type'] == 'إيراد') & (group['payment_method'] == 'كاش')]['amount'].sum()
        card_income = group[(group['type'] == 'إيراد') & (group['payment_method'] == 'شبكة')]['amount'].sum()
        cash_expenses = group[(group['type'] == 'مصروف') & (group['payment_method'] == 'كاش')]['amount'].sum()
        card_expenses = group[(group['type'] == 'مصروف') & (group['payment_method'] == 'شبكة')]['amount'].sum()
        cash_withdrawals = group[(group['type'] == 'سحب') & (group['payment_method'] == 'كاش')]['amount'].sum()
        card_withdrawals = group[(group['type'] == 'سحب') & (group['payment_method'] == 'شبكة')]['amount'].sum()
        report_data.append([year, cash_income, card_income, cash_expenses, card_expenses, cash_withdrawals, card_withdrawals])
        
    report_df = pd.DataFrame(report_data, columns=['السنة', 'إيرادات الكاش', 'إيرادات الشبكة', 'مصروفات الكاش', 'مصروفات الشبكة', 'سحبيات الكاش', 'سحبيات الشبكة'])
    
    return render_template('yearly_report.html', report=report_df.to_dict('records'))

@app.route('/reports/custom', methods=['GET', 'POST'])
@login_required
def custom_report():
    report_data = None
    if request.method == 'POST':
        start_date_str = request.form['start_date']
        end_date_str = request.form['end_date']
        
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)

        transactions = get_transactions()
        df = pd.DataFrame([t.__dict__ for t in transactions])
        df['date_added'] = pd.to_datetime(df['date_added'])

        filtered_df = df[(df['date_added'] >= start_date) & (df['date_added'] <= end_date)].copy()
        
        if filtered_df.empty:
            flash('لا توجد معاملات في النطاق الزمني المحدد.')
        else:
            cash_income = filtered_df[(filtered_df['type'] == 'إيراد') & (filtered_df['payment_method'] == 'كاش')]['amount'].sum()
            card_income = filtered_df[(filtered_df['type'] == 'إيراد') & (filtered_df['payment_method'] == 'شبكة')]['amount'].sum()
            cash_expenses = filtered_df[(filtered_df['type'] == 'مصروف') & (filtered_df['payment_method'] == 'كاش')]['amount'].sum()
            card_expenses = filtered_df[(filtered_df['type'] == 'مصروف') & (filtered_df['payment_method'] == 'شبكة')]['amount'].sum()
            cash_withdrawals = filtered_df[(filtered_df['type'] == 'سحب') & (filtered_df['payment_method'] == 'كاش')]['amount'].sum()
            card_withdrawals = filtered_df[(filtered_df['type'] == 'سحب') & (filtered_df['payment_method'] == 'شبكة')]['amount'].sum()
            
            report_data = {
                'cash_income': cash_income,
                'card_income': card_income,
                'cash_expenses': cash_expenses,
                'card_expenses': card_expenses,
                'cash_withdrawals': cash_withdrawals,
                'card_withdrawals': card_withdrawals,
            }

    return render_template('custom_report.html', report=report_data)

@app.route('/export/<report_type>')
@login_required
def export_excel(report_type):
    transactions = get_transactions()
    if not transactions:
        flash('لا توجد بيانات للتصدير.')
        return redirect(url_for('home'))

    df = pd.DataFrame([t.__dict__ for t in transactions])
    df['date_added'] = pd.to_datetime(df['date_added'])

    if report_type == 'monthly':
        df['month_year'] = df['date_added'].dt.to_period('M').astype(str)
        report_df = df.groupby('month_year').agg(
            إيرادات_كاش=('amount', lambda x: x[df.loc[x.index, 'type'] == 'إيراد'][df.loc[x.index, 'payment_method'] == 'كاش'].sum()),
            إيرادات_شبكة=('amount', lambda x: x[df.loc[x.index, 'type'] == 'إيراد'][df.loc[x.index, 'payment_method'] == 'شبكة'].sum()),
            مصروفات_كاش=('amount', lambda x: x[df.loc[x.index, 'type'] == 'مصروف'][df.loc[x.index, 'payment_method'] == 'كاش'].sum()),
            مصروفات_شبكة=('amount', lambda x: x[df.loc[x.index, 'type'] == 'مصروف'][df.loc[x.index, 'payment_method'] == 'شبكة'].sum()),
            سحبيات_كاش=('amount', lambda x: x[df.loc[x.index, 'type'] == 'سحب'][df.loc[x.index, 'payment_method'] == 'كاش'].sum()),
            سحبيات_شبكة=('amount', lambda x: x[df.loc[x.index, 'type'] == 'سحب'][df.loc[x.index, 'payment_method'] == 'شبكة'].sum())
        ).reset_index()
        file_name = f'تقرير_شهري_{datetime.now().strftime("%Y-%m-%d")}.xlsx'
    
    elif report_type == 'yearly':
        df['year'] = df['date_added'].dt.year
        report_df = df.groupby('year').agg(
            إيرادات_كاش=('amount', lambda x: x[df.loc[x.index, 'type'] == 'إيراد'][df.loc[x.index, 'payment_method'] == 'كاش'].sum()),
            إيرادات_شبكة=('amount', lambda x: x[df.loc[x.index, 'type'] == 'إيراد'][df.loc[x.index, 'payment_method'] == 'شبكة'].sum()),
            مصروفات_كاش=('amount', lambda x: x[df.loc[x.index, 'type'] == 'مصروف'][df.loc[x.index, 'payment_method'] == 'كاش'].sum()),
            مصروفات_شبكة=('amount', lambda x: x[df.loc[x.index, 'type'] == 'مصروف'][df.loc[x.index, 'payment_method'] == 'شبكة'].sum()),
            سحبيات_كاش=('amount', lambda x: x[df.loc[x.index, 'type'] == 'سحب'][df.loc[x.index, 'payment_method'] == 'كاش'].sum()),
            سحبيات_شبكة=('amount', lambda x: x[df.loc[x.index, 'type'] == 'سحب'][df.loc[x.index, 'payment_method'] == 'شبكة'].sum())
        ).reset_index()
        file_name = f'تقرير_سنوي_{datetime.now().strftime("%Y-%m-%d")}.xlsx'
    
    elif report_type == 'custom':
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)

        filtered_df = df[(df['date_added'] >= start_date) & (df['date_added'] <= end_date)]
        if filtered_df.empty:
            flash('لا توجد بيانات في النطاق المحدد للتصدير.')
            return redirect(url_for('custom_report'))
        
        report_df = filtered_df
        file_name = f'تقرير_مخصص_{start_date_str}_إلى_{end_date_str}.xlsx'

    else:
        flash('نوع التقرير غير صالح.')
        return redirect(url_for('home'))

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        report_df.to_excel(writer, index=False, sheet_name='تقرير')
    output.seek(0)
    
    return send_file(output, as_attachment=True, download_name=file_name, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# هذا السطر ضروري ليعمل التطبيق على الخوادم مثل Render
if __name__ == '__main__':
    app.run()