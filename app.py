from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import uuid
from datetime import date
from functools import wraps

app = Flask(__name__)
app.secret_key = 'bookstore_secret_key_2024'
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'images')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# ─── DB CONFIG ───────────────────────────────────────────────────────────────

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Oracle04',
    'database': 'bookstore_db'
}

def get_db():
    return mysql.connector.connect(**DB_CONFIG)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ─── AUTH DECORATORS ─────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated

def customer_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'customer':
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated

# ─── ROUTES: AUTH ─────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        # Admin login
        if username == 'admin' and password == 'admin123':
            session['user'] = 'admin'
            session['role'] = 'admin'
            session['name'] = 'Administrator'
            return redirect(url_for('books'))

        # Customer login
        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM CUSTOMER WHERE USERNAME = %s", (username,))
        customer = cur.fetchone()
        cur.close(); db.close()

        if customer and check_password_hash(customer['PASSWORD_HASH'], password):
            session['user'] = username
            session['role'] = 'customer'
            session['cust_id'] = customer['CUST_ID']
            session['name'] = customer['FIRST_NAME'] + ' ' + customer['LAST_NAME']
            return redirect(url_for('books'))
        else:
            flash('Invalid credentials', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.form
        try:
            db = get_db()
            cur = db.cursor()
            # TCL: Transaction with savepoint
            cur.execute("START TRANSACTION")
            cur.execute("SAVEPOINT before_register")
            cur.execute("""
                INSERT INTO CUSTOMER(FIRST_NAME, LAST_NAME, PHONE_NUMBER, EMAIL,
                    HOUSE_NUMBER, STREET, CITY, STATE, PINCODE, USERNAME, PASSWORD_HASH)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                data['first_name'], data['last_name'], data['phone'], data['email'],
                data['house_number'], data['street'], data['city'], data['state'],
                data['pincode'], data['username'], generate_password_hash(data['password'])
            ))
            db.commit()
            cur.close(); db.close()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except mysql.connector.IntegrityError:
            cur.execute("ROLLBACK")
            flash('Username or Email already exists.', 'error')
            cur.close(); db.close()
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# ─── ROUTES: BOOKS ───────────────────────────────────────────────────────────

@app.route('/books')
def books():
    db = get_db()
    cur = db.cursor(dictionary=True)

    sort = request.args.get('sort', '')
    language = request.args.get('language', '')
    author = request.args.get('author', '')
    publisher = request.args.get('publisher', '')
    search = request.args.get('search', '')

    # Base query using VIEW (covers LEFT JOIN, aggregate)
    query = "SELECT * FROM BOOK_FULL_DETAILS WHERE 1=1"
    params = []

    # WHERE + LIKE
    if search:
        query += " AND TITLE LIKE %s"
        params.append(f'%{search}%')

    # WHERE + IN style filter
    if language:
        query += " AND LANGUAGE = %s"
        params.append(language)

    if author:
        query += " AND AUTHOR_NAME LIKE %s"
        params.append(f'%{author}%')

    if publisher:
        query += " AND PUBLISHER_NAME LIKE %s"
        params.append(f'%{publisher}%')

    # ORDER BY
    if sort == 'price_asc':
        query += " ORDER BY PRICE ASC"
    elif sort == 'price_desc':
        query += " ORDER BY PRICE DESC"
    else:
        query += " ORDER BY TITLE ASC"

    cur.execute(query, params)
    all_books = cur.fetchall()

    # DISTINCT languages for filter
    cur.execute("SELECT DISTINCT LANGUAGE FROM BOOK ORDER BY LANGUAGE")
    languages = [r['LANGUAGE'] for r in cur.fetchall()]

    # Aggregate: total books
    cur.execute("SELECT COUNT(*) AS total, SUM(QUANTITY_AVAILABLE) AS total_qty, AVG(PRICE) AS avg_price, MAX(PRICE) AS max_price, MIN(PRICE) AS min_price FROM BOOK")
    stats = cur.fetchone()

    # Top ordered books (using VIEW)
    cur.execute("SELECT * FROM TOP_ORDERED_BOOKS LIMIT 5")
    top_books = cur.fetchall()

    # All authors and publishers for filter dropdowns
    cur.execute("SELECT NAME FROM AUTHOR ORDER BY NAME")
    authors = [r['NAME'] for r in cur.fetchall()]
    cur.execute("SELECT NAME FROM PUBLISHER_DETAILS ORDER BY NAME")
    publishers = [r['NAME'] for r in cur.fetchall()]

    cur.close(); db.close()

    not_found_msg = None
    if search and not all_books:
        # Log to SEARCH_LOG (simulating trigger behavior)
        db2 = get_db()
        c2 = db2.cursor()
        c2.execute("INSERT INTO SEARCH_LOG(SEARCH_TYPE,SEARCH_TERM,RESULT) VALUES('BOOK',%s,'NOT FOUND')", (search,))
        db2.commit(); c2.close(); db2.close()
        not_found_msg = "NOT AVAILABLE AT THE MOMENT"

    return render_template('books.html', books=all_books, languages=languages,
                           stats=stats, top_books=top_books, authors=authors,
                           publishers=publishers, not_found_msg=not_found_msg,
                           search=search, sort=sort, language=language)

@app.route('/books/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_book():
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM AUTHOR ORDER BY NAME")
    authors = cur.fetchall()
    cur.execute("SELECT * FROM PUBLISHER_DETAILS ORDER BY NAME")
    publishers = cur.fetchall()
    cur.close(); db.close()

    if request.method == 'POST':
        data = request.form
        image_path = None

        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(str(uuid.uuid4()) + '_' + file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_path = filename

        try:
            db = get_db()
            cur = db.cursor()
            # DML: INSERT
            cur.execute("""
                INSERT INTO BOOK(ISBN, TITLE, EDITION, PRICE, PUBLICATION_YEAR,
                    LANGUAGE, QUANTITY_AVAILABLE, P_ID, A_ID, IMAGE_PATH)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (data['isbn'], data['title'], data['edition'], data['price'],
                  data['pub_year'], data['language'], data['quantity'],
                  data.get('publisher_id') or None, data.get('author_id') or None, image_path))
            db.commit()
            cur.close(); db.close()
            flash('Book added successfully!', 'success')
            return redirect(url_for('books'))
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')

    return render_template('add_book.html', authors=authors, publishers=publishers)

@app.route('/books/edit/<isbn>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_book(isbn):
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM BOOK_FULL_DETAILS WHERE ISBN = %s", (isbn,))
    book = cur.fetchone()
    cur.execute("SELECT * FROM AUTHOR ORDER BY NAME")
    authors = cur.fetchall()
    cur.execute("SELECT * FROM PUBLISHER_DETAILS ORDER BY NAME")
    publishers = cur.fetchall()

    # Get current A_ID and P_ID
    cur.execute("SELECT A_ID, P_ID FROM BOOK WHERE ISBN = %s", (isbn,))
    ids = cur.fetchone()
    cur.close(); db.close()

    if not book:
        flash('Book not found', 'error')
        return redirect(url_for('books'))

    if request.method == 'POST':
        data = request.form
        image_path = book['IMAGE_PATH']

        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(str(uuid.uuid4()) + '_' + file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_path = filename

        db = get_db()
        cur = db.cursor()
        # DML: UPDATE
        cur.execute("""
            UPDATE BOOK SET TITLE=%s, EDITION=%s, PRICE=%s, PUBLICATION_YEAR=%s,
            LANGUAGE=%s, QUANTITY_AVAILABLE=%s, P_ID=%s, A_ID=%s, IMAGE_PATH=%s
            WHERE ISBN=%s
        """, (data['title'], data['edition'], data['price'], data['pub_year'],
              data['language'], data['quantity'],
              data.get('publisher_id') or None, data.get('author_id') or None,
              image_path, isbn))
        db.commit()
        cur.close(); db.close()
        flash('Book updated!', 'success')
        return redirect(url_for('books'))

    return render_template('edit_book.html', book=book, authors=authors, publishers=publishers, ids=ids)

@app.route('/books/delete/<isbn>')
@login_required
@admin_required
def delete_book(isbn):
    db = get_db()
    cur = db.cursor()
    # DML: DELETE
    cur.execute("DELETE FROM BOOK WHERE ISBN = %s", (isbn,))
    db.commit()
    cur.close(); db.close()
    flash('Book deleted.', 'success')
    return redirect(url_for('books'))

# ─── ROUTES: AUTHORS ─────────────────────────────────────────────────────────

@app.route('/authors')
def authors():
    db = get_db()
    cur = db.cursor(dictionary=True)
    search = request.args.get('search', '')

    if search:
        # Using LIKE and string functions in query
        cur.execute("""
            SELECT A.A_ID, UPPER(A.NAME) AS NAME_UPPER, A.NAME, A.EMAIL, A.PHONE,
                   COUNT(B.ISBN) AS BOOKS_WRITTEN
            FROM AUTHOR A
            LEFT JOIN BOOK B ON A.A_ID = B.A_ID
            WHERE A.NAME LIKE %s
            GROUP BY A.A_ID
            ORDER BY A.NAME
        """, (f'%{search}%',))
    else:
        cur.execute("""
            SELECT A.A_ID, A.NAME, A.EMAIL, A.PHONE,
                   COUNT(B.ISBN) AS BOOKS_WRITTEN
            FROM AUTHOR A
            LEFT JOIN BOOK B ON A.A_ID = B.A_ID
            GROUP BY A.A_ID
            ORDER BY A.NAME
        """)

    all_authors = cur.fetchall()

    not_found_msg = None
    if search and not all_authors:
        cur.execute("INSERT INTO SEARCH_LOG(SEARCH_TYPE,SEARCH_TERM,RESULT) VALUES('AUTHOR',%s,'NOT FOUND')", (search,))
        db.commit()
        not_found_msg = "NO SUCH AUTHOR"

    # Get books per author
    author_books = {}
    for a in all_authors:
        cur.execute("""
            SELECT ISBN, TITLE, PRICE, LANGUAGE FROM BOOK WHERE A_ID = %s
        """, (a['A_ID'],))
        author_books[a['A_ID']] = cur.fetchall()

    cur.close(); db.close()
    return render_template('authors.html', authors=all_authors, author_books=author_books,
                           not_found_msg=not_found_msg, search=search)

@app.route('/authors/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_author():
    if request.method == 'POST':
        data = request.form
        db = get_db()
        cur = db.cursor()
        cur.execute("INSERT INTO AUTHOR(NAME, EMAIL, PHONE) VALUES(%s,%s,%s)",
                    (data['name'], data['email'], data['phone']))
        db.commit()
        cur.close(); db.close()
        flash('Author added!', 'success')
        return redirect(url_for('authors'))
    return render_template('add_author.html')

# ─── ROUTES: PUBLISHERS ──────────────────────────────────────────────────────

@app.route('/publishers')
def publishers():
    db = get_db()
    cur = db.cursor(dictionary=True)
    search = request.args.get('search', '')

    if search:
        cur.execute("""
            SELECT P.P_ID, P.NAME, P.ADDRESS, P.EMAIL, P.PHONE_NUMBER,
                   COUNT(B.ISBN) AS BOOKS_PUBLISHED
            FROM PUBLISHER_DETAILS P
            LEFT JOIN BOOK B ON P.P_ID = B.P_ID
            WHERE P.NAME LIKE %s
            GROUP BY P.P_ID
            ORDER BY P.NAME
        """, (f'%{search}%',))
    else:
        cur.execute("""
            SELECT P.P_ID, P.NAME, P.ADDRESS, P.EMAIL, P.PHONE_NUMBER,
                   COUNT(B.ISBN) AS BOOKS_PUBLISHED
            FROM PUBLISHER_DETAILS P
            LEFT JOIN BOOK B ON P.P_ID = B.P_ID
            GROUP BY P.P_ID
            ORDER BY P.NAME
        """)

    all_pubs = cur.fetchall()

    not_found_msg = None
    if search and not all_pubs:
        cur.execute("INSERT INTO SEARCH_LOG(SEARCH_TYPE,SEARCH_TERM,RESULT) VALUES('PUBLISHER',%s,'NOT FOUND')", (search,))
        db.commit()
        not_found_msg = "NO SUCH PUBLISHER"

    pub_books = {}
    for p in all_pubs:
        cur.execute("SELECT ISBN, TITLE, PRICE FROM BOOK WHERE P_ID = %s", (p['P_ID'],))
        pub_books[p['P_ID']] = cur.fetchall()

    cur.close(); db.close()
    return render_template('publishers.html', publishers=all_pubs, pub_books=pub_books,
                           not_found_msg=not_found_msg, search=search)

@app.route('/publishers/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_publisher():
    if request.method == 'POST':
        data = request.form
        db = get_db()
        cur = db.cursor()
        cur.execute("INSERT INTO PUBLISHER_DETAILS(NAME, ADDRESS, EMAIL, PHONE_NUMBER) VALUES(%s,%s,%s,%s)",
                    (data['name'], data['address'], data['email'], data['phone']))
        db.commit()
        cur.close(); db.close()
        flash('Publisher added!', 'success')
        return redirect(url_for('publishers'))
    return render_template('add_publisher.html')

# ─── ROUTES: ORDER ───────────────────────────────────────────────────────────

@app.route('/order', methods=['GET', 'POST'])
@login_required
@customer_required
def order_books():
    db = get_db()
    cur = db.cursor(dictionary=True)
    # Books with quantity > 0
    cur.execute("SELECT ISBN, TITLE, PRICE, QUANTITY_AVAILABLE, AUTHOR_NAME FROM BOOK_FULL_DETAILS WHERE QUANTITY_AVAILABLE > 0 ORDER BY TITLE")
    available_books = cur.fetchall()

    # Pre-fill customer info
    cur.execute("SELECT * FROM CUSTOMER WHERE CUST_ID = %s", (session['cust_id'],))
    customer = cur.fetchone()
    cur.close(); db.close()

    if request.method == 'POST':
        data = request.form
        isbns = request.form.getlist('isbn[]')
        quantities = request.form.getlist('quantity[]')

        if not isbns:
            flash('Please select at least one book.', 'error')
            return redirect(url_for('order_books'))

        try:
            db = get_db()
            cur = db.cursor(dictionary=True)
            cur.execute("START TRANSACTION")
            cur.execute("SAVEPOINT order_start")

            total_amount = 0
            total_books = 0
            order_items = []

            # Validate stock and calculate total
            for isbn, qty_str in zip(isbns, quantities):
                qty = int(qty_str)
                if qty <= 0:
                    continue
                cur.execute("SELECT TITLE, PRICE, QUANTITY_AVAILABLE FROM BOOK WHERE ISBN = %s FOR UPDATE", (isbn,))
                book = cur.fetchone()
                if not book or book['QUANTITY_AVAILABLE'] < qty:
                    db.rollback()
                    flash(f'Insufficient stock for a selected book.', 'error')
                    cur.close(); db.close()
                    return redirect(url_for('order_books'))
                total_amount += book['PRICE'] * qty
                total_books += qty
                order_items.append({'isbn': isbn, 'title': book['TITLE'], 'qty': qty, 'price': book['PRICE']})

            # INSERT ORDER
            cur2 = db.cursor()
            cur2.execute("""
                INSERT INTO `ORDER`(CUST_ID, ORDER_STATUS, HOUSE_NUMBER, STREET, CITY, STATE, PINCODE, NOS_OF_BOOKS_ORDERED, TOTAL_AMOUNT)
                VALUES(%s,'Pending',%s,%s,%s,%s,%s,%s,%s)
            """, (session['cust_id'], data['house_number'], data['street'], data['city'],
                  data['state'], data['pincode'], total_books, total_amount))

            order_id = cur2.lastrowid
            cur2.execute("SAVEPOINT after_order")

            for item in order_items:
                cur2.execute("""
                    INSERT INTO ORDER_ITEMS(O_ID, ISBN, BOOK_TITLE, QUANTITY, UNIT_PRICE)
                    VALUES(%s,%s,%s,%s,%s)
                """, (order_id, item['isbn'], item['title'], item['qty'], item['price']))

            cur2.execute("SAVEPOINT after_items")

            # PAYMENT
            trans_id = 'TXN' + str(uuid.uuid4().hex[:12]).upper()
            cur2.execute("""
                INSERT INTO PAYMENT(O_ID, AMOUNT_TOTAL, METHOD, PAYMENT_DATE, PAYMENT_STATUS, TRANSACTION_ID)
                VALUES(%s,%s,%s,CURRENT_DATE,'Completed',%s)
            """, (order_id, total_amount, data['payment_method'], trans_id))

            db.commit()
            cur.close(); cur2.close(); db.close()
            flash(f'Order placed! Order ID: {order_id} | Transaction: {trans_id}', 'success')
            return redirect(url_for('books'))

        except Exception as e:
            db.rollback()
            flash(f'Order failed: {str(e)}', 'error')

    return render_template('order.html', books=available_books, customer=customer)

# ─── ROUTES: ADMIN - ORDERS & CUSTOMERS ──────────────────────────────────────

@app.route('/admin/orders')
@login_required
@admin_required
def admin_orders():
    db = get_db()
    cur = db.cursor(dictionary=True)

    status = request.args.get('status', '')
    city = request.args.get('city', '')
    state = request.args.get('state', '')
    order_date = request.args.get('order_date', '')
    search_id = request.args.get('search_id', '')
    search_type = request.args.get('search_type', 'order')

    # Uses the ORDER_CUSTOMER_VIEW (JOIN-based view)
    query = "SELECT * FROM ORDER_CUSTOMER_VIEW WHERE 1=1"
    params = []

    if status:
        query += " AND ORDER_STATUS = %s"
        params.append(status)
    if city:
        query += " AND CITY LIKE %s"
        params.append(f'%{city}%')
    if state:
        query += " AND STATE LIKE %s"
        params.append(f'%{state}%')
    if order_date:
        query += " AND ORDER_DATE = %s"
        params.append(order_date)
    if search_id:
        if search_type == 'order':
            query += " AND O_ID = %s"
        else:
            query += " AND CUST_ID = %s"
        params.append(search_id)

    query += " ORDER BY O_ID DESC"
    cur.execute(query, params)
    orders = cur.fetchall()

    # Get order items for each order
    order_items_map = {}
    for o in orders:
        cur.execute("SELECT * FROM ORDER_ITEMS WHERE O_ID = %s", (o['O_ID'],))
        order_items_map[o['O_ID']] = cur.fetchall()

    # Stats using aggregate functions
    cur.execute("""
        SELECT COUNT(*) AS total_orders,
               SUM(TOTAL_AMOUNT) AS total_revenue,
               AVG(TOTAL_AMOUNT) AS avg_order_value,
               MAX(TOTAL_AMOUNT) AS max_order,
               MIN(TOTAL_AMOUNT) AS min_order
        FROM `ORDER`
    """)
    stats = cur.fetchone()

    # DISTINCT cities and states for filter
    cur.execute("SELECT DISTINCT CITY FROM `ORDER` WHERE CITY IS NOT NULL ORDER BY CITY")
    cities = [r['CITY'] for r in cur.fetchall()]
    cur.execute("SELECT DISTINCT STATE FROM `ORDER` WHERE STATE IS NOT NULL ORDER BY STATE")
    states = [r['STATE'] for r in cur.fetchall()]

    cur.close(); db.close()
    return render_template('admin_orders.html', orders=orders, order_items_map=order_items_map,
                           stats=stats, cities=cities, states=states,
                           status=status, city=city, state=state)

@app.route('/admin/update_order_status', methods=['POST'])
@login_required
@admin_required
def update_order_status():
    order_id = request.form.get('order_id')
    new_status = request.form.get('status')
    db = get_db()
    cur = db.cursor()
    cur.execute("UPDATE `ORDER` SET ORDER_STATUS = %s WHERE O_ID = %s", (new_status, order_id))
    db.commit()
    cur.close(); db.close()
    flash('Order status updated!', 'success')
    return redirect(url_for('admin_orders'))

# ─── API: Get book price for JS calculation ───────────────────────────────────

@app.route('/api/book_price/<isbn>')
def get_book_price(isbn):
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT PRICE, QUANTITY_AVAILABLE FROM BOOK WHERE ISBN = %s", (isbn,))
    book = cur.fetchone()
    cur.close(); db.close()
    if book:
        return jsonify({'price': float(book['PRICE']), 'available': book['QUANTITY_AVAILABLE']})
    return jsonify({'error': 'Not found'}), 404

# ─── MAIN ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)
