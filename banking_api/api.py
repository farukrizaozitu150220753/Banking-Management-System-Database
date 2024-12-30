from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid
from sqlalchemy.dialects.mysql import BINARY
from sqlalchemy.ext.hybrid import hybrid_property
from flask_restful import Resource, Api, reqparse, fields, marshal_with, abort

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///banking_management.db'
db = SQLAlchemy(app)
api = Api(app)

def generate_uuid():
    return uuid.uuid4().bytes

class Branch(db.Model):
    __tablename__ = 'branch'
    
    branch_id = db.Column(BINARY(16), primary_key=True, default=generate_uuid)
    branch_name = db.Column(db.String(255), unique=True, nullable=False)
    address_line1 = db.Column(db.String(255), nullable=False)
    address_line2 = db.Column(db.String(255))
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100), nullable=False)
    zip_code = db.Column(db.String(20), nullable=False)
    phone_number = db.Column(db.String(15), unique=True, nullable=False)

    # Relationships
    customers = db.relationship('Customer', backref='branch', lazy=True)
    employees = db.relationship('Employee', backref='branch', lazy=True)

    def __repr__(self):
        return f"Branch(branch_id = {self.branch_id}, branch_name = {self.branch_name}, address_line1 = {self.address_line1}, address_line2 = {self.address_line2}, city = {self.city}, state = {self.state}, zip_code = {self.zip_code}, phone_number = {self.phone_number})"

class Customer(db.Model):
    __tablename__ = 'customer'
    
    customer_id = db.Column(BINARY(16), primary_key=True, default=generate_uuid)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    phone_number = db.Column(db.String(15), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    address_line1 = db.Column(db.String(255), nullable=False)
    address_line2 = db.Column(db.String(255))
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100), nullable=False)
    zip_code = db.Column(db.String(20), nullable=False)
    branch_id = db.Column(BINARY(16), db.ForeignKey('branch.branch_id'), nullable=False)

    # Relationships
    accounts = db.relationship('Account', backref='customer', lazy=True)
    loans = db.relationship('Loan', backref='customer', lazy=True)
    support_tickets = db.relationship('CustomerSupport', backref='customer', lazy=True)
    credit_score = db.relationship('CreditScore', backref='customer', uselist=False, lazy=True)

    def __repr__(self):
        return f"Customer(customer_id = {self.customer_id}, first_name = {self.first_name}, last_name = {self.last_name}, date_of_birth = {self.date_of_birth}, phone_number = {self.phone_number}, email = {self.email}, address_line1 = {self.address_line1}, address_line2 = {self.address_line2}, city = {self.city}, state = {self.state}, zip_code = {self.zip_code}, branch_id = {self.branch_id})"

class Account(db.Model):
    __tablename__ = 'account'
    
    account_id = db.Column(BINARY(16), primary_key=True, default=generate_uuid)
    customer_id = db.Column(BINARY(16), db.ForeignKey('customer.customer_id'), nullable=False)
    account_type = db.Column(db.Enum('CHECKING', 'SAVINGS'), nullable=False)
    balance = db.Column(db.Numeric(15, 2), nullable=False, default=0.00)
    creation_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    cards = db.relationship('Card', backref='account', lazy=True)
    outgoing_transactions = db.relationship('Transaction', 
                                         foreign_keys='Transaction.from_account_id',
                                         backref='from_account', lazy=True)
    incoming_transactions = db.relationship('Transaction',
                                         foreign_keys='Transaction.to_account_id',
                                         backref='to_account', lazy=True)

    __table_args__ = (
        db.CheckConstraint('balance >= 0', name='check_balance_positive'),
    )
    
    def __repr__(self):
        return f"Account(account_id = {self.account_id}, customer_id = {self.customer_id}, account_type = {self.account_type}, balance = {self.balance}, creation_date = {self.creation_date})"


class Loan(db.Model):
    __tablename__ = 'loan'
    
    loan_id = db.Column(BINARY(16), primary_key=True, default=generate_uuid)
    customer_id = db.Column(BINARY(16), db.ForeignKey('customer.customer_id'), nullable=False)
    loan_type = db.Column(db.Enum('HOME', 'AUTO', 'PERSONAL'), nullable=False)
    principal_amount = db.Column(db.Numeric(15, 2), nullable=False)
    interest_rate = db.Column(db.Numeric(5, 2), nullable=False, default=0.00)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.Enum('ACTIVE', 'PAID_OFF', 'DEFAULT'), nullable=False, default='ACTIVE')

    # Relationships
    payments = db.relationship('LoanPayment', backref='loan', lazy=True)

    __table_args__ = (
        db.CheckConstraint('principal_amount > 0', name='check_principal_positive'),
        db.CheckConstraint('interest_rate >= 0', name='check_interest_non_negative'),
        db.CheckConstraint('start_date < end_date', name='check_dates_valid'),
    )
    
    def __repr__(self):
        return f"Loan(loan_id = {self.loan_id}, customer_id = {self.customer_id}, loan_type = {self.loan_type}, principal_amount = {self.principal_amount}, interest_rate = {self.interest_rate}, start_date = {self.start_date}, end_date = {self.end_date}, status = {self.status})"

