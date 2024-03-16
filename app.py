import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # holdings is a list of dictionaries where each list element is a dictionary associated with a holding
    holdings = db.execute("SELECT * FROM holdings WHERE user_id = ?", session["user_id"])
    total_value = 0
    pnl = 0
    balance = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    balance = round(balance[0]["cash"], 2)
    print(balance)
    for holding in holdings:
        holding["current_price"] = lookup(holding["symbol"])["price"]
        holding["gain"] = (holding["current_price"]/holding["avg_price"]-1)*100
        holding["value"] = holding["current_price"]*holding["shares"]
        holding["profit"] = (holding["current_price"]-holding["avg_price"])*holding["shares"]

        # rounding to 2 dp
        for key in holding.keys():
            if type(holding[key]) != str:
                holding[key] = round(holding[key], 2)

        total_value += holding["value"]
        pnl += holding["profit"]

        pnl, total_value = round(pnl, 2), round(total_value, 2)



    # print(holdings)

    return render_template("portfolio.html", holdings=holdings, total_value = total_value, pnl = pnl, balance = balance)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        quantity = float(request.form.get("quantity"))

        result = lookup(symbol)
        if result == None:
            return apology("stock not found")

        # print(type(result["price"]))
        # print(type(quantity))
        value = result["price"] * quantity

        currentbalance = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        cash = currentbalance[0]["cash"]

        print(currentbalance)

        if cash < value:
            return apology("too poor")

        cash -= value

        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, session["user_id"])

        # if share is in portfolio
        if (len(db.execute("SELECT * FROM holdings WHERE user_id = ? AND symbol = ?", session["user_id"], symbol)) != 0):
            currentshares = db.execute("SELECT shares, avg_price FROM holdings WHERE user_id = ? AND symbol = ?", session["user_id"], symbol)

            db.execute("UPDATE holdings SET shares = ? WHERE symbol = ?", currentshares[0]["shares"] + quantity, symbol)
            # calculates avg buy price
            db.execute("UPDATE holdings SET avg_price = ? WHERE symbol = ?", (currentshares[0]["shares"] * currentshares[0]["avg_price"] + value)/(currentshares[0]["shares"] + quantity), symbol)

        # if share not in portfolio
        else:
            db.execute("INSERT INTO holdings (user_id, symbol, shares, avg_price) VALUES (?, ?, ?, ?)", session["user_id"], symbol, quantity, result["price"])

        return render_template("buy.html")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    return apology("TODO")


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
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
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


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "POST":
        result = lookup(request.form.get("symbol"))

        if result == None:
            return render_template("quoted.html", symbol = "", price = "")

        return render_template("quoted.html", symbol = result["symbol"], price = result["price"])

    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        username = request.form.get("username")
        hash = generate_password_hash(request.form.get("password"))
        rows = db.execute("SELECT username FROM users WHERE username = ? ", username)

        if len(rows) != 0 or username == "" or request.form.get("password") != request.form.get("confirmation"):
            return apology("invalid", 403)

        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash)

        return render_template("login.html")

    else:
        return render_template("register.html")

@app.route("/friends", methods=["GET", "POST"])
@login_required
def friends():

    if request.method == "POST":

        username = request.form.get("username")
        friend_id = db.execute("SELECT id FROM users WHERE username = ?", username)
        print(friend_id)
        friend_id = friend_id[0]["id"]
        friends = db.execute("SELECT * FROM friends WHERE id_1 = ? OR id_2 = ?", session["user_id"], session["user_id"])

        friend_ids = []
        for friend in friends:
            if friend["id_1"] == session["user_id"]:
                friend_ids.append(friend["id_2"])
            else:
                friend_ids.append(friend["id_1"])

        if friend_id not in friend_ids:
            return apology("not friends")



        holdings = db.execute("SELECT * FROM holdings WHERE user_id = ?", friend_id)
        total_value = 0
        pnl = 0
        balance = db.execute("SELECT cash FROM users WHERE id = ?", friend_id)
        balance = round(balance[0]["cash"], 2)
        for holding in holdings:
            holding["current_price"] = lookup(holding["symbol"])["price"]
            holding["gain"] = (holding["current_price"]/holding["avg_price"]-1)*100
            holding["value"] = holding["current_price"]*holding["shares"]
            holding["profit"] = (holding["current_price"]-holding["avg_price"])*holding["shares"]

            # rounding to 2 dp
            for key in holding.keys():
                if type(holding[key]) != str:
                    holding[key] = round(holding[key], 2)

            total_value += holding["value"]
            pnl += holding["profit"]

        return render_template("/friends.html", friends = friends, holdings=holdings, total_value = total_value, pnl = pnl, friend_username = username, balance = balance)

    return render_template("/friendsearch.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    holdings = db.execute("SELECT * FROM holdings WHERE user_id = ?", session["user_id"])
    # print(holdings)
    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        quantity = float(request.form.get("quantity"))

        stockaval = False
        quantityaval = 0
        i=0
        while not stockaval and i<len(holdings):
            if symbol == holdings[i]["symbol"]:
                quantityaval = holdings[i]["shares"]
                # print(holdings[i])
                # print(quantityaval)
                stockaval = True
            i+=1


        print(quantity)
        print(quantityaval)

        if stockaval and quantity < quantityaval:
            # subtract stock quantity from holdings and add money
            db.execute("UPDATE holdings SET shares = ? WHERE symbol = ?", round(quantityaval - quantity, 4), symbol)

        elif stockaval and quantity == quantityaval:
            db.execute("DELETE FROM holdings WHERE symbol = ?", symbol)

        else:
            return apology("not enough stock")

        return redirect("/sell")

    else:
        return render_template("sell.html", holdings = holdings)
