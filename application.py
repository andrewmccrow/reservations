import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

# Andy - added to timstamp
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    # Andy Code
    # get current users cash total
    result = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
    cash = result[0]['cash']

    # determine all stocks belonging to user
    portfolio = db.execute("SELECT stock, quantity FROM portfolio WHERE userID=:id", id=session["user_id"])

    if not portfolio:
        stocks = [{'stock': 'CASH', 'quantity': 'N/A', 'price': 'N/A', 'total': cash}]
        price = 'N/A'
        name = 'CASH'
        total = cash
        final_amount = cash
        #return apology("You have no stocks in your portfolio")
        return render_template("index.html", stocks=portfolio, cash=cash, total=final_amount, name=name)

    final_amount = cash

    # determine current price of stocks, stock total value and grand total value
    for stock in portfolio:
        price = lookup(stock['stock'])['price']
        name = lookup(stock['stock'])['name']
        total = stock['quantity'] * price
        stock.update({'price': price, 'total': total})
        final_amount = final_amount+total

    return render_template("index.html", stocks=portfolio, cash=cash, total=final_amount, name=name)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # Andy Code
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 403)

        # Ensure no of shares was submitted
        if not request.form.get("shares"):
            return apology("enter number of shares", 403)

        # ensure number of shares is valid
        if int(request.form.get("shares")) <= 0:
            return apology("enter a positive number of shares (int)")

        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        stock_info = lookup(symbol)

        # check Stock exists
        if stock_info == None:
            return apology("Invalid Stock Symbol")

        # calculate cost of transaction
        cost = int(shares) * stock_info['price']

        # determine amopunt of cash user has
        reserve1 = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
        reserve = (reserve1[0])['cash']

        # check user has enough cash
        if cost > reserve:
            return apology("You do not have enough cash to make this purchase")

        # record transaction in "transactions DB"
        add_transaction = db.execute("INSERT INTO transactions (timestamp, userID, stock, shares, price) VALUES (:timestamp, :userID, :stock, :shares, :price)",
                                    timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), userID=session["user_id"], stock=stock_info["symbol"], shares=int(request.form.get("shares")),
                                    price=stock_info['price'])

        # adjust cash amount fro user in "users DB"
        db.execute("UPDATE users SET cash=cash-:cost WHERE id=:id", cost=cost, id=session["user_id"])

        # determine current number of shares of symbol in portfolio
        current_portfolio = db.execute("SELECT quantity FROM portfolio WHERE stock=:stock AND userID=:id",
                                        stock=stock_info["symbol"], id=session["user_id"])

        # add to portfolio database
        # if symbol is new, add to portfolio
        if not current_portfolio:
            db.execute("INSERT INTO portfolio (userID, stock, quantity) VALUES (:id, :stock, :quantity)",
                        id=session["user_id"], stock=stock_info["symbol"], quantity=int(request.form.get("shares")))

        # if symbol is already in portfolio, update quantity of shares and total
        else:
            db.execute("UPDATE portfolio SET quantity=quantity+:quantity WHERE stock=:stock AND userID=:id",
                        id=session["user_id"], quantity=int(request.form.get("shares")), stock=stock_info["symbol"]);

        return redirect("/")
    # else:
    return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # pull all transactions belonging to user
    transactions = db.execute("SELECT Timestamp, stock, shares, price FROM transactions WHERE userID=:id", id=session["user_id"])

    if not transactions:
        return apology("You have not bought or sold any stocks")

    return render_template("history.html", stocks=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


# Andy codeed route to add cash
@app.route("/addcash", methods=["GET", "POST"])
@login_required
def addcash():
    # Andy code
    if request.method == "POST":

        # Ensure cash added_cash was submitted
        if not request.form.get("added_cash"):
            return apology("must provide amount of cash to add", 403)

        # ensure amount of cash is valid
        if int(request.form.get("added_cash")) <= 0:
            return apology("enter a positive amount of cash")

        # get current users cash total
        result = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
        current_cash = result[0]['cash']

        # get amount of cash to add and add to current cash
        added_cash = request.form.get("added_cash")
        new_cash = int(current_cash) + int(added_cash)

        # adjust cash amount for user in "users DB"
        db.execute("UPDATE users SET cash=cash+:added_cash WHERE id=:id", added_cash=added_cash, id=session["user_id"]);

        # record transaction in "transactions DB"
        add_transaction = db.execute("INSERT INTO transactions (timestamp, userID, stock, shares, price) VALUES (:timestamp, :userID, :stock, :shares, :price)",
                                    timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), userID=session["user_id"], stock="CASH", shares="N/A", price=added_cash)

        return redirect("/")
    # else:
    result = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
    current_cash = result[0]['cash']
    return render_template("addcash.html", current_cash=current_cash)


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    # Andy code
    if request.method == "POST":
        symbol = request.form.get("symbol")
        stock_info = lookup(symbol)
        if stock_info == None:
            return apology("Invalid Stock Symbol")
        stock_price = stock_info['price']
        return render_template("quoted.html", stock_info=stock_info, stock_price=stock_price)
    # else:
    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # Andy Code
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure confirmation password was submitted
        elif not request.form.get("confirmation"):
            return apology("must confirm password", 400)

        # Ensure confirmation password and password match
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords do not match", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        # Ensure username is unique and not already taken
        if len(rows) != 0:
            return apology("username is already taken", 400)

        # Andy - insert username and password in registartion form into finance DB
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        passwordHASH = generate_password_hash(password)
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, passwordHASH)

        # remember which user has logged in
        #session["user_id"] = result

        return redirect("/")

    else:
        # Andy - display register template
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # Andy Code
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 403)

        # Ensure no of shares was submitted
        if not request.form.get("shares"):
            return apology("enter number of shares", 403)

        # ensure number of shares is valid
        if int(request.form.get("shares")) <= 0:
            return apology("enter a positive number of shares (int)")

        # check that number of shares being sold does not exceed quantity in portfolio
        held_shares = db.execute("SELECT quantity FROM portfolio WHERE :stock=stock AND userID=:id",
                                stock=request.form.get("symbol"), id=session["user_id"])

        if int(request.form.get("shares")) > held_shares[0]['quantity']:
            return apology("You do not hold enough shares")

        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        stock_info = lookup(symbol)

        # calculate cost of transaction
        cost = int(shares) * stock_info['price']

        # determine amount of cash user has
        reserve1 = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
        reserve = (reserve1[0])['cash']

        # update cash amount in users database
        db.execute("UPDATE users SET cash=cash+:cost WHERE id=:id", cost=cost, id=session["user_id"])

        # record transaction in "transactions DB"
        add_transaction = db.execute("INSERT INTO transactions (timestamp, userID, stock, shares, price) VALUES (:timestamp, :userID, :stock, :shares, :price)",
                                     timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), userID=session["user_id"], stock=stock_info["symbol"],
                                     shares=-int(request.form.get("shares")), price=stock_info['price'])

        # determine current number of shares of symbol in portfolio
        current_portfolio = db.execute("SELECT quantity FROM portfolio WHERE stock=:stock AND userID=:id",
                                        stock=stock_info["symbol"], id=session["user_id"])

        # deduct from portfolio database
        db.execute("UPDATE portfolio SET quantity=quantity+:quantity WHERE stock=:stock AND userID=:id",
                    id=session["user_id"], quantity=-int(request.form.get("shares")), stock=stock_info["symbol"])

        return redirect("/")
    #else:
    #genrate list of held stocks in portfolio
    portfolio = db.execute("SELECT stock FROM portfolio WHERE userID=:id",
                        id=session["user_id"])
    return render_template("sell.html", stocks=portfolio)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