class LoanPayment(db.Model):
    __tablename__ = 'loan_payment'
    
    loan_payment_id = db.Column(BINARY(16), primary_key=True, default=generate_uuid)
    loan_id = db.Column(BINARY(16), db.ForeignKey('loan.loan_id'), nullable=False)
    payment_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    payment_amount = db.Column(db.Numeric(15, 2), nullable=False)
    remaining_balance = db.Column(db.Numeric(15, 2), nullable=False)

    __table_args__ = (
        db.CheckConstraint('payment_amount > 0', name='check_payment_positive'),
        db.CheckConstraint('remaining_balance >= 0', name='check_remaining_non_negative'),
    )
    
    def __repr__(self):
        return f"LoanPayment(loan_payment_id = {self.loan_payment_id}, loan_id = {self.loan_id}, payment_date = {self.payment_date}, payment_amount = {self.payment_amount}, remaining_balance = {self.remaining_balance})"

class Employee(db.Model):
    __tablename__ = 'employee'
    
    employee_id = db.Column(BINARY(16), primary_key=True, default=generate_uuid)
    branch_id = db.Column(BINARY(16), db.ForeignKey('branch.branch_id'), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    position = db.Column(db.String(100), nullable=False)
    hire_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    phone_number = db.Column(db.String(15), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
        
    def __repr__(self):
        return f"Employee(employee_id = {self.employee_id}, branch_id = {self.branch_id}, first_name = {self.first_name}, last_name = {self.last_name}, position = {self.position}, hire_date = {self.hire_date}, phone_number = {self.phone_number}, email = {self.email})"

class Card(db.Model):
    __tablename__ = 'card'
    
    card_id = db.Column(BINARY(16), primary_key=True, default=generate_uuid)
    account_id = db.Column(BINARY(16), db.ForeignKey('account.account_id'), nullable=False)
    card_type = db.Column(db.Enum('DEBIT', 'CREDIT'), nullable=False)
    card_number = db.Column(db.String(16), unique=True, nullable=False)
    expiration_date = db.Column(db.Date, nullable=False)
    cvv = db.Column(db.String(3), nullable=False)
    status = db.Column(db.Enum('ACTIVE', 'BLOCKED', 'EXPIRED'), nullable=False, default='ACTIVE')
        
    def __repr__(self):
        return f"Card(card_id = {self.card_id}, account_id = {self.account_id}, card_type = {self.card_type}, card_number = {self.card_number}, expiration_date = {self.expiration_date}, cvv = {self.cvv}, status = {self.status})"

class Transaction(db.Model):
    __tablename__ = 'transaction'
    
    transaction_id = db.Column(BINARY(16), primary_key=True, default=generate_uuid)
    from_account_id = db.Column(BINARY(16), db.ForeignKey('account.account_id'), nullable=False)
    to_account_id = db.Column(BINARY(16), db.ForeignKey('account.account_id'), nullable=True)
    transaction_type = db.Column(db.Enum('DEPOSIT', 'WITHDRAWAL', 'TRANSFER'), nullable=False)
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    transaction_timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint('amount > 0', name='check_amount_positive'),
    )
        
    def __repr__(self):
        return f"Transaction(transaction_id = {self.transaction_id}, from_account_id = {self.from_account_id}, to_account_id = {self.to_account_id}, transaction_type = {self.transaction_type}, amount = {self.amount}, transaction_timestamp = {self.transaction_timestamp})"

class CustomerSupport(db.Model):
    __tablename__ = 'customer_support'
    
    ticket_id = db.Column(BINARY(16), primary_key=True, default=generate_uuid)
    customer_id = db.Column(BINARY(16), db.ForeignKey('customer.customer_id'), nullable=False)
    issue_description = db.Column(db.Text, nullable=False)
    status = db.Column(db.Enum('OPEN', 'IN_PROGRESS', 'RESOLVED'), nullable=False, default='OPEN')
    resolution_details = db.Column(db.Text, nullable=True)
    created_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    resolved_date = db.Column(db.DateTime)
        
    def __repr__(self):
        return f"CustomerSupport(ticket_id = {self.ticket_id}, customer_id = {self.customer_id}, issue_description = {self.issue_description}, status = {self.status}, resolution_details = {self.resolution_details}, created_date = {self.created_date}, resolved_date = {self.resolved_date})"

class CreditScore(db.Model):
    __tablename__ = 'credit_score'
    
    credit_score_id = db.Column(BINARY(16), primary_key=True, default=generate_uuid)
    customer_id = db.Column(BINARY(16), db.ForeignKey('customer.customer_id'), nullable=False)
    score = db.Column(db.Numeric(5, 2), nullable=False)
    risk_category = db.Column(db.String(50), nullable=False)
    computed_by_system = db.Column(db.Boolean)

    __table_args__ = (
        db.CheckConstraint('score >= 300 AND score <= 850', name='check_score_range'),
    )
        
    def __repr__(self):
        return f"CreditScore(credit_score_id = {self.credit_score_id}, customer_id = {self.customer_id}, score = {self.score}, risk_category = {self.risk_category}, computed_by_system = {self.computed_by_system})"

branch_args = reqparse.RequestParser()
branch_args.add_argument('branch_name', type=str, required=True, help='Branch name is required')
branch_args.add_argument('address_line1', type=str, required=True, help='Address line 1 is required')
branch_args.add_argument('address_line2', type=str)
branch_args.add_argument('city', type=str, required=True, help='City is required')
branch_args.add_argument('state', type=str, required=True, help='State is required')
branch_args.add_argument('zip_code', type=str, required=True, help='Zip code is required')
branch_args.add_argument('phone_number', type=str, required=True, help='Phone number is required')

customer_args = reqparse.RequestParser()
customer_args.add_argument('first_name', type=str, required=True, help='First name is required')
customer_args.add_argument('last_name', type=str, required=True, help='Last name is required')
customer_args.add_argument('date_of_birth', type=str, required=True, help='Date of birth is required')
customer_args.add_argument('phone_number', type=str, required=True, help='Phone number is required')
customer_args.add_argument('email', type=str, required=True, help='Email is required')
customer_args.add_argument('address_line1', type=str, required=True, help='Address line 1 is required')
customer_args.add_argument('address_line2', type=str)
customer_args.add_argument('city', type=str, required=True, help='City is required')
customer_args.add_argument('state', type=str, required=True, help='State is required')
customer_args.add_argument('zip_code', type=str, required=True, help='Zip code is required')
customer_args.add_argument('branch_id', type=str, required=True, help='Branch ID is required')

account_args = reqparse.RequestParser()
account_args.add_argument('customer_id', type=str, required=True, help='Customer ID is required')
account_args.add_argument('account_type', type=str, required=True, help='Account type is required')
account_args.add_argument('balance', type=float)

loan_args = reqparse.RequestParser()
loan_args.add_argument('customer_id', type=str, required=True, help='Customer ID is required')
loan_args.add_argument('loan_type', type=str, required=True, help='Loan type is required')
loan_args.add_argument('principal_amount', type=float, required=True, help='Principal amount is required')
loan_args.add_argument('interest_rate', type=float)
loan_args.add_argument('start_date', type=str, required=True, help='Start date is required')
loan_args.add_argument('end_date', type=str, required=True, help='End date is required')
loan_args.add_argument('status', type=str)

loan_payment_args = reqparse.RequestParser()
loan_payment_args.add_argument('loan_id', type=str, required=True, help='Loan ID is required')
loan_payment_args.add_argument('payment_date', type=str)
loan_payment_args.add_argument('payment_amount', type=float, required=True, help='Payment amount is required')
loan_payment_args.add_argument('remaining_balance', type=float, required=True, help='Remaining balance is required')

employee_args = reqparse.RequestParser()
employee_args.add_argument('branch_id', type=str, required=True, help='Branch ID is required')
employee_args.add_argument('first_name', type=str, required=True, help='First name is required')
employee_args.add_argument('last_name', type=str, required=True, help='Last name is required')
employee_args.add_argument('position', type=str, required=True, help='Position is required')
employee_args.add_argument('phone_number', type=str, required=True, help='Phone number is required')
employee_args.add_argument('email', type=str, required=True, help='Email is required')

card_args = reqparse.RequestParser()
card_args.add_argument('account_id', type=str, required=True, help='Account ID is required')
card_args.add_argument('card_type', type=str, required=True, help='Card type is required')
card_args.add_argument('card_number', type=str, required=True, help='Card number is required')
card_args.add_argument('expiration_date', type=str, required=True, help='Expiration date is required')
card_args.add_argument('cvv', type=str, required=True, help='CVV is required')
card_args.add_argument('status', type=str)

transaction_args = reqparse.RequestParser()
transaction_args.add_argument('from_account_id', type=str, required=True, help='From account ID is required')
transaction_args.add_argument('to_account_id', type=str)
transaction_args.add_argument('transaction_type', type=str, required=True, help='Transaction type is required')
transaction_args.add_argument('amount', type=float, required=True, help='Amount is required')

customer_support_args = reqparse.RequestParser()
customer_support_args.add_argument('customer_id', type=str, required=True, help='Customer ID is required')
customer_support_args.add_argument('issue_description', type=str, required=True, help='Issue description is required')
customer_support_args.add_argument('status', type=str)
customer_support_args.add_argument('resolution_details', type=str)
customer_support_args.add_argument('resolved_date', type=str)

credit_score_args = reqparse.RequestParser()
credit_score_args.add_argument('customer_id', type=str, required=True, help='Customer ID is required')
credit_score_args.add_argument('score', type=float, required=True, help='Credit score is required')
credit_score_args.add_argument('risk_category', type=str, required=True, help='Risk category is required')
credit_score_args.add_argument('computed_by_system', type=bool, required=True, help='Computed by system is required')

branch_fields = {
    'branch_id': fields.String,
    'branch_name': fields.String,
    'address_line1': fields.String,
    'address_line2': fields.String,
    'city': fields.String,
    'state': fields.String,
    'zip_code': fields.String,
    'phone_number': fields.String,
}

customer_fields = {
    'customer_id': fields.String,
    'first_name': fields.String,
    'last_name': fields.String,
    'date_of_birth': fields.String,
    'phone_number': fields.String,
    'email': fields.String,
    'address_line1': fields.String,
    'address_line2': fields.String,
    'city': fields.String,
    'state': fields.String,
    'zip_code': fields.String,
    'branch_id': fields.String,
}

account_fields = {
    'account_id': fields.String,
    'customer_id': fields.String,
    'account_type': fields.String,
    'balance': fields.Float,
    'creation_date': fields.DateTime,
}

loan_fields = {
    'loan_id': fields.String,
    'customer_id': fields.String,
    'loan_type': fields.String,
    'principal_amount': fields.Float,
    'interest_rate': fields.Float,
    'start_date': fields.String,
    'end_date': fields.String,
    'status': fields.String,
}

loan_payment_fields = {
    'loan_payment_id': fields.String,
    'loan_id': fields.String,
    'payment_date': fields.String,
    'payment_amount': fields.Float,
    'remaining_balance': fields.Float,
}

employee_fields = {
    'employee_id': fields.String,
    'branch_id': fields.String,
    'first_name': fields.String,
    'last_name': fields.String,
    'position': fields.String,
    'hire_date': fields.DateTime,
    'phone_number': fields.String,
    'email': fields.String,
}

card_fields = {
    'card_id': fields.String,
    'account_id': fields.String,
    'card_type': fields.String,
    'card_number': fields.String,
    'expiration_date': fields.String,
    'cvv': fields.String,
    'status': fields.String,
}

transaction_fields = {
    'transaction_id': fields.String,
    'from_account_id': fields.String,
    'to_account_id': fields.String,
    'transaction_type': fields.String,
    'amount': fields.Float,
    'transaction_timestamp': fields.DateTime,
}

customer_support_fields = {
    'ticket_id': fields.String,
    'customer_id': fields.String,
    'issue_description': fields.String,
    'status': fields.String,
    'resolution_details': fields.String,
    'created_date': fields.DateTime,
    'resolved_date': fields.DateTime,
}

credit_score_fields = {
    'credit_score_id': fields.String,
    'customer_id': fields.String,
    'score': fields.Float,
    'risk_category': fields.String,
    'computed_by_system': fields.Boolean,
}

class BranchResourceAll(Resource):
    @marshal_with(branch_fields)
    def get(self):
        branch = Branch.query.all()
        return branch

    @marshal_with(branch_fields)
    def post(self):
        args = branch_args.parse_args()
        branch = Branch(
            branch_name=args['branch_name'], 
            address_line1=args['address_line1'], 
            address_line2=args['address_line2'], 
            city=args['city'], 
            state=args['state'], 
            zip_code=args['zip_code'], 
            phone_number=args['phone_number']
        )
        db.session.add(branch)
        db.session.commit()
        branches = Branch.query.all()
        return branches

class BranchResource(Resource):
    @marshal_with(branch_fields)
    def get(self, branch_id):
        branch = Branch.query.filter_by(branch_id=branch_id).first()
        if not branch:
            abort(404, message='Branch not found')
        return branch
    
    @marshal_with(branch_fields)
    def put(self, branch_id):
        args = branch_args.parse_args()
        branch = Branch.query.filter_by(branch_id=branch_id).first()
        if not branch:
            abort(404, message='Branch not found')
        branch.branch_name = args['branch_name']
        branch.address_line1 = args['address_line1']
        branch.address_line2 = args['address_line2']
        branch.city = args['city']
        branch.state = args['state']
        branch.zip_code = args['zip_code']
        branch.phone_number = args['phone_number']
        db.session.commit()
        return branch

@app.route('/')
def home():
    return '<h1>Welcome to the Banking API!</h1>'

if __name__ == '__main__':
    app.run(debug=True)